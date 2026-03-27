package input

import (
	"context"

	"trading-bot-system/backend/internal/domain/model"
)

// OrderHandler defines the interface for handling order-related requests
type OrderHandler interface {
	CreateOrder(ctx context.Context, req *model.OrderRequest) (*model.OrderResponse, error)
	CancelOrder(ctx context.Context, orderID string) error
	GetOrder(ctx context.Context, orderID string) (*model.Order, error)
	GetAllOrders(ctx context.Context) ([]*model.Order, error)
}

// MarketDataHandler defines the interface for handling market data requests
type MarketDataHandler interface {
	GetLatestPrice(ctx context.Context, symbol model.TradeSymbol) (*model.MarketData, error)
	GetPriceHistory(ctx context.Context, symbol model.TradeSymbol) ([]*model.MarketData, error)
	Subscribe(ctx context.Context, symbol model.TradeSymbol) (<-chan *model.MarketData, error)
	Unsubscribe(ctx context.Context, symbol model.TradeSymbol) error
	StartStreaming(ctx context.Context, symbol model.TradeSymbol) error
	StopStreaming(ctx context.Context, symbol model.TradeSymbol) error
	Shutdown()
}

// PortfolioHandler defines the interface for handling portfolio requests
type PortfolioHandler interface {
	GetPortfolio(ctx context.Context) ([]*model.Portfolio, error)
}

// BotHandler defines the interface for handling bot control requests
type BotHandler interface {
	Start(ctx context.Context) error
	Stop(ctx context.Context) error
	GetStatus(ctx context.Context) (*model.BotStatus, error)
}

// TradeHistoryHandler defines the interface for handling trade history requests
type TradeHistoryHandler interface {
	GetTradeHistory(ctx context.Context, limit int) ([]*model.TradeHistory, error)
	GetTradeHistoryBySymbol(ctx context.Context, symbol model.TradeSymbol, limit int) ([]*model.TradeHistory, error)
}
