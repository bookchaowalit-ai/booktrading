package grpcserver

import (
	"context"
	"math/big"
	"time"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"trading-bot-system/backend/internal/adapter/dex"
	"trading-bot-system/backend/internal/port/output/pb"
)

// dexGRPCServer implements the pb.DexServiceServer interface
type dexGRPCServer struct {
	pb.UnimplementedDexServiceServer
	dexManager *dex.DEXManager
}

// newDexGRPCServer creates a new DEX gRPC server
func newDexGRPCServer(dexManager *dex.DEXManager) *dexGRPCServer {
	return &dexGRPCServer{dexManager: dexManager}
}

// GetQuote returns a quote for a token swap
func (s *dexGRPCServer) GetQuote(ctx context.Context, req *pb.GetQuoteRequest) (*pb.QuoteResponse, error) {
	if !s.dexManager.IsEnabled() {
		return &pb.QuoteResponse{Error: "DEX trading is disabled"}, nil
	}

	amountIn, ok := new(big.Int).SetString(req.AmountIn, 10)
	if !ok {
		return &pb.QuoteResponse{Error: "invalid amount_in"}, status.Errorf(codes.InvalidArgument, "invalid amount_in: %s", req.AmountIn)
	}

	var quote *dex.Quote
	var err error

	if req.BestRoute {
		quote, err = s.dexManager.GetBestQuote(ctx, req.TokenIn, req.TokenOut, amountIn, req.SlippagePct)
	} else {
		quote, err = s.dexManager.GetQuote(ctx, req.TokenIn, req.TokenOut, amountIn, req.SlippagePct)
	}
	if err != nil {
		return &pb.QuoteResponse{Error: err.Error()}, status.Errorf(codes.Internal, "failed to get quote: %v", err)
	}

	resp := &pb.QuoteResponse{
		TokenInAddress:  quote.TokenIn.Address,
		TokenOutAddress: quote.TokenOut.Address,
		TokenInSymbol:   quote.TokenIn.Symbol,
		TokenOutSymbol:  quote.TokenOut.Symbol,
		AmountIn:        amountIn.String(),
		AmountOut:       quote.AmountOut.String(),
		AmountOutMin:    quote.AmountOutMin.String(),
		PriceImpact:     quote.PriceImpact,
		MinimumReceived: quote.MinimumReceived.String(),
		GasEstimate:     quote.GasEstimate,
		Route:           quote.Route,
		DexProvider:     quote.DEXProvider,
	}

	return resp, nil
}

// Swap executes a token swap
func (s *dexGRPCServer) Swap(ctx context.Context, req *pb.SwapRequest) (*pb.SwapTxResponse, error) {
	if !s.dexManager.IsEnabled() {
		return &pb.SwapTxResponse{Error: "DEX trading is disabled"}, status.Errorf(codes.FailedPrecondition, "DEX trading is disabled")
	}

	amountIn, ok := new(big.Int).SetString(req.AmountIn, 10)
	if !ok {
		return &pb.SwapTxResponse{Error: "invalid amount_in"}, status.Errorf(codes.InvalidArgument, "invalid amount_in: %s", req.AmountIn)
	}

	amountOutMin, ok := new(big.Int).SetString(req.AmountOutMin, 10)
	if !ok {
		return &pb.SwapTxResponse{Error: "invalid amount_out_min"}, status.Errorf(codes.InvalidArgument, "invalid amount_out_min: %s", req.AmountOutMin)
	}

	deadline, ok := new(big.Int).SetString(req.Deadline, 10)
	if !ok {
		// Default deadline: 5 minutes from now
		deadline = big.NewInt(time.Now().Add(5 * time.Minute).Unix())
	}

	swapParams := &dex.SwapParams{
		TokenInAddress:  req.TokenInAddress,
		TokenOutAddress: req.TokenOutAddress,
		AmountIn:        amountIn,
		AmountOutMin:    amountOutMin,
		Recipient:       req.Recipient,
		SlippagePct:     req.SlippagePct,
		Deadline:        deadline,
	}

	result, err := s.dexManager.Swap(ctx, swapParams)
	if err != nil {
		return &pb.SwapTxResponse{Error: err.Error()}, status.Errorf(codes.Internal, "swap failed: %v", err)
	}

	resp := &pb.SwapTxResponse{
		TxHash:      result.TxHash,
		BlockNumber: result.BlockNumber,
		GasUsed:     result.GasUsed,
		Status:      result.Status,
	}

	if result.GasPrice != nil {
		resp.GasPrice = result.GasPrice.String()
	}
	if result.AmountIn != nil {
		resp.AmountIn = result.AmountIn.String()
	}
	if result.AmountOut != nil {
		resp.AmountOut = result.AmountOut.String()
	}

	return resp, nil
}

// GetTokenInfo returns information about an ERC20 token
func (s *dexGRPCServer) GetTokenInfo(ctx context.Context, req *pb.TokenInfoRequest) (*pb.TokenInfoResponse, error) {
	if !s.dexManager.IsEnabled() {
		return &pb.TokenInfoResponse{Error: "DEX trading is disabled"}, nil
	}

	token, err := s.dexManager.GetTokenInfo(ctx, req.TokenAddress)
	if err != nil {
		return &pb.TokenInfoResponse{Error: err.Error()}, status.Errorf(codes.Internal, "failed to get token info: %v", err)
	}

	return &pb.TokenInfoResponse{
		Address:  token.Address,
		Symbol:   token.Symbol,
		Name:     token.Name,
		Decimals: uint32(token.Decimals),
		LogoUri:  token.LogoURI,
	}, nil
}

// GetBalance returns the balance of a token or native token
func (s *dexGRPCServer) GetBalance(ctx context.Context, req *pb.BalanceRequest) (*pb.BalanceResponse, error) {
	if !s.dexManager.IsEnabled() {
		return &pb.BalanceResponse{Error: "DEX trading is disabled"}, nil
	}

	var balance *big.Int
	var err error

	if req.TokenAddress == "" {
		// Native token balance
		balance, err = s.dexManager.GetNativeBalance(ctx, req.UserAddress)
	} else {
		// ERC20 token balance
		balance, err = s.dexManager.GetTokenBalance(ctx, req.TokenAddress, req.UserAddress)
	}
	if err != nil {
		return &pb.BalanceResponse{Error: err.Error()}, status.Errorf(codes.Internal, "failed to get balance: %v", err)
	}

	return &pb.BalanceResponse{
		Balance: balance.String(),
	}, nil
}
