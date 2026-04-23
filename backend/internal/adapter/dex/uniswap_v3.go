package dex

import (
	"context"
	"fmt"
	"math/big"
	"strings"

	"github.com/ethereum/go-ethereum"
	"github.com/ethereum/go-ethereum/accounts/abi"
	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/ethclient"

	"trading-bot-system/backend/internal/config"
	"trading-bot-system/backend/internal/logger"
)

// uint128 is a type alias for ABI packing
type uint128 = uint64

// UniswapV3Provider implements Provider for Uniswap V3
type UniswapV3Provider struct {
	client          *ethclient.Client
	swapRouterAddr  common.Address
	factoryAddr     common.Address
	quoterAddr      common.Address
	positionMgrAddr common.Address
	chainID         *big.Int
	signer          Signer
}

func NewUniswapV3Provider(client *ethclient.Client, cfg *config.DEXRouterConfig, chainID *big.Int) *UniswapV3Provider {
	return &UniswapV3Provider{
		client:          client,
		swapRouterAddr:  common.HexToAddress(cfg.RouterAddress),
		factoryAddr:     common.HexToAddress(cfg.FactoryAddress),
		quoterAddr:      common.HexToAddress(cfg.QuoterAddress),
		positionMgrAddr: common.HexToAddress(cfg.PositionManager),
		chainID:         chainID,
	}
}

func (p *UniswapV3Provider) GetProvider() config.DEXProvider { return config.DEXUniswapV3 }

func (p *UniswapV3Provider) SetSigner(s Signer) { p.signer = s }

// signAndSend handles the full transaction signing and broadcasting flow
func (p *UniswapV3Provider) signAndSend(ctx context.Context, to common.Address, data []byte, value *big.Int, gasLimit uint64) (*SwapResult, error) {
	if p.signer == nil {
		return nil, fmt.Errorf("signer not set, cannot sign transaction")
	}

	client := p.signer.GetClient()
	if client == nil {
		return nil, fmt.Errorf("client not available")
	}

	from := p.signer.GetAddress()

	nonce, err := client.PendingNonceAt(ctx, from)
	if err != nil {
		return nil, fmt.Errorf("failed to get nonce: %w", err)
	}

	gasPrice, err := client.SuggestGasPrice(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to get gas price: %w", err)
	}

	tx := types.NewTransaction(nonce, to, value, gasLimit, gasPrice, data)

	signedTx, err := p.signer.SignTransaction(ctx, tx)
	if err != nil {
		return nil, fmt.Errorf("failed to sign transaction: %w", err)
	}

	err = p.signer.SendTransaction(ctx, signedTx)
	if err != nil {
		return nil, fmt.Errorf("failed to send transaction: %w", err)
	}

	return &SwapResult{
		TxHash:   signedTx.Hash().Hex(),
		Status:   "pending",
		GasUsed:  gasLimit,
		GasPrice: gasPrice,
	}, nil
}

func (p *UniswapV3Provider) GetQuote(ctx context.Context, tokenIn, tokenOut string, amountIn *big.Int, slippagePct float64) (*Quote, error) {
	feeTiers := []uint32{500, 3000, 10000}
	var bestAmountOut *big.Int
	var bestFee uint32
	for _, fee := range feeTiers {
		amountOut, err := p.quoteExactInputSingle(ctx, tokenIn, tokenOut, amountIn, fee)
		if err == nil && (bestAmountOut == nil || amountOut.Cmp(bestAmountOut) > 0) {
			bestAmountOut = amountOut
			bestFee = fee
		}
	}
	if bestAmountOut == nil {
		return nil, fmt.Errorf("no valid route found for tokens %s -> %s", tokenIn, tokenOut)
	}
	slippageMult := new(big.Float).SetFloat64(1.0 - slippagePct/100.0)
	amountOutMin, _ := new(big.Float).Mul(new(big.Float).SetInt(bestAmountOut), slippageMult).Int(nil)
	return &Quote{AmountIn: amountIn, AmountOut: bestAmountOut, AmountOutMin: amountOutMin, PriceImpact: 0.0, MinimumReceived: amountOutMin, GasEstimate: 200000, Route: []string{fmt.Sprintf("fee:%d", bestFee)}, DEXProvider: string(config.DEXUniswapV3)}, nil
}

func (p *UniswapV3Provider) Swap(ctx context.Context, params *SwapParams) (*SwapResult, error) {
	parsedABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[{"type":"address","name":"tokenIn"},{"type":"address","name":"tokenOut"},{"type":"uint24","name":"fee"},{"type":"address","name":"recipient"},{"type":"uint256","name":"deadline"},{"type":"uint256","name":"amountIn"},{"type":"uint256","name":"amountOutMinimum"},{"type":"uint160","name":"sqrtPriceLimitX96"}],"name":"exactInputSingle","outputs":[{"type":"uint256","name":"amountOut"}],"stateMutability":"payable","type":"function"}]`))
	data, err := parsedABI.Pack("exactInputSingle",
		common.HexToAddress(params.TokenInAddress), common.HexToAddress(params.TokenOutAddress),
		uint32(3000), common.HexToAddress(params.Recipient), params.Deadline,
		params.AmountIn, params.AmountOutMin, big.NewInt(0))
	if err != nil {
		return nil, fmt.Errorf("failed to pack swap calldata: %w", err)
	}
	gasEst, err := p.client.EstimateGas(ctx, ethereum.CallMsg{To: &p.swapRouterAddr, Data: data})
	if err != nil {
		gasEst = 200000 // fallback
	}
	logger.Info("Uniswap V3 swap", "token_in", params.TokenInAddress, "gas", gasEst)
	return p.signAndSend(ctx, p.swapRouterAddr, data, big.NewInt(0), gasEst)
}

func (p *UniswapV3Provider) GetLiquidityPools(ctx context.Context, userAddress string) ([]LiquidityPosition, error) {
	return []LiquidityPosition{}, nil
}
func (p *UniswapV3Provider) AddLiquidity(ctx context.Context, params *AddLiquidityParams) (*SwapResult, error) {
	// V3 uses PositionManager for minting positions
	parsedABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[{"type":"tuple","name":"params","components":[{"type":"address","name":"token0"},{"type":"address","name":"token1"},{"type":"uint24","name":"fee"},{"type":"int24","name":"tickLower"},{"type":"int24","name":"tickUpper"},{"type":"uint256","name":"amount0Desired"},{"type":"uint256","name":"amount1Desired"},{"type":"uint256","name":"amount0Min"},{"type":"uint256","name":"amount1Min"},{"type":"address","name":"recipient"},{"type":"uint256","name":"deadline"}]}],"name":"mint","outputs":[{"type":"uint256","name":"tokenId"},{"type":"uint128","name":"liquidity"},{"type":"uint256","name":"amount0"},{"type":"uint256","name":"amount1"}],"stateMutability":"payable","type":"function"}]`))
	// V3 requires tickLower/tickUpper which are not in AddLiquidityParams; use defaults
	// In production, these should be calculated from price range
	tickLower := int32(0)
	tickUpper := int32(0)
	mintParams := struct {
		Token0         common.Address
		Token1         common.Address
		Fee            uint32
		TickLower      int32
		TickUpper      int32
		Amount0Desired *big.Int
		Amount1Desired *big.Int
		Amount0Min     *big.Int
		Amount1Min     *big.Int
		Recipient      common.Address
		Deadline       *big.Int
	}{
		Token0:         common.HexToAddress(params.Token0Address),
		Token1:         common.HexToAddress(params.Token1Address),
		Fee:            3000,
		TickLower:      tickLower,
		TickUpper:      tickUpper,
		Amount0Desired: params.Amount0,
		Amount1Desired: params.Amount1,
		Amount0Min:     params.Amount0Min,
		Amount1Min:     params.Amount1Min,
		Recipient:      common.HexToAddress(params.Recipient),
		Deadline:       params.Deadline,
	}
	data, err := parsedABI.Pack("mint", mintParams)
	if err != nil {
		return nil, fmt.Errorf("failed to pack mint calldata: %w", err)
	}
	gasEst, err := p.client.EstimateGas(ctx, ethereum.CallMsg{To: &p.positionMgrAddr, Data: data})
	if err != nil {
		gasEst = 400000 // fallback
	}
	logger.Info("Uniswap V3 add liquidity", "token0", params.Token0Address, "token1", params.Token1Address, "gas", gasEst)
	return p.signAndSend(ctx, p.positionMgrAddr, data, big.NewInt(0), gasEst)
}
func (p *UniswapV3Provider) RemoveLiquidity(ctx context.Context, params *RemoveLiquidityParams) (*SwapResult, error) {
	// V3 uses PositionManager's decreaseLiquidity + collect
	// For simplicity, we call decreaseLiquidity with the LP amount (tokenId)
	parsedABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[{"type":"tuple","name":"params","components":[{"type":"uint256","name":"tokenId"},{"type":"uint128","name":"liquidity"},{"type":"uint256","name":"amount0Min"},{"type":"uint256","name":"amount1Min"},{"type":"uint256","name":"deadline"}]}],"name":"decreaseLiquidity","outputs":[{"type":"uint256","name":"amount0"},{"type":"uint256","name":"amount1"}],"stateMutability":"payable","type":"function"}]`))
	// In V3, LPTokenAmount is the tokenId
	tokenID := params.LPTokenAmount
	decParams := struct {
		TokenID    *big.Int
		Liquidity  uint128
		Amount0Min *big.Int
		Amount1Min *big.Int
		Deadline   *big.Int
	}{
		TokenID:    tokenID,
		Liquidity:  uint128(0), // 0 means decrease by full liquidity
		Amount0Min: params.Amount0Min,
		Amount1Min: params.Amount1Min,
		Deadline:   params.Deadline,
	}
	data, err := parsedABI.Pack("decreaseLiquidity", decParams)
	if err != nil {
		return nil, fmt.Errorf("failed to pack decreaseLiquidity calldata: %w", err)
	}
	gasEst, err := p.client.EstimateGas(ctx, ethereum.CallMsg{To: &p.positionMgrAddr, Data: data})
	if err != nil {
		gasEst = 300000 // fallback
	}
	logger.Info("Uniswap V3 remove liquidity", "tokenId", tokenID, "gas", gasEst)
	return p.signAndSend(ctx, p.positionMgrAddr, data, big.NewInt(0), gasEst)
}

func (p *UniswapV3Provider) GetPoolReserves(ctx context.Context, poolAddress string) (*big.Int, *big.Int, error) {
	parsedABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[],"name":"liquidity","outputs":[{"type":"uint128","name":""}],"stateMutability":"view","type":"function"}]`))
	callData, _ := parsedABI.Pack("liquidity")
	addr := common.HexToAddress(poolAddress)
	result, err := p.client.CallContract(ctx, ethereum.CallMsg{To: &addr, Data: callData}, nil)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to call pool: %w", err)
	}
	var liquidity *big.Int
	parsedABI.UnpackIntoInterface(&liquidity, "liquidity", result)
	return liquidity, liquidity, nil
}

func (p *UniswapV3Provider) EstimateGas(ctx context.Context, to string, data []byte) (*GasEstimate, error) {
	tAddr := common.HexToAddress(to)
	gasLimit, _ := p.client.EstimateGas(ctx, ethereum.CallMsg{To: &tAddr, Data: data})
	gasPrice, _ := p.client.SuggestGasPrice(ctx)
	return &GasEstimate{GasLimit: gasLimit, GasPrice: gasPrice, GasCostETH: new(big.Int).Mul(big.NewInt(int64(gasLimit)), gasPrice)}, nil
}

func (p *UniswapV3Provider) GetTokenBalance(ctx context.Context, tokenAddress, userAddress string) (*big.Int, error) {
	parsedABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[{"type":"address","name":"account"}],"name":"balanceOf","outputs":[{"type":"uint256","name":""}],"stateMutability":"view","type":"function"}]`))
	callData, _ := parsedABI.Pack("balanceOf", common.HexToAddress(userAddress))
	tAddr := common.HexToAddress(tokenAddress)
	result, err := p.client.CallContract(ctx, ethereum.CallMsg{To: &tAddr, Data: callData}, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to call contract: %w", err)
	}
	var balance *big.Int
	parsedABI.UnpackIntoInterface(&balance, "balanceOf", result)
	return balance, nil
}

func (p *UniswapV3Provider) GetNativeBalance(ctx context.Context, userAddress string) (*big.Int, error) {
	return p.client.BalanceAt(ctx, common.HexToAddress(userAddress), nil)
}

func (p *UniswapV3Provider) GetTokenInfo(ctx context.Context, tokenAddress string) (*Token, error) {
	parsedABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[],"name":"name","outputs":[{"type":"string","name":""}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"symbol","outputs":[{"type":"string","name":""}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"decimals","outputs":[{"type":"uint8","name":""}],"stateMutability":"view","type":"function"}]`))
	tAddr := common.HexToAddress(tokenAddress)
	var name, symbol string
	var decimals uint8
	if d, _ := parsedABI.Pack("name"); d != nil {
		if r, err := p.client.CallContract(ctx, ethereum.CallMsg{To: &tAddr, Data: d}, nil); err == nil {
			parsedABI.UnpackIntoInterface(&name, "name", r)
		}
	}
	if d, _ := parsedABI.Pack("symbol"); d != nil {
		if r, err := p.client.CallContract(ctx, ethereum.CallMsg{To: &tAddr, Data: d}, nil); err == nil {
			parsedABI.UnpackIntoInterface(&symbol, "symbol", r)
		}
	}
	if d, _ := parsedABI.Pack("decimals"); d != nil {
		if r, err := p.client.CallContract(ctx, ethereum.CallMsg{To: &tAddr, Data: d}, nil); err == nil {
			parsedABI.UnpackIntoInterface(&decimals, "decimals", r)
		}
	}
	return &Token{Address: tokenAddress, Symbol: symbol, Name: name, Decimals: decimals}, nil
}

func (p *UniswapV3Provider) quoteExactInputSingle(ctx context.Context, tokenIn, tokenOut string, amountIn *big.Int, fee uint32) (*big.Int, error) {
	parsedABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[{"type":"address","name":"tokenIn"},{"type":"address","name":"tokenOut"},{"type":"uint256","name":"amountIn"},{"type":"uint24","name":"fee"}],"name":"quoteExactInputSingle","outputs":[{"type":"uint256","name":"amountOut"}],"stateMutability":"nonpayable","type":"function"}]`))
	callData, _ := parsedABI.Pack("quoteExactInputSingle", common.HexToAddress(tokenIn), common.HexToAddress(tokenOut), amountIn, fee)
	result, err := p.client.CallContract(ctx, ethereum.CallMsg{To: &p.quoterAddr, Data: callData}, nil)
	if err != nil {
		return nil, err
	}
	var amountOut *big.Int
	parsedABI.UnpackIntoInterface(&amountOut, "quoteExactInputSingle", result)
	return amountOut, nil
}
