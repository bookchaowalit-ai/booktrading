package redis

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/port/output"
)

// RedisAdapter implements the RedisPublisher interface
type RedisAdapter struct {
	client *redis.Client
}

// NewRedisAdapter creates a new Redis adapter
func NewRedisAdapter(host, port, password string, db int) *RedisAdapter {
	client := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%s", host, port),
		Password: password,
		DB:       db,
	})
	return &RedisAdapter{
		client: client,
	}
}

// PublishMarketData publishes market data to Redis channel
func (r *RedisAdapter) PublishMarketData(ctx context.Context, data *model.MarketData) error {
	jsonData, err := json.Marshal(data)
	if err != nil {
		return fmt.Errorf("failed to marshal market data: %w", err)
	}

	channel := fmt.Sprintf("market_data:%s", data.Symbol)
	err = r.client.Publish(ctx, channel, jsonData).Err()
	if err != nil {
		return fmt.Errorf("failed to publish market data: %w", err)
	}

	// Also publish to general market_data channel for all subscribers
	err = r.client.Publish(ctx, "market_data", jsonData).Err()
	if err != nil {
		return fmt.Errorf("failed to publish to general market data channel: %w", err)
	}

	return nil
}

// Publish publishes market data to Redis channel (alias for PublishMarketData)
func (r *RedisAdapter) Publish(ctx context.Context, data *model.MarketData) error {
	return r.PublishMarketData(ctx, data)
}

// PublishOrderSignal publishes a trading signal to Redis channel
func (r *RedisAdapter) PublishOrderSignal(ctx context.Context, signal *output.OrderSignal) error {
	jsonData, err := json.Marshal(signal)
	if err != nil {
		return fmt.Errorf("failed to marshal order signal: %w", err)
	}

	channel := "order_signals"
	err = r.client.Publish(ctx, channel, jsonData).Err()
	if err != nil {
		return fmt.Errorf("failed to publish order signal: %w", err)
	}

	return nil
}

// SubscribeOrderSignals subscribes to order signals from Redis channel
func (r *RedisAdapter) SubscribeOrderSignals(ctx context.Context) (<-chan *output.OrderSignal, error) {
	pubsub := r.client.Subscribe(ctx, "order_signals")

	// Subscribe to channel
	_, err := pubsub.Receive(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to subscribe: %w", err)
	}

	signalChan := make(chan *output.OrderSignal)

	go func() {
		defer close(signalChan)
		defer pubsub.Close()

		for {
			select {
			case <-ctx.Done():
				return
			default:
				msg, err := pubsub.ReceiveMessage(ctx)
				if err != nil {
					if ctx.Err() != nil {
						return
					}
					continue
				}

				var signal output.OrderSignal
				if err := json.Unmarshal([]byte(msg.Payload), &signal); err != nil {
					continue
				}

				select {
				case signalChan <- &signal:
				case <-ctx.Done():
					return
				}
			}
		}
	}()

	return signalChan, nil
}

// GetClient returns the underlying Redis client for other operations
func (r *RedisAdapter) GetClient() *redis.Client {
	return r.client
}

// HealthCheck checks Redis connection
func (r *RedisAdapter) HealthCheck(ctx context.Context) error {
	_, err := r.client.Ping(ctx).Result()
	return err
}

// Close closes the Redis connection
func (r *RedisAdapter) Close() error {
	return r.client.Close()
}

// MarketDataCacheAdapter implements caching for market data
type MarketDataCacheAdapter struct {
	client *redis.Client
	ttl    time.Duration
}

// NewMarketDataCacheAdapter creates a new market data cache adapter
func NewMarketDataCacheAdapter(client *redis.Client, ttl time.Duration) *MarketDataCacheAdapter {
	return &MarketDataCacheAdapter{
		client: client,
		ttl:    ttl,
	}
}

// GetLatest retrieves the latest market data from cache
func (m *MarketDataCacheAdapter) GetLatest(ctx context.Context, symbol model.TradeSymbol) (*model.MarketData, error) {
	key := fmt.Sprintf("market_data:latest:%s", symbol)
	data, err := m.client.Get(ctx, key).Bytes()
	if err != nil {
		if err == redis.Nil {
			return nil, nil
		}
		return nil, err
	}

	var marketData model.MarketData
	if err := json.Unmarshal(data, &marketData); err != nil {
		return nil, err
	}

	return &marketData, nil
}

// Save saves market data to cache
func (m *MarketDataCacheAdapter) Save(ctx context.Context, data *model.MarketData) error {
	key := fmt.Sprintf("market_data:latest:%s", data.Symbol)
	jsonData, err := json.Marshal(data)
	if err != nil {
		return err
	}

	return m.client.Set(ctx, key, jsonData, m.ttl).Err()
}

// GetPriceHistory retrieves price history from Redis sorted set
func (m *MarketDataCacheAdapter) GetPriceHistory(ctx context.Context, symbol model.TradeSymbol, duration time.Duration) ([]*model.MarketData, error) {
	key := fmt.Sprintf("market_data:history:%s", symbol)
	start := time.Now().Add(-duration).UnixMilli()
	end := time.Now().UnixMilli()

	data, err := m.client.ZRangeByScore(ctx, key, &redis.ZRangeBy{
		Min: fmt.Sprintf("%d", start),
		Max: fmt.Sprintf("%d", end),
	}).Result()
	if err != nil {
		return nil, err
	}

	var result []*model.MarketData
	for _, item := range data {
		var marketData model.MarketData
		if err := json.Unmarshal([]byte(item), &marketData); err != nil {
			continue
		}
		result = append(result, &marketData)
	}

	return result, nil
}

// SaveToHistory saves market data to history sorted set
func (m *MarketDataCacheAdapter) SaveToHistory(ctx context.Context, data *model.MarketData) error {
	key := fmt.Sprintf("market_data:history:%s", data.Symbol)
	jsonData, err := json.Marshal(data)
	if err != nil {
		return err
	}

	return m.client.ZAdd(ctx, key, redis.Z{
		Score:  float64(data.Timestamp.UnixMilli()),
		Member: string(jsonData),
	}).Err()
}
