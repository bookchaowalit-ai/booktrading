package service

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"sync"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/logger"
)

// HistoricalDataService fetches and stores historical kline (candlestick) data
// from Binance public API into PostgreSQL for backtesting and analysis.
type HistoricalDataService struct {
	pool       *pgxpool.Pool
	httpClient *http.Client
	baseURL    string
	ctx        context.Context
	cancel     context.CancelFunc
	mu         sync.Mutex
	symbols    []string
}

// binanceKlineRaw matches the JSON array response from Binance /api/v3/klines.
// Each element in the outer array is a candle with fields as an inner array.
type binanceKlineRaw []any

// NewHistoricalDataService creates a new HistoricalDataService with the given
// database connection pool and list of symbols to track.
func NewHistoricalDataService(pool *pgxpool.Pool, symbols []string) *HistoricalDataService {
	ctx, cancel := context.WithCancel(context.Background())
	return &HistoricalDataService{
		pool:       pool,
		httpClient: &http.Client{Timeout: 30 * time.Second},
		baseURL:    "https://api.binance.com",
		ctx:        ctx,
		cancel:     cancel,
		symbols:    symbols,
	}
}

// StartSync launches a background goroutine that periodically fetches the latest
// klines for each configured symbol and interval. The interval parameter
// controls how often the sync runs (e.g. "1m", "5m"). The sync itself fetches
// "1h" and "1d" klines on every tick.
func (s *HistoricalDataService) StartSync(interval string) {
	d, err := time.ParseDuration(interval)
	if err != nil {
		logger.Error("Invalid sync interval, defaulting to 1m", "interval", interval, "error", err)
		d = 1 * time.Minute
	}

	go func() {
		logger.Info("Historical data sync started", "interval", d.String(), "symbols", s.symbols)
		ticker := time.NewTicker(d)
		defer ticker.Stop()

		intervals := []string{"1h", "1d"}

		for {
			select {
			case <-s.ctx.Done():
				logger.Info("Historical data sync stopped")
				return
			case <-ticker.C:
				for _, symbol := range s.symbols {
					for _, intv := range intervals {
						if err := s.SyncOnce(s.ctx, symbol, intv); err != nil {
							logger.Error("SyncOnce failed", "symbol", symbol, "interval", intv, "error", err)
						}
					}
				}
			}
		}
	}()
}

// StopSync cancels the service context, stopping the background sync goroutine.
func (s *HistoricalDataService) StopSync() {
	s.cancel()
}

// SyncOnce fetches the most recent klines from Binance for the given symbol and
// interval, then upserts them into the database. It determines the start time
// based on the latest record already in the DB to avoid re-fetching old data.
func (s *HistoricalDataService) SyncOnce(ctx context.Context, symbol, interval string) error {
	// Determine the start time from the latest stored kline
	startTime, err := s.getLatestTime(ctx, symbol, interval)
	if err != nil {
		logger.Warn("Could not get latest time from DB, fetching last 100 klines", "symbol", symbol, "interval", interval, "error", err)
		// Fall back: fetch the most recent 100 klines
		startTime = time.Now().Add(-100 * intervalDuration(interval))
	}

	klines, err := s.FetchFromBinance(ctx, symbol, interval, startTime, time.Now(), 1000)
	if err != nil {
		return fmt.Errorf("fetch from Binance: %w", err)
	}

	if len(klines) == 0 {
		return nil
	}

	if err := s.upsertKlines(ctx, klines); err != nil {
		return fmt.Errorf("upsert klines: %w", err)
	}

	logger.Info("Synced klines", "symbol", symbol, "interval", interval, "count", len(klines))
	return nil
}

// intervalDuration returns an approximate time.Duration for a Binance interval string.
func intervalDuration(interval string) time.Duration {
	if len(interval) < 2 {
		return 1 * time.Hour
	}
	unit := interval[len(interval)-1:]
	numStr := interval[:len(interval)-1]
	num, err := strconv.Atoi(numStr)
	if err != nil {
		num = 1
	}
	switch unit {
	case "m":
		return time.Duration(num) * time.Minute
	case "h":
		return time.Duration(num) * time.Hour
	case "d":
		return time.Duration(num) * 24 * time.Hour
	case "w":
		return time.Duration(num) * 7 * 24 * time.Hour
	default:
		return 1 * time.Hour
	}
}

// FetchFromBinance retrieves klines from the Binance public REST API.
// No authentication is required. Returns parsed []model.Kline.
func (s *HistoricalDataService) FetchFromBinance(ctx context.Context, symbol, interval string, startTime, endTime time.Time, limit int) ([]model.Kline, error) {
	url := fmt.Sprintf(
		"%s/api/v3/klines?symbol=%s&interval=%s&limit=%d&startTime=%d&endTime=%d",
		s.baseURL,
		symbol,
		interval,
		limit,
		startTime.UnixMilli(),
		endTime.UnixMilli(),
	)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("http request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("binance API returned status %d", resp.StatusCode)
	}

	var rawKlines []binanceKlineRaw
	if err := json.NewDecoder(resp.Body).Decode(&rawKlines); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	klines := make([]model.Kline, 0, len(rawKlines))
	for _, raw := range rawKlines {
		k, err := parseBinanceKline(raw, symbol, interval)
		if err != nil {
			logger.Warn("Failed to parse kline", "symbol", symbol, "interval", interval, "error", err)
			continue
		}
		klines = append(klines, k)
	}

	return klines, nil
}

// parseBinanceKline converts a Binance raw JSON array into a model.Kline.
// Binance returns: [openTime, open, high, low, close, volume, closeTime,
// quoteVolume, trades, ...]
func parseBinanceKline(raw binanceKlineRaw, symbol, interval string) (model.Kline, error) {
	if len(raw) < 11 {
		return model.Kline{}, fmt.Errorf("unexpected kline length: %d", len(raw))
	}

	openTime, ok := raw[0].(float64)
	if !ok {
		return model.Kline{}, fmt.Errorf("invalid open_time type")
	}

	parseFloat := func(v any) (float64, error) {
		switch val := v.(type) {
		case float64:
			return val, nil
		case string:
			return strconv.ParseFloat(val, 64)
		default:
			return 0, fmt.Errorf("unexpected type for float value")
		}
	}

	parseInt := func(v any) (int, error) {
		switch val := v.(type) {
		case float64:
			return int(val), nil
		case string:
			n, err := strconv.Atoi(val)
			return n, err
		default:
			return 0, fmt.Errorf("unexpected type for int value")
		}
	}

	open, _ := parseFloat(raw[1])
	high, _ := parseFloat(raw[2])
	low, _ := parseFloat(raw[3])
	close, _ := parseFloat(raw[4])
	volume, _ := parseFloat(raw[5])

	closeTimeMs, _ := raw[6].(float64)
	quoteVolume, _ := parseFloat(raw[7])
	trades, _ := parseInt(raw[8])

	return model.Kline{
		Time:         time.UnixMilli(int64(openTime)),
		Symbol:       symbol,
		IntervalType: interval,
		Open:         open,
		High:         high,
		Low:          low,
		Close:        close,
		Volume:       volume,
		CloseTime:    time.UnixMilli(int64(closeTimeMs)),
		QuoteVolume:  quoteVolume,
		Trades:       trades,
	}, nil
}

// upsertKlines bulk-inserts klines into the database, using ON CONFLICT to
// update existing records.
func (s *HistoricalDataService) upsertKlines(ctx context.Context, klines []model.Kline) error {
	if len(klines) == 0 {
		return nil
	}

	query := `
		INSERT INTO klines (time, symbol, interval_type, open, high, low, close, volume, close_time, quote_volume, trades)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
		ON CONFLICT (time, symbol, interval_type) DO UPDATE SET
			open = EXCLUDED.open,
			high = EXCLUDED.high,
			low = EXCLUDED.low,
			close = EXCLUDED.close,
			volume = EXCLUDED.volume,
			close_time = EXCLUDED.close_time,
			quote_volume = EXCLUDED.quote_volume,
			trades = EXCLUDED.trades
	`

	batch := &pgx.Batch{}
	for _, k := range klines {
		batch.Queue(query,
			k.Time, k.Symbol, k.IntervalType,
			k.Open, k.High, k.Low, k.Close, k.Volume,
			k.CloseTime, k.QuoteVolume, k.Trades,
		)
	}

	// Use a connection from the pool for batch execution
	conn, err := s.pool.Acquire(ctx)
	if err != nil {
		return fmt.Errorf("acquire connection: %w", err)
	}
	defer conn.Release()

	br := conn.SendBatch(ctx, batch)
	defer br.Close()

	for range klines {
		if _, err := br.Exec(); err != nil {
			return fmt.Errorf("batch exec: %w", err)
		}
	}

	return nil
}

// GetKlines queries the database for klines matching the given criteria.
// Set startTime/endTime to zero-value to omit those filters.
func (s *HistoricalDataService) GetKlines(ctx context.Context, symbol, interval string, startTime, endTime time.Time, limit int) ([]model.Kline, error) {
	if limit <= 0 {
		limit = 100
	}
	if limit > 5000 {
		limit = 5000
	}

	query := `
		SELECT time, symbol, interval_type, open, high, low, close, volume, close_time, quote_volume, trades
		FROM klines
		WHERE symbol = $1 AND interval_type = $2
	`
	args := []any{symbol, interval}
	argCount := 2

	if !startTime.IsZero() {
		argCount++
		query += fmt.Sprintf(" AND time >= $%d", argCount)
		args = append(args, startTime)
	}
	if !endTime.IsZero() {
		argCount++
		query += fmt.Sprintf(" AND time <= $%d", argCount)
		args = append(args, endTime)
	}

	query += fmt.Sprintf(" ORDER BY time DESC LIMIT $%d", argCount+1)
	args = append(args, limit)

	rows, err := s.pool.Query(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("query klines: %w", err)
	}
	defer rows.Close()

	var klines []model.Kline
	for rows.Next() {
		var k model.Kline
		if err := rows.Scan(
			&k.Time, &k.Symbol, &k.IntervalType,
			&k.Open, &k.High, &k.Low, &k.Close, &k.Volume,
			&k.CloseTime, &k.QuoteVolume, &k.Trades,
		); err != nil {
			return nil, fmt.Errorf("scan kline: %w", err)
		}
		klines = append(klines, k)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration error: %w", err)
	}

	return klines, nil
}

// GetLatestPrice returns the most recent close price for a symbol across all
// stored intervals. Returns an error if no data exists.
func (s *HistoricalDataService) GetLatestPrice(ctx context.Context, symbol string) (float64, error) {
	query := `
		SELECT close FROM klines
		WHERE symbol = $1
		ORDER BY time DESC
		LIMIT 1
	`

	var price float64
	if err := s.pool.QueryRow(ctx, query, symbol).Scan(&price); err != nil {
		return 0, fmt.Errorf("get latest price for %s: %w", symbol, err)
	}

	return price, nil
}

// getLatestTime returns the most recent kline time for a given symbol and interval.
func (s *HistoricalDataService) getLatestTime(ctx context.Context, symbol, interval string) (time.Time, error) {
	query := `
		SELECT MAX(time) FROM klines
		WHERE symbol = $1 AND interval_type = $2
	`

	var t time.Time
	err := s.pool.QueryRow(ctx, query, symbol, interval).Scan(&t)
	if err != nil {
		return time.Time{}, err
	}
	return t, nil
}
