package service

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/logger"
)

// BinanceKline represents a single candlestick from Binance
type BinanceKline struct {
	OpenTime   int64   `json:"open_time"`
	Open       float64 `json:"open"`
	High       float64 `json:"high"`
	Low        float64 `json:"low"`
	Close      float64 `json:"close"`
	Volume     float64 `json:"volume"`
	CloseTime  int64   `json:"close_time"`
	QuoteVolume float64 `json:"quote_volume"`
	Trades     int     `json:"trades"`
}

// BacktestResult holds the results of a backtest simulation
type BacktestResult struct {
	InitialCapital  float64   `json:"initial_capital"`
	FinalCapital    float64   `json:"final_capital"`
	TotalReturn     float64   `json:"total_return"`
	TotalReturnPct  float64   `json:"total_return_percent"`
	TotalTrades     int       `json:"total_trades"`
	WinTrades       int       `json:"win_trades"`
	LossTrades      int       `json:"loss_trades"`
	WinRate         float64   `json:"win_rate"`
	ProfitFactor    float64   `json:"profit_factor"`
	MaxDrawdown     float64   `json:"max_drawdown"`
	MaxDrawdownPct  float64   `json:"max_drawdown_percent"`
	SharpeRatio     float64   `json:"sharpe_ratio"`
	SortinoRatio    float64   `json:"sortino_ratio"`
	AvgWin          float64   `json:"avg_win"`
	AvgLoss         float64   `json:"avg_loss"`
	BestTrade       float64   `json:"best_trade"`
	WorstTrade      float64   `json:"worst_trade"`
	AvgTradeDuration string   `json:"avg_trade_duration"`
	Trades          []TradeResult `json:"trades"`
	EquityCurve     []EquityPoint `json:"equity_curve"`
}

// TradeResult represents a single completed trade in backtest
type TradeResult struct {
	Symbol     string    `json:"symbol"`
	Side       string    `json:"side"`
	EntryPrice float64   `json:"entry_price"`
	ExitPrice  float64   `json:"exit_price"`
	Quantity   float64   `json:"quantity"`
	PnL        float64   `json:"pnl"`
	PnLPct     float64   `json:"pnl_percent"`
	EntryTime  time.Time `json:"entry_time"`
	ExitTime   time.Time `json:"exit_time"`
	Duration   string    `json:"duration"`
}

// EquityPoint represents a point on the equity curve
type EquityPoint struct {
	Time   time.Time `json:"time"`
	Value  float64   `json:"value"`
}

// BacktestConfig holds parameters for running a backtest
type BacktestConfig struct {
	Symbol          string    `json:"symbol"`
	StartDate       time.Time `json:"start_date"`
	EndDate         time.Time `json:"end_date"`
	InitialCapital  float64   `json:"initial_capital"`
	Commission      float64   `json:"commission"`      // e.g. 0.001 = 0.1%
	Slippage        float64   `json:"slippage"`        // e.g. 0.0005 = 0.05%
	RiskConfig      *model.RiskConfig `json:"risk_config,omitempty"`
	Strategy        string    `json:"strategy"`        // "rsi", "ema_cross", "macd"
	RSIPeriod       int       `json:"rsi_period"`
	RSIOversold     float64   `json:"rsi_oversold"`
	RSIOverbought   float64   `json:"rsi_overbought"`
	EMAFastPeriod   int       `json:"ema_fast_period"`
	EMASlowPeriod   int       `json:"ema_slow_period"`
}

// BacktestService runs backtests using real historical data
type BacktestService struct {
	binanceBaseURL string
	httpClient     *http.Client
}

// NewBacktestService creates a new backtest service
func NewBacktestService() *BacktestService {
	return &BacktestService{
		binanceBaseURL: "https://api.binance.com",
		httpClient:     &http.Client{Timeout: 30 * time.Second},
	}
}

// FetchHistoricalKlines fetches historical candlestick data from Binance
func (s *BacktestService) FetchHistoricalKlines(ctx context.Context, symbol string, interval string, startTime, endTime time.Time) ([]BinanceKline, error) {
	// Binance klines endpoint
	url := fmt.Sprintf("%s/api/v3/klines?symbol=%s&interval=%s&limit=1000",
		s.binanceBaseURL, symbol, interval)

	if !startTime.IsZero() {
		url += fmt.Sprintf("&startTime=%d", startTime.UnixMilli())
	}
	if !endTime.IsZero() {
		url += fmt.Sprintf("&endTime=%d", endTime.UnixMilli())
	}

	logger.Info("Fetching historical klines", "url", url, "symbol", symbol)

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch klines: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("binance API returned %d: %s", resp.StatusCode, string(body))
	}

	// Binance returns array of arrays: [open_time, open, high, low, close, volume, ...]
	var raw [][]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&raw); err != nil {
		return nil, fmt.Errorf("failed to decode klines: %w", err)
	}

	klines := make([]BinanceKline, 0, len(raw))
	for _, k := range raw {
		if len(k) < 11 {
			continue
		}

		kline := BinanceKline{
			OpenTime:   toInt64(k[0]),
			Open:       toFloat64(k[1]),
			High:       toFloat64(k[2]),
			Low:        toFloat64(k[3]),
			Close:      toFloat64(k[4]),
			Volume:     toFloat64(k[5]),
			CloseTime:  toInt64(k[6]),
			QuoteVolume: toFloat64(k[7]),
			Trades:     int(toInt64(k[8])),
		}
		klines = append(klines, kline)
	}

	logger.Info("Fetched klines", "count", len(klines), "symbol", symbol)
	return klines, nil
}

// RunBacktest runs a backtest simulation on historical data
func (s *BacktestService) RunBacktest(ctx context.Context, config BacktestConfig) (*BacktestResult, error) {
	logger.Info("Starting backtest",
		"symbol", config.Symbol,
		"start", config.StartDate.Format("2006-01-02"),
		"end", config.EndDate.Format("2006-01-02"),
		"strategy", config.Strategy,
	)

	// Fetch historical data
	klines, err := s.FetchHistoricalKlines(ctx, config.Symbol, "1d", config.StartDate, config.EndDate)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch historical data: %w", err)
	}

	if len(klines) < 50 {
		return nil, fmt.Errorf("not enough data for backtest: got %d klines, need at least 50", len(klines))
	}

	// Initialize risk manager
	riskMgr := NewRiskManager(config.RiskConfig, config.InitialCapital)

	// Run backtest
	result := &BacktestResult{
		InitialCapital: config.InitialCapital,
		Trades:         make([]TradeResult, 0),
		EquityCurve:    make([]EquityPoint, 0),
	}

	// Extract close prices for indicator calculation
	closes := make([]float64, len(klines))
	for i, k := range klines {
		closes[i] = k.Close
	}

	// Backtest engine state
	capital := config.InitialCapital
	position := 0.0        // Quantity held
	entryPrice := 0.0
	entryTime := time.Time{}
	peakCapital := capital
	var tradeResults []float64

	for i := 20; i < len(klines); i++ { // Need warmup for indicators
		currentPrice := klines[i].Close
		currentTime := time.UnixMilli(klines[i].OpenTime)

		// Calculate indicators
		var shouldBuy, shouldSell bool

		switch config.Strategy {
		case "rsi":
			rsi := calculateRSI(closes[:i+1], config.RSIPeriod)
			shouldBuy = rsi < config.RSIOversold
			shouldSell = rsi > config.RSIOverbought
		case "ema_cross":
			emaFast := calculateEMA(closes[:i+1], config.EMAFastPeriod)
			emaSlow := calculateEMA(closes[:i+1], config.EMASlowPeriod)
			shouldBuy = emaFast > emaSlow
			shouldSell = emaFast < emaSlow
		default:
			// Default: RSI strategy
			rsi := calculateRSI(closes[:i+1], config.RSIPeriod)
			shouldBuy = rsi < config.RSIOversold
			shouldSell = rsi > config.RSIOverbought
		}

		// Risk check before entering
		if position == 0 && shouldBuy {
			blocked := riskMgr.CheckTradeApproval(config.Symbol, model.SideBuy, 1, currentPrice, capital)
			if len(blocked) == 0 {
				// Enter position
				slippagePrice := currentPrice * (1 + config.Slippage)
				position = capital / slippagePrice
				entryPrice = slippagePrice
				entryTime = currentTime
				capital = 0
			}
		}

		// Exit position
		if position > 0 && shouldSell {
			exitPrice := currentPrice * (1 - config.Slippage)
			grossPnL := (exitPrice - entryPrice) * position

			// Commission on both entry and exit
			commission := (entryPrice*position + exitPrice*position) * config.Commission
			netPnL := grossPnL - commission

			capital += position*exitPrice - commission
			duration := currentTime.Sub(entryTime)

			riskMgr.RecordTrade(netPnL, false, false)

			tradeResults = append(tradeResults, netPnL)

			result.Trades = append(result.Trades, TradeResult{
				Symbol:     config.Symbol,
				Side:       "BUY",
				EntryPrice: entryPrice,
				ExitPrice:  exitPrice,
				Quantity:   position,
				PnL:        netPnL,
				PnLPct:     (netPnL / (entryPrice * position)) * 100,
				EntryTime:  entryTime,
				ExitTime:   currentTime,
				Duration:   duration.String(),
			})

			position = 0
			entryPrice = 0
			entryTime = time.Time{}
		}

		// Track peak capital and drawdown
		totalValue := capital + position*currentPrice
		if totalValue > peakCapital {
			peakCapital = totalValue
		}

		// Equity curve point
		result.EquityCurve = append(result.EquityCurve, EquityPoint{
			Time:  currentTime,
			Value: totalValue,
		})
	}

	// Close any remaining position at last price
	if position > 0 && len(klines) > 0 {
		lastPrice := klines[len(klines)-1].Close
		exitPrice := lastPrice * (1 - config.Slippage)
		netPnL := (exitPrice - entryPrice)*position - (entryPrice*position+exitPrice*position)*config.Commission
		capital += position*exitPrice - (entryPrice*position+exitPrice*position)*config.Commission

		tradeResults = append(tradeResults, netPnL)
	}

	// Calculate final metrics
	result.FinalCapital = capital
	result.TotalReturn = capital - config.InitialCapital
	if config.InitialCapital > 0 {
		result.TotalReturnPct = (result.TotalReturn / config.InitialCapital) * 100
	}

	// Win/loss stats
	wins := make([]float64, 0)
	losses := make([]float64, 0)
	for _, pnl := range tradeResults {
		if pnl > 0 {
			wins = append(wins, pnl)
		} else {
			losses = append(losses, pnl)
		}
	}

	result.TotalTrades = len(tradeResults)
	result.WinTrades = len(wins)
	result.LossTrades = len(losses)

	if result.TotalTrades > 0 {
		result.WinRate = float64(result.WinTrades) / float64(result.TotalTrades) * 100
	}

	grossProfit := sumFloats(wins)
	grossLoss := absSumFloats(losses)
	if grossLoss > 0 {
		result.ProfitFactor = grossProfit / grossLoss
	} else if grossProfit > 0 {
		result.ProfitFactor = grossProfit
	}

	if len(wins) > 0 {
		result.AvgWin = grossProfit / float64(len(wins))
		result.BestTrade = maxFloat(wins)
	}
	if len(losses) > 0 {
		result.AvgLoss = grossLoss / float64(len(losses))
		result.WorstTrade = minFloat(losses)
	}

	// Max drawdown
	maxDD := 0.0
	peak := config.InitialCapital
	for _, ep := range result.EquityCurve {
		if ep.Value > peak {
			peak = ep.Value
		}
		dd := (peak - ep.Value) / peak * 100
		if dd > maxDD {
			maxDD = dd
		}
	}
	result.MaxDrawdownPct = maxDD
	result.MaxDrawdown = peak * maxDD / 100

	// Sharpe ratio (annualized)
	if len(tradeResults) > 1 {
		mean := sumFloats(tradeResults) / float64(len(tradeResults))
		variance := 0.0
		for _, r := range tradeResults {
			variance += (r - mean) * (r - mean)
		}
		stdDev := sqrt(variance / float64(len(tradeResults)-1))
		if stdDev > 0 {
			result.SharpeRatio = (mean / stdDev) * sqrt(252)
		}

		// Sortino ratio
		negReturns := make([]float64, 0)
		for _, r := range tradeResults {
			if r < 0 {
				negReturns = append(negReturns, r)
			}
		}
		if len(negReturns) > 1 {
			downsideVar := 0.0
			for _, r := range negReturns {
				downsideVar += r * r
			}
			downsideDev := sqrt(downsideVar / float64(len(negReturns)))
			if downsideDev > 0 {
				result.SortinoRatio = (mean / downsideDev) * sqrt(252)
			}
		}
	}

	logger.Info("Backtest completed",
		"total_trades", result.TotalTrades,
		"win_rate", fmt.Sprintf("%.1f%%", result.WinRate),
		"total_return", fmt.Sprintf("%.2f%%", result.TotalReturnPct),
		"max_drawdown", fmt.Sprintf("%.2f%%", result.MaxDrawdownPct),
	)

	return result, nil
}

// ── Helper math functions ──

func sumFloats(s []float64) float64 {
	var sum float64
	for _, v := range s {
		sum += v
	}
	return sum
}

func absSumFloats(s []float64) float64 {
	var sum float64
	for _, v := range s {
		sum += -v
	}
	return sum
}

func maxFloat(s []float64) float64 {
	if len(s) == 0 {
		return 0
	}
	m := s[0]
	for _, v := range s[1:] {
		if v > m {
			m = v
		}
	}
	return m
}

func minFloat(s []float64) float64 {
	if len(s) == 0 {
		return 0
	}
	m := s[0]
	for _, v := range s[1:] {
		if v < m {
			m = v
		}
	}
	return m
}

func sqrt(x float64) float64 {
	if x <= 0 {
		return 0
	}
	z := x
	for i := 0; i < 10; i++ {
		z = (z + x/z) / 2
	}
	return z
}

// ── Technical indicator calculations ──

func calculateRSI(prices []float64, period int) float64 {
	if len(prices) < period+1 {
		return 50 // Neutral
	}

	gains := 0.0
	losses := 0.0

	for i := len(prices) - period; i < len(prices); i++ {
		change := prices[i] - prices[i-1]
		if change > 0 {
			gains += change
		} else {
			losses += -change
		}
	}

	avgGain := gains / float64(period)
	avgLoss := losses / float64(period)

	if avgLoss == 0 {
		return 100
	}

	rs := avgGain / avgLoss
	return 100 - (100 / (1 + rs))
}

func calculateEMA(prices []float64, period int) float64 {
	if len(prices) < period {
		return 0
	}

	// Start with SMA
	sma := 0.0
	for i := 0; i < period; i++ {
		sma += prices[i]
	}
	sma /= float64(period)

	multiplier := 2.0 / (float64(period) + 1)
	ema := sma

	for i := period; i < len(prices); i++ {
		ema = (prices[i]-ema)*multiplier + ema
	}

	return ema
}

func toInt64(v interface{}) int64 {
	switch val := v.(type) {
	case float64:
		return int64(val)
	case int64:
		return val
	case string:
		var result int64
		fmt.Sscanf(val, "%d", &result)
		return result
	default:
		return 0
	}
}

func toFloat64(v interface{}) float64 {
	switch val := v.(type) {
	case float64:
		return val
	case int64:
		return float64(val)
	case int:
		return float64(val)
	case string:
		var result float64
		fmt.Sscanf(val, "%f", &result)
		return result
	default:
		return 0
	}
}
