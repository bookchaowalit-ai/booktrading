// Package pb contains generated protobuf types.
// In production, generate with: protoc --go_out=. --go_opt=paths=source_relative --go-grpc_out=. --go-grpc_opt=paths=source_relative proto/trading.proto

package pb

import (
	"context"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// UnimplementedOrderExecutionServiceServer for embedding
type UnimplementedOrderExecutionServiceServer struct{}

// UnimplementedBotStatusServiceServer for embedding
type UnimplementedBotStatusServiceServer struct{}

// UnimplementedMarketDataServiceServer for embedding
type UnimplementedMarketDataServiceServer struct{}

// MarketDataService_SubscribeMarketDataServer interface
type MarketDataService_SubscribeMarketDataServer interface {
	Send(*MarketData) error
	grpc.ServerStream
}

// RegisterOrderExecutionServiceServer stub
func RegisterOrderExecutionServiceServer(s *grpc.Server, srv OrderExecutionServiceServer) {
	// Stub implementation - in production use protoc generated code
}

// RegisterBotStatusServiceServer stub
func RegisterBotStatusServiceServer(s *grpc.Server, srv BotStatusServiceServer) {
	// Stub implementation
}

// RegisterMarketDataServiceServer stub
func RegisterMarketDataServiceServer(s *grpc.Server, srv MarketDataServiceServer) {
	// Stub implementation
}

// OrderExecutionServiceServer interface
type OrderExecutionServiceServer interface {
	ExecuteOrder(context.Context, *OrderRequest) (*OrderResponse, error)
	CancelOrder(context.Context, *CancelOrderRequest) (*CancelOrderResponse, error)
}

// BotStatusServiceServer interface
type BotStatusServiceServer interface {
	GetBotStatus(context.Context, *GetBotStatusRequest) (*BotStatusResponse, error)
	StartBot(context.Context, *StartBotRequest) (*StartBotResponse, error)
	StopBot(context.Context, *StopBotRequest) (*StopBotResponse, error)
}

// MarketDataServiceServer interface
type MarketDataServiceServer interface {
	SubscribeMarketData(*SubscribeRequest, MarketDataService_SubscribeMarketDataServer) error
}

// MarketData represents market data message
type MarketData struct {
	Symbol    string  `protobuf:"bytes,1,opt,name=symbol,proto3" json:"symbol,omitempty"`
	Price     float64 `protobuf:"fixed64,2,opt,name=price,proto3" json:"price,omitempty"`
	Volume    float64 `protobuf:"fixed64,3,opt,name=volume,proto3" json:"volume,omitempty"`
	Timestamp int64   `protobuf:"varint,4,opt,name=timestamp,proto3" json:"timestamp,omitempty"`
}

// OrderRequest represents an order execution request
type OrderRequest struct {
	Id       string  `protobuf:"bytes,1,opt,name=id,proto3" json:"id,omitempty"`
	Symbol   string  `protobuf:"bytes,2,opt,name=symbol,proto3" json:"symbol,omitempty"`
	Side     string  `protobuf:"bytes,3,opt,name=side,proto3" json:"side,omitempty"`
	Type     string  `protobuf:"bytes,4,opt,name=type,proto3" json:"type,omitempty"`
	Quantity float64 `protobuf:"fixed64,5,opt,name=quantity,proto3" json:"quantity,omitempty"`
	Price    float64 `protobuf:"fixed64,6,opt,name=price,proto3" json:"price,omitempty"`
}

// OrderResponse represents an order execution response
type OrderResponse struct {
	OrderId   string  `protobuf:"bytes,1,opt,name=order_id,json=orderId,proto3" json:"order_id,omitempty"`
	Symbol    string  `protobuf:"bytes,2,opt,name=symbol,proto3" json:"symbol,omitempty"`
	Side      string  `protobuf:"bytes,3,opt,name=side,proto3" json:"side,omitempty"`
	Status    string  `protobuf:"bytes,4,opt,name=status,proto3" json:"status,omitempty"`
	Quantity  float64 `protobuf:"fixed64,5,opt,name=quantity,proto3" json:"quantity,omitempty"`
	Price     float64 `protobuf:"fixed64,6,opt,name=price,proto3" json:"price,omitempty"`
	CreatedAt int64   `protobuf:"varint,7,opt,name=created_at,json=createdAt,proto3" json:"created_at,omitempty"`
	Error     string  `protobuf:"bytes,8,opt,name=error,proto3" json:"error,omitempty"`
}

// CancelOrderRequest represents a cancel order request
type CancelOrderRequest struct {
	OrderId string `protobuf:"bytes,1,opt,name=order_id,json=orderId,proto3" json:"order_id,omitempty"`
	Symbol  string `protobuf:"bytes,2,opt,name=symbol,proto3" json:"symbol,omitempty"`
}

// CancelOrderResponse represents a cancel order response
type CancelOrderResponse struct {
	Success bool   `protobuf:"varint,1,opt,name=success,proto3" json:"success,omitempty"`
	Message string `protobuf:"bytes,2,opt,name=message,proto3" json:"message,omitempty"`
}

// BotStatusResponse represents bot status
type BotStatusResponse struct {
	IsActive    bool    `protobuf:"varint,1,opt,name=is_active,json=isActive,proto3" json:"is_active,omitempty"`
	StartedAt   int64   `protobuf:"varint,2,opt,name=started_at,json=startedAt,proto3" json:"started_at,omitempty"`
	StoppedAt   int64   `protobuf:"varint,3,opt,name=stopped_at,json=stoppedAt,proto3" json:"stopped_at,omitempty"`
	TotalTrades int32   `protobuf:"varint,4,opt,name=total_trades,json=totalTrades,proto3" json:"total_trades,omitempty"`
	TotalProfit float64 `protobuf:"fixed64,5,opt,name=total_profit,json=totalProfit,proto3" json:"total_profit,omitempty"`
}

// SubscribeRequest represents a subscription request
type SubscribeRequest struct {
	Symbols []string `protobuf:"bytes,1,rep,name=symbols,proto3" json:"symbols,omitempty"`
}

// GetBotStatusRequest represents a get bot status request
type GetBotStatusRequest struct{}

// StartBotRequest represents a start bot request
type StartBotRequest struct{}

// StartBotResponse represents a start bot response
type StartBotResponse struct {
	Success bool   `protobuf:"varint,1,opt,name=success,proto3" json:"success,omitempty"`
	Message string `protobuf:"bytes,2,opt,name=message,proto3" json:"message,omitempty"`
}

// StopBotRequest represents a stop bot request
type StopBotRequest struct{}

// StopBotResponse represents a stop bot response
type StopBotResponse struct {
	Success bool   `protobuf:"varint,1,opt,name=success,proto3" json:"success,omitempty"`
	Message string `protobuf:"bytes,2,opt,name=message,proto3" json:"message,omitempty"`
}

// Convert MarketData from domain model
func MarketDataFromDomain(symbol string, price, volume float64) *MarketData {
	return &MarketData{
		Symbol:    symbol,
		Price:     price,
		Volume:    volume,
		Timestamp: time.Now().UnixMilli(),
	}
}

// Convert OrderResponse from domain model
func OrderResponseFromDomain(orderID, symbol, side, status string, quantity, price float64) *OrderResponse {
	return &OrderResponse{
		OrderId:   orderID,
		Symbol:    symbol,
		Side:      side,
		Status:    status,
		Quantity:  quantity,
		Price:     price,
		CreatedAt: time.Now().UnixMilli(),
	}
}

// OrderExecutionServiceClient is the client interface for order execution
type OrderExecutionServiceClient interface {
	ExecuteOrder(ctx context.Context, req *OrderRequest, opts ...grpc.CallOption) (*OrderResponse, error)
	CancelOrder(ctx context.Context, req *CancelOrderRequest, opts ...grpc.CallOption) (*CancelOrderResponse, error)
}

// BotStatusServiceClient is the client interface for bot status
type BotStatusServiceClient interface {
	GetBotStatus(ctx context.Context, req *GetBotStatusRequest, opts ...grpc.CallOption) (*BotStatusResponse, error)
	StartBot(ctx context.Context, req *StartBotRequest, opts ...grpc.CallOption) (*StartBotResponse, error)
	StopBot(ctx context.Context, req *StopBotRequest, opts ...grpc.CallOption) (*StopBotResponse, error)
}

// MarketDataServiceClient is the client interface for market data
type MarketDataServiceClient interface {
	SubscribeMarketData(ctx context.Context, req *SubscribeRequest, opts ...grpc.CallOption) (MarketDataService_SubscribeMarketDataClient, error)
}

// MarketDataService_SubscribeMarketDataClient is the stream client interface
type MarketDataService_SubscribeMarketDataClient interface {
	Recv() (*MarketData, error)
	grpc.ClientStream
}

// Error helpers
func Errorf(codes codes.Code, format string, a ...interface{}) error {
	return status.Errorf(codes, format, a...)
}
