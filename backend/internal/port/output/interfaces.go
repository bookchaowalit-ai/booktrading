package output

import (
	"context"

	"trading-bot-system/backend/internal/domain/model"
)

// MarketDataPublisher defines the interface for publishing market data
type MarketDataPublisher interface {
	Publish(ctx context.Context, data *model.MarketData) error
	PublishMarketData(ctx context.Context, data *model.MarketData) error
}

// OrderExecutor defines the interface for executing orders on external exchanges
type OrderExecutor interface {
	PlaceOrder(ctx context.Context, order *model.Order) (*model.Order, error)
	CancelOrder(ctx context.Context, orderID string, symbol model.TradeSymbol) error
	GetOrderStatus(ctx context.Context, orderID string, symbol model.TradeSymbol) (*model.Order, error)
}

// ExchangeDataStream defines the interface for streaming data from exchanges
type ExchangeDataStream interface {
	Connect(ctx context.Context) error
	Disconnect(ctx context.Context) error
	Subscribe(ctx context.Context, symbol model.TradeSymbol) error
	Unsubscribe(ctx context.Context, symbol model.TradeSymbol) error
	GetStreamChannel() <-chan *model.MarketData
}

// WebSocketBroadcaster defines the interface for broadcasting to WebSocket clients
type WebSocketBroadcaster interface {
	BroadcastMarketData(data *model.MarketData)
	BroadcastBotStatus(status *model.BotStatus)
	BroadcastOrderUpdate(order *model.Order)
	BroadcastTradeNotification(trade *model.TradeNotification)
	BroadcastBotActivity(activity *model.BotActivity)
	RegisterClient(ch chan []byte)
	UnregisterClient(ch chan []byte)
}

// RedisPublisher defines the interface for Redis pub/sub operations
type RedisPublisher interface {
	PublishMarketData(ctx context.Context, data *model.MarketData) error
	PublishOrderSignal(ctx context.Context, signal *OrderSignal) error
	SubscribeOrderSignals(ctx context.Context) (<-chan *OrderSignal, error)
}

// OrderSignal represents a trading signal from strategy service
type OrderSignal struct {
	Symbol   model.TradeSymbol `json:"symbol"`
	Side     model.OrderSide   `json:"side"`
	Strength float64           `json:"strength"` // 0.0 to 1.0
	Reason   string            `json:"reason"`
}
