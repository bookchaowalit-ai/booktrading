package dex

import (
	"context"
	"math/big"

	"trading-bot-system/backend/internal/config"
)

// Token represents an ERC20 token
type Token struct {
	Address  string `json:"address"`
	Symbol   string `json:"symbol"`
	Name     string `json:"name"`
	Decimals uint8  `json:"decimals"`
	LogoURI  string `json:"logo_uri,omitempty"`
}

// Quote represents a DEX swap quote
type Quote struct {
	TokenIn         Token    `json:"token_in"`
	TokenOut        Token    `json:"token_out"`
	AmountIn        *big.Int `json:"amount_in"`
	AmountOut       *big.Int `json:"amount_out"`
	AmountOutMin    *big.Int `json:"amount_out_min"` // After slippage
	PriceImpact     float64  `json:"price_impact"`   // Percentage
	MinimumReceived *big.Int `json:"minimum_received"`
	GasEstimate     uint64   `json:"gas_estimate"`
	Route           []string `json:"route"` // Pool addresses
	DEXProvider     string   `json:"dex_provider"`
}

// SwapParams contains parameters for a token swap
type SwapParams struct {
	TokenInAddress  string   `json:"token_in_address"`
	TokenOutAddress string   `json:"token_out_address"`
	AmountIn        *big.Int `json:"amount_in"`
	AmountOutMin    *big.Int `json:"amount_out_min"` // Minimum tokens to receive
	Recipient       string   `json:"recipient"`      // Wallet address
	SlippagePct     float64  `json:"slippage_pct"`   // Slippage tolerance
	Deadline        *big.Int `json:"deadline"`       // Unix timestamp
}

// SwapResult contains the result of a swap
type SwapResult struct {
	TxHash      string   `json:"tx_hash"`
	BlockNumber uint64   `json:"block_number"`
	GasUsed     uint64   `json:"gas_used"`
	GasPrice    *big.Int `json:"gas_price"`
	AmountIn    *big.Int `json:"amount_in"`
	AmountOut   *big.Int `json:"amount_out"`
	Status      string   `json:"status"` // "pending", "confirmed", "failed"
}

// LiquidityPosition represents an LP position
type LiquidityPosition struct {
	PoolAddress   string   `json:"pool_address"`
	Token0        Token    `json:"token0"`
	Token1        Token    `json:"token1"`
	LPTokenAmount *big.Int `json:"lp_token_amount"`
	Token0Amount  *big.Int `json:"token0_amount"`
	Token1Amount  *big.Int `json:"token1_amount"`
	FeesEarned0   *big.Int `json:"fees_earned0"`
	FeesEarned1   *big.Int `json:"fees_earned1"`
}

// AddLiquidityParams contains parameters for adding liquidity
type AddLiquidityParams struct {
	Token0Address string   `json:"token0_address"`
	Token1Address string   `json:"token1_address"`
	Amount0       *big.Int `json:"amount0"`
	Amount1       *big.Int `json:"amount1"`
	Amount0Min    *big.Int `json:"amount0_min"`
	Amount1Min    *big.Int `json:"amount1_min"`
	Recipient     string   `json:"recipient"`
	Deadline      *big.Int `json:"deadline"`
}

// RemoveLiquidityParams contains parameters for removing liquidity
type RemoveLiquidityParams struct {
	PoolAddress   string   `json:"pool_address"`
	LPTokenAmount *big.Int `json:"lp_token_amount"`
	Amount0Min    *big.Int `json:"amount0_min"`
	Amount1Min    *big.Int `json:"amount1_min"`
	Recipient     string   `json:"recipient"`
	Deadline      *big.Int `json:"deadline"`
}

// GasEstimate contains gas information
type GasEstimate struct {
	GasLimit   uint64   `json:"gas_limit"`
	GasPrice   *big.Int `json:"gas_price"`
	GasCostETH *big.Int `json:"gas_cost_eth"`
	GasCostUSD *big.Int `json:"gas_cost_usd"`
}

// Provider defines the interface that all DEX providers must implement
type Provider interface {
	// GetQuote returns a quote for a token swap
	GetQuote(ctx context.Context, tokenIn, tokenOut string, amountIn *big.Int, slippagePct float64) (*Quote, error)

	// Swap executes a token swap
	Swap(ctx context.Context, params *SwapParams) (*SwapResult, error)

	// GetLiquidityPools returns all pools where the user has liquidity
	GetLiquidityPools(ctx context.Context, userAddress string) ([]LiquidityPosition, error)

	// AddLiquidity adds liquidity to a pool
	AddLiquidity(ctx context.Context, params *AddLiquidityParams) (*SwapResult, error)

	// RemoveLiquidity removes liquidity from a pool
	RemoveLiquidity(ctx context.Context, params *RemoveLiquidityParams) (*SwapResult, error)

	// GetPoolReserves returns reserves for a specific pool
	GetPoolReserves(ctx context.Context, poolAddress string) (*big.Int, *big.Int, error)

	// EstimateGas estimates gas for a transaction
	EstimateGas(ctx context.Context, to string, data []byte) (*GasEstimate, error)

	// GetTokenBalance returns the balance of an ERC20 token for an address
	GetTokenBalance(ctx context.Context, tokenAddress, userAddress string) (*big.Int, error)

	// GetNativeBalance returns the native token balance (ETH/BNB)
	GetNativeBalance(ctx context.Context, userAddress string) (*big.Int, error)

	// GetTokenInfo returns information about an ERC20 token
	GetTokenInfo(ctx context.Context, tokenAddress string) (*Token, error)

	// GetProvider returns the DEX provider name
	GetProvider() config.DEXProvider

	// SetSigner sets the transaction signer for this provider (see Signer in manager.go)
	SetSigner(signer Signer)
}
