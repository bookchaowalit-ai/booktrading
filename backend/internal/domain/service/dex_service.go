package service

import (
	"context"
	"fmt"
	"math/big"
	"time"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/jackc/pgx/v5/pgxpool"

	"trading-bot-system/backend/internal/adapter/dex"
	"trading-bot-system/backend/internal/config"
	"trading-bot-system/backend/internal/logger"
)

// DexService handles DEX trading operations
type DexService struct {
	dexManager *dex.DEXManager
	walletSvc  *WalletService
	ilCalc     *ILCalculator
	pool       *pgxpool.Pool
	cfg        *config.DexConfig
}

// NewDexService creates a new DEX service
func NewDexService(dexManager *dex.DEXManager, walletSvc *WalletService, pool *pgxpool.Pool, cfg *config.DexConfig) *DexService {
	// Set up the transaction signer on the DEX manager
	txSigner := NewTxSigner(walletSvc)
	dexManager.SetSigner(txSigner)

	return &DexService{
		dexManager: dexManager,
		walletSvc:  walletSvc,
		ilCalc:     NewILCalculator(),
		pool:       pool,
		cfg:        cfg,
	}
}

// SwapTokens executes a token swap
func (s *DexService) SwapTokens(ctx context.Context, userID, walletID, tokenIn, tokenOut string, amountIn *big.Int, slippagePct float64) (*dex.SwapResult, error) {
	if !s.dexManager.IsEnabled() {
		return nil, fmt.Errorf("DEX trading is disabled")
	}

	// Load wallet for this operation
	if walletID != "" {
		if err := s.walletSvc.LoadWalletById(ctx, userID, walletID); err != nil {
			return nil, fmt.Errorf("failed to load wallet: %w", err)
		}
	}

	// Get user's wallet address
	walletAddr := s.walletSvc.GetAddress()
	if walletAddr.Hex() == "" {
		return nil, fmt.Errorf("wallet not loaded")
	}

	// Get quote
	quote, err := s.dexManager.GetQuote(ctx, tokenIn, tokenOut, amountIn, slippagePct)
	if err != nil {
		return nil, fmt.Errorf("failed to get quote: %w", err)
	}

	// Check price impact
	if quote.PriceImpact > s.cfg.MaxPriceImpact {
		return nil, fmt.Errorf("price impact %.2f%% exceeds maximum %.2f%%", quote.PriceImpact, s.cfg.MaxPriceImpact)
	}

	// Set deadline (5 minutes from now)
	deadline := big.NewInt(time.Now().Add(5 * time.Minute).Unix())

	// Execute swap
	swapParams := &dex.SwapParams{
		TokenInAddress:  tokenIn,
		TokenOutAddress: tokenOut,
		AmountIn:        amountIn,
		AmountOutMin:    quote.AmountOutMin,
		Recipient:       walletAddr.Hex(),
		SlippagePct:     slippagePct,
		Deadline:        deadline,
	}

	result, err := s.dexManager.Swap(ctx, swapParams)
	if err != nil {
		return nil, fmt.Errorf("swap failed: %w", err)
	}

	logger.Info("DEX swap executed",
		"user_id", userID,
		"token_in", tokenIn,
		"token_out", tokenOut,
		"amount_in", amountIn,
		"amount_out_min", quote.AmountOutMin,
		"provider", quote.DEXProvider,
	)

	return result, nil
}

// ApproveToken approves a token for the router to spend
func (s *DexService) ApproveToken(ctx context.Context, userID, walletID, tokenAddress string, amount *big.Int) (*dex.SwapResult, error) {
	if !s.dexManager.IsEnabled() {
		return nil, fmt.Errorf("DEX trading is disabled")
	}

	if walletID != "" {
		if err := s.walletSvc.LoadWalletById(ctx, userID, walletID); err != nil {
			return nil, fmt.Errorf("failed to load wallet: %w", err)
		}
	}

	walletAddr := s.walletSvc.GetAddress()
	if walletAddr.Hex() == "" {
		return nil, fmt.Errorf("wallet not loaded")
	}

	// Get the router address from config
	chainCfg := s.dexManager.GetChainConfig()
	if chainCfg == nil {
		return nil, fmt.Errorf("chain config not found")
	}

	dexCfg := s.dexManager.GetConfig()
	routerCfg, ok := dexCfg.DEXRouters[dexCfg.DefaultDEX]
	if !ok {
		return nil, fmt.Errorf("router config not found for %s", dexCfg.DefaultDEX)
	}

	approveParams := &dex.ApproveParams{
		TokenAddress: tokenAddress,
		Spender:      routerCfg.RouterAddress,
		Amount:       amount,
	}

	result, err := s.dexManager.ApproveToken(ctx, approveParams)
	if err != nil {
		return nil, fmt.Errorf("approve failed: %w", err)
	}

	logger.Info("DEX approve executed",
		"user_id", userID,
		"token", tokenAddress,
		"spender", routerCfg.RouterAddress,
		"amount", amount,
	)

	return result, nil
}

// GetSwapQuote gets a quote for a potential swap
func (s *DexService) GetSwapQuote(ctx context.Context, tokenIn, tokenOut string, amountIn *big.Int, slippagePct float64, findBestRoute bool) (*dex.Quote, error) {
	if !s.dexManager.IsEnabled() {
		return nil, fmt.Errorf("DEX trading is disabled")
	}

	if findBestRoute {
		return s.dexManager.GetBestQuote(ctx, tokenIn, tokenOut, amountIn, slippagePct)
	}

	return s.dexManager.GetQuote(ctx, tokenIn, tokenOut, amountIn, slippagePct)
}

// GetLiquidityPools returns all LP positions for a user
func (s *DexService) GetLiquidityPools(ctx context.Context, userAddress string) ([]dex.LiquidityPosition, error) {
	if !s.dexManager.IsEnabled() {
		return nil, fmt.Errorf("DEX trading is disabled")
	}

	positions, err := s.dexManager.GetLiquidityPools(ctx, userAddress)
	if err != nil {
		return nil, fmt.Errorf("failed to get liquidity pools: %w", err)
	}

	return positions, nil
}

// AddLiquidity adds liquidity to a pool
func (s *DexService) AddLiquidity(ctx context.Context, userID, token0, token1 string, amount0, amount1 *big.Int) (*dex.SwapResult, error) {
	if !s.dexManager.IsEnabled() {
		return nil, fmt.Errorf("DEX trading is disabled")
	}

	walletAddr := s.walletSvc.GetAddress()
	if walletAddr.Hex() == "" {
		return nil, fmt.Errorf("wallet not loaded")
	}

	deadline := big.NewInt(time.Now().Add(5 * time.Minute).Unix())

	// Calculate minimum amounts (apply slippage)
	slippage := s.cfg.SlippagePct
	amount0Min := calculateMinAmount(amount0, slippage)
	amount1Min := calculateMinAmount(amount1, slippage)

	params := &dex.AddLiquidityParams{
		Token0Address: token0,
		Token1Address: token1,
		Amount0:       amount0,
		Amount1:       amount1,
		Amount0Min:    amount0Min,
		Amount1Min:    amount1Min,
		Recipient:     walletAddr.Hex(),
		Deadline:      deadline,
	}

	result, err := s.dexManager.AddLiquidity(ctx, params)
	if err != nil {
		return nil, fmt.Errorf("add liquidity failed: %w", err)
	}

	logger.Info("Add liquidity executed",
		"user_id", userID,
		"token0", token0,
		"token1", token1,
		"amount0", amount0,
		"amount1", amount1,
	)

	return result, nil
}

// RemoveLiquidity removes liquidity from a pool
func (s *DexService) RemoveLiquidity(ctx context.Context, userID, poolAddress string, lpAmount *big.Int) (*dex.SwapResult, error) {
	if !s.dexManager.IsEnabled() {
		return nil, fmt.Errorf("DEX trading is disabled")
	}

	walletAddr := s.walletSvc.GetAddress()
	if walletAddr.Hex() == "" {
		return nil, fmt.Errorf("wallet not loaded")
	}

	deadline := big.NewInt(time.Now().Add(5 * time.Minute).Unix())
	slippage := s.cfg.SlippagePct

	// Get pool reserves to calculate minimum amounts
	reserve0, reserve1, err := s.dexManager.GetPoolReserves(ctx, poolAddress)
	if err != nil {
		return nil, fmt.Errorf("failed to get pool reserves: %w", err)
	}

	// Estimate minimum amounts based on LP share (simplified)
	amount0Min := calculateMinAmount(reserve0, slippage)
	amount1Min := calculateMinAmount(reserve1, slippage)

	params := &dex.RemoveLiquidityParams{
		PoolAddress:   poolAddress,
		LPTokenAmount: lpAmount,
		Amount0Min:    amount0Min,
		Amount1Min:    amount1Min,
		Recipient:     walletAddr.Hex(),
		Deadline:      deadline,
	}

	result, err := s.dexManager.RemoveLiquidity(ctx, params)
	if err != nil {
		return nil, fmt.Errorf("remove liquidity failed: %w", err)
	}

	logger.Info("Remove liquidity executed",
		"user_id", userID,
		"pool", poolAddress,
		"lp_amount", lpAmount,
	)

	return result, nil
}

// CalculateImpermanentLoss calculates IL for a position
func (s *DexService) CalculateImpermanentLoss(priceRatio, initialDepositUSD, feeAPR, daysHeld float64) *ImpermanentLossResult {
	return s.ilCalc.CalculateILWithFees(priceRatio, initialDepositUSD, feeAPR, daysHeld)
}

// GetTokenBalance returns the balance of an ERC20 token
func (s *DexService) GetTokenBalance(ctx context.Context, tokenAddress, userAddress string) (*big.Int, error) {
	return s.dexManager.GetTokenBalance(ctx, tokenAddress, userAddress)
}

// GetNativeBalance returns the native token balance
func (s *DexService) GetNativeBalance(ctx context.Context, userAddress string) (*big.Int, error) {
	return s.dexManager.GetNativeBalance(ctx, userAddress)
}

// GetTokenInfo returns token information
func (s *DexService) GetTokenInfo(ctx context.Context, tokenAddress string) (*dex.Token, error) {
	return s.dexManager.GetTokenInfo(ctx, tokenAddress)
}

// CheckAllowance returns the approved allowance for a token
func (s *DexService) CheckAllowance(ctx context.Context, tokenAddress, owner, spender string) (*big.Int, error) {
	return s.dexManager.CheckAllowance(ctx, tokenAddress, owner, spender)
}

// SaveTransaction records a swap transaction to the database
func (s *DexService) SaveTransaction(ctx context.Context, userID, walletID, txHash, dexProvider, tokenInAddr, tokenOutAddr, tokenInAmount string, status string) error {
	_, err := s.pool.Exec(ctx, `
		INSERT INTO dex_swap_history (user_id, wallet_id, tx_hash, dex_provider, chain_id, token_in_address, token_out_address, token_in_amount, status)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		ON CONFLICT (tx_hash) DO UPDATE SET status = $9
	`, userID, walletID, txHash, dexProvider, s.cfg.DefaultChain, tokenInAddr, tokenOutAddr, tokenInAmount, status)
	return err
}

// GetTransactionHistory returns recent transactions for a user
func (s *DexService) GetTransactionHistory(ctx context.Context, userID string, limit int) ([]map[string]interface{}, error) {
	if limit <= 0 || limit > 50 {
		limit = 20
	}
	rows, err := s.pool.Query(ctx, `
		SELECT tx_hash, dex_provider, token_in_address, token_out_address, token_in_amount, token_out_amount, status, created_at, confirmed_at
		FROM dex_swap_history
		WHERE user_id = $1
		ORDER BY created_at DESC
		LIMIT $2
	`, userID, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to query transaction history: %w", err)
	}
	defer rows.Close()

	var results []map[string]interface{}
	for rows.Next() {
		var txHash, dexProvider, tokenInAddr, tokenOutAddr, tokenInAmount, status string
		var tokenOutAmount, confirmedAt interface{}
		var createdAt interface{}
		err := rows.Scan(&txHash, &dexProvider, &tokenInAddr, &tokenOutAddr, &tokenInAmount, &tokenOutAmount, &status, &createdAt, &confirmedAt)
		if err != nil {
			return nil, fmt.Errorf("failed to scan transaction: %w", err)
		}
		results = append(results, map[string]interface{}{
			"tx_hash":         txHash,
			"dex_provider":    dexProvider,
			"token_in":        map[string]string{"address": tokenInAddr, "amount": tokenInAmount},
			"token_out":       map[string]string{"address": tokenOutAddr, "amount": fmt.Sprintf("%v", tokenOutAmount)},
			"status":          status,
			"created_at":      createdAt,
			"confirmed_at":    confirmedAt,
		})
	}
	return results, nil
}

// GetTransactionStatus returns the on-chain status of a transaction
func (s *DexService) GetTransactionStatus(ctx context.Context, txHash string) (map[string]interface{}, error) {
	if !s.dexManager.IsEnabled() {
		return nil, fmt.Errorf("DEX trading is disabled")
	}

	client := s.dexManager.GetClient()
	if client == nil {
		return nil, fmt.Errorf("blockchain client not available")
	}

	hash := common.HexToHash(txHash)
	receipt, err := client.TransactionReceipt(ctx, hash)
	if err != nil {
		// Transaction not yet mined
		return map[string]interface{}{"status": "pending"}, nil
	}

	// Get the block number of the latest block for confirmations
	header, err := client.HeaderByNumber(ctx, nil)
	if err != nil {
		return map[string]interface{}{
			"status":      "confirmed",
			"blockNumber": receipt.BlockNumber.Uint64(),
		}, nil
	}

	confirmations := uint64(0)
	if header.Number.Uint64() >= receipt.BlockNumber.Uint64() {
		confirmations = header.Number.Uint64() - receipt.BlockNumber.Uint64()
	}

	txStatus := "confirmed"
	if receipt.Status == types.ReceiptStatusFailed {
		txStatus = "failed"
	}

	return map[string]interface{}{
		"status":        txStatus,
		"blockNumber":   receipt.BlockNumber.Uint64(),
		"confirmations": confirmations,
	}, nil
}

// GetDEXConfig returns the DEX configuration
func (s *DexService) GetDEXConfig() *config.DexConfig {
	return s.cfg
}

// GetCurrentProvider returns the current DEX provider
func (s *DexService) GetCurrentProvider() string {
	provider, err := s.dexManager.GetCurrentProvider()
	if err != nil {
		return ""
	}
	return string(provider.GetProvider())
}

// SwitchProvider switches the active DEX provider
func (s *DexService) SwitchProvider(providerName config.DEXProvider) error {
	return s.dexManager.SetCurrentProvider(providerName)
}

// ListProviders returns available DEX providers
func (s *DexService) ListProviders() []config.DEXProvider {
	return s.dexManager.ListProviders()
}

// Helper: calculate minimum amount after slippage
func calculateMinAmount(amount *big.Int, slippagePct float64) *big.Int {
	slippageMultiplier := new(big.Float).SetFloat64(1.0 - slippagePct/100.0)
	minAmountFloat := new(big.Float).Mul(new(big.Float).SetInt(amount), slippageMultiplier)
	minAmount, _ := minAmountFloat.Int(nil)
	return minAmount
}
