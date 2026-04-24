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

// UnimplementedDexServiceServer for embedding
type UnimplementedDexServiceServer struct{}

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

// RegisterDexServiceServer stub
func RegisterDexServiceServer(s *grpc.Server, srv DexServiceServer) {
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

// DexServiceServer interface
type DexServiceServer interface {
	GetQuote(context.Context, *GetQuoteRequest) (*QuoteResponse, error)
	Swap(context.Context, *SwapRequest) (*SwapTxResponse, error)
	GetTokenInfo(context.Context, *TokenInfoRequest) (*TokenInfoResponse, error)
	GetBalance(context.Context, *BalanceRequest) (*BalanceResponse, error)
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

// GetQuoteRequest represents a DEX quote request
type GetQuoteRequest struct {
	TokenIn     string  `protobuf:"bytes,1,opt,name=token_in,json=tokenIn,proto3" json:"token_in,omitempty"`
	TokenOut    string  `protobuf:"bytes,2,opt,name=token_out,json=tokenOut,proto3" json:"token_out,omitempty"`
	AmountIn    string  `protobuf:"bytes,3,opt,name=amount_in,json=amountIn,proto3" json:"amount_in,omitempty"`
	SlippagePct float64 `protobuf:"fixed64,4,opt,name=slippage_pct,json=slippagePct,proto3" json:"slippage_pct,omitempty"`
	BestRoute   bool    `protobuf:"varint,5,opt,name=best_route,json=bestRoute,proto3" json:"best_route,omitempty"`
}

// QuoteResponse represents a DEX quote response
type QuoteResponse struct {
	TokenInAddress  string   `protobuf:"bytes,1,opt,name=token_in_address,json=tokenInAddress,proto3" json:"token_in_address,omitempty"`
	TokenOutAddress string   `protobuf:"bytes,2,opt,name=token_out_address,json=tokenOutAddress,proto3" json:"token_out_address,omitempty"`
	TokenInSymbol   string   `protobuf:"bytes,3,opt,name=token_in_symbol,json=tokenInSymbol,proto3" json:"token_in_symbol,omitempty"`
	TokenOutSymbol  string   `protobuf:"bytes,4,opt,name=token_out_symbol,json=tokenOutSymbol,proto3" json:"token_out_symbol,omitempty"`
	AmountIn        string   `protobuf:"bytes,5,opt,name=amount_in,json=amountIn,proto3" json:"amount_in,omitempty"`
	AmountOut       string   `protobuf:"bytes,6,opt,name=amount_out,json=amountOut,proto3" json:"amount_out,omitempty"`
	AmountOutMin    string   `protobuf:"bytes,7,opt,name=amount_out_min,json=amountOutMin,proto3" json:"amount_out_min,omitempty"`
	PriceImpact     float64  `protobuf:"fixed64,8,opt,name=price_impact,json=priceImpact,proto3" json:"price_impact,omitempty"`
	MinimumReceived string   `protobuf:"bytes,9,opt,name=minimum_received,json=minimumReceived,proto3" json:"minimum_received,omitempty"`
	GasEstimate     uint64   `protobuf:"varint,10,opt,name=gas_estimate,json=gasEstimate,proto3" json:"gas_estimate,omitempty"`
	Route           []string `protobuf:"bytes,11,rep,name=route,proto3" json:"route,omitempty"`
	DexProvider     string   `protobuf:"bytes,12,opt,name=dex_provider,json=dexProvider,proto3" json:"dex_provider,omitempty"`
	Error           string   `protobuf:"bytes,13,opt,name=error,proto3" json:"error,omitempty"`
}

// SwapRequest represents a DEX swap request
type SwapRequest struct {
	TokenInAddress  string  `protobuf:"bytes,1,opt,name=token_in_address,json=tokenInAddress,proto3" json:"token_in_address,omitempty"`
	TokenOutAddress string  `protobuf:"bytes,2,opt,name=token_out_address,json=tokenOutAddress,proto3" json:"token_out_address,omitempty"`
	AmountIn        string  `protobuf:"bytes,3,opt,name=amount_in,json=amountIn,proto3" json:"amount_in,omitempty"`
	AmountOutMin    string  `protobuf:"bytes,4,opt,name=amount_out_min,json=amountOutMin,proto3" json:"amount_out_min,omitempty"`
	Recipient       string  `protobuf:"bytes,5,opt,name=recipient,proto3" json:"recipient,omitempty"`
	SlippagePct     float64 `protobuf:"fixed64,6,opt,name=slippage_pct,json=slippagePct,proto3" json:"slippage_pct,omitempty"`
	Deadline        string  `protobuf:"bytes,7,opt,name=deadline,proto3" json:"deadline,omitempty"`
}

// SwapTxResponse represents a DEX swap transaction response
type SwapTxResponse struct {
	TxHash      string `protobuf:"bytes,1,opt,name=tx_hash,json=txHash,proto3" json:"tx_hash,omitempty"`
	BlockNumber uint64 `protobuf:"varint,2,opt,name=block_number,json=blockNumber,proto3" json:"block_number,omitempty"`
	GasUsed     uint64 `protobuf:"varint,3,opt,name=gas_used,json=gasUsed,proto3" json:"gas_used,omitempty"`
	GasPrice    string `protobuf:"bytes,4,opt,name=gas_price,json=gasPrice,proto3" json:"gas_price,omitempty"`
	AmountIn    string `protobuf:"bytes,5,opt,name=amount_in,json=amountIn,proto3" json:"amount_in,omitempty"`
	AmountOut   string `protobuf:"bytes,6,opt,name=amount_out,json=amountOut,proto3" json:"amount_out,omitempty"`
	Status      string `protobuf:"bytes,7,opt,name=status,proto3" json:"status,omitempty"`
	Error       string `protobuf:"bytes,8,opt,name=error,proto3" json:"error,omitempty"`
}

// TokenInfoRequest represents a token info request
type TokenInfoRequest struct {
	TokenAddress string `protobuf:"bytes,1,opt,name=token_address,json=tokenAddress,proto3" json:"token_address,omitempty"`
}

// TokenInfoResponse represents a token info response
type TokenInfoResponse struct {
	Address  string `protobuf:"bytes,1,opt,name=address,proto3" json:"address,omitempty"`
	Symbol   string `protobuf:"bytes,2,opt,name=symbol,proto3" json:"symbol,omitempty"`
	Name     string `protobuf:"bytes,3,opt,name=name,proto3" json:"name,omitempty"`
	Decimals uint32 `protobuf:"varint,4,opt,name=decimals,proto3" json:"decimals,omitempty"`
	LogoUri  string `protobuf:"bytes,5,opt,name=logo_uri,json=logoUri,proto3" json:"logo_uri,omitempty"`
	Error    string `protobuf:"bytes,6,opt,name=error,proto3" json:"error,omitempty"`
}

// BalanceRequest represents a balance request
type BalanceRequest struct {
	TokenAddress string `protobuf:"bytes,1,opt,name=token_address,json=tokenAddress,proto3" json:"token_address,omitempty"`
	UserAddress  string `protobuf:"bytes,2,opt,name=user_address,json=userAddress,proto3" json:"user_address,omitempty"`
}

// BalanceResponse represents a balance response
type BalanceResponse struct {
	Balance string `protobuf:"bytes,1,opt,name=balance,proto3" json:"balance,omitempty"`
	Error   string `protobuf:"bytes,2,opt,name=error,proto3" json:"error,omitempty"`
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

// DexServiceClient is the client interface for DEX operations
type DexServiceClient interface {
	GetQuote(ctx context.Context, req *GetQuoteRequest, opts ...grpc.CallOption) (*QuoteResponse, error)
	Swap(ctx context.Context, req *SwapRequest, opts ...grpc.CallOption) (*SwapTxResponse, error)
	GetTokenInfo(ctx context.Context, req *TokenInfoRequest, opts ...grpc.CallOption) (*TokenInfoResponse, error)
	GetBalance(ctx context.Context, req *BalanceRequest, opts ...grpc.CallOption) (*BalanceResponse, error)
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
