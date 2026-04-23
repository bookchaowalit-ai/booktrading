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

// PancakeSwapProvider implements Provider for PancakeSwap
type PancakeSwapProvider struct {
	client        *ethclient.Client
	routerAddress common.Address
	factoryAddr   common.Address
	chainID       *big.Int
	signer        Signer
}

func NewPancakeSwapProvider(client *ethclient.Client, cfg *config.DEXRouterConfig, chainID *big.Int) *PancakeSwapProvider {
	return &PancakeSwapProvider{
		client:        client,
		routerAddress: common.HexToAddress(cfg.RouterAddress),
		factoryAddr:   common.HexToAddress(cfg.FactoryAddress),
		chainID:       chainID,
	}
}

func (p *PancakeSwapProvider) GetProvider() config.DEXProvider { return config.DEXPancakeSwap }

func (p *PancakeSwapProvider) SetSigner(s Signer) { p.signer = s }

// signAndSend handles the full transaction signing and broadcasting flow
func (p *PancakeSwapProvider) signAndSend(ctx context.Context, to common.Address, data []byte, value *big.Int, gasLimit uint64) (*SwapResult, error) {
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

func (p *PancakeSwapProvider) GetQuote(ctx context.Context, tokenIn, tokenOut string, amountIn *big.Int, slippagePct float64) (*Quote, error) {
	parsedABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[{"type":"address","name":"tokenA"},{"type":"address","name":"tokenB"}],"name":"getPair","outputs":[{"type":"address","name":"pair"}],"stateMutability":"view","type":"function"}]`))
	callData, _ := parsedABI.Pack("getPair", common.HexToAddress(tokenIn), common.HexToAddress(tokenOut))
	result, err := p.client.CallContract(ctx, ethereum.CallMsg{To: &p.factoryAddr, Data: callData}, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to call factory: %w", err)
	}
	var pair common.Address
	parsedABI.UnpackIntoInterface(&pair, "getPair", result)
	if pair == (common.Address{}) {
		return nil, fmt.Errorf("no pair found for tokens %s -> %s", tokenIn, tokenOut)
	}

	reserveABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[],"name":"getReserves","outputs":[{"type":"uint112","name":"reserve0"},{"type":"uint112","name":"reserve1"},{"type":"uint32","name":"blockTimestampLast"}],"stateMutability":"view","type":"function"}]`))
	reserveData, _ := reserveABI.Pack("getReserves")
	reserveResult, err := p.client.CallContract(ctx, ethereum.CallMsg{To: &pair, Data: reserveData}, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to call pair: %w", err)
	}
	var reserves struct {
		Reserve0, Reserve1 *big.Int
		BlockTimestampLast uint32
	}
	reserveABI.UnpackIntoInterface(&reserves, "getReserves", reserveResult)

	amountOut := calcAmountOutPancake(amountIn, reserves.Reserve0, reserves.Reserve1)
	priceImpact := calcPriceImpact(amountIn, amountOut, reserves.Reserve0, reserves.Reserve1)
	slippageMult := new(big.Float).SetFloat64(1.0 - slippagePct/100.0)
	amountOutMin, _ := new(big.Float).Mul(new(big.Float).SetInt(amountOut), slippageMult).Int(nil)

	return &Quote{AmountIn: amountIn, AmountOut: amountOut, AmountOutMin: amountOutMin, PriceImpact: priceImpact, MinimumReceived: amountOutMin, GasEstimate: 150000, DEXProvider: string(config.DEXPancakeSwap)}, nil
}

func (p *PancakeSwapProvider) Swap(ctx context.Context, params *SwapParams) (*SwapResult, error) {
	parsedABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[{"type":"uint256","name":"amountOutMin"},{"type":"uint256","name":"amountIn"},{"type":"address[]","name":"path"},{"type":"address","name":"to"},{"type":"uint256","name":"deadline"}],"name":"swapExactTokensForTokens","outputs":[{"type":"uint256[]","name":"amounts"}],"stateMutability":"nonpayable","type":"function"}]`))
	path := []common.Address{common.HexToAddress(params.TokenInAddress), common.HexToAddress(params.TokenOutAddress)}
	data, err := parsedABI.Pack("swapExactTokensForTokens", params.AmountIn, params.AmountOutMin, path, common.HexToAddress(params.Recipient), params.Deadline)
	if err != nil {
		return nil, fmt.Errorf("failed to pack swap calldata: %w", err)
	}
	gasEst, err := p.client.EstimateGas(ctx, ethereum.CallMsg{To: &p.routerAddress, Data: data})
	if err != nil {
		gasEst = 150000 // fallback
	}
	logger.Info("PancakeSwap swap", "token_in", params.TokenInAddress, "gas", gasEst)
	return p.signAndSend(ctx, p.routerAddress, data, big.NewInt(0), gasEst)
}

func (p *PancakeSwapProvider) GetLiquidityPools(ctx context.Context, userAddress string) ([]LiquidityPosition, error) {
	return []LiquidityPosition{}, nil
}
func (p *PancakeSwapProvider) AddLiquidity(ctx context.Context, params *AddLiquidityParams) (*SwapResult, error) {
	parsedABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[{"type":"address","name":"tokenA"},{"type":"address","name":"tokenB"},{"type":"uint256","name":"amountA"},{"type":"uint256","name":"amountB"},{"type":"uint256","name":"amountAMin"},{"type":"uint256","name":"amountBMin"},{"type":"address","name":"to"},{"type":"uint256","name":"deadline"}],"name":"addLiquidity","outputs":[{"type":"uint256","name":"amountA"},{"type":"uint256","name":"amountB"},{"type":"uint256","name":"liquidity"}],"stateMutability":"nonpayable","type":"function"}]`))
	data, err := parsedABI.Pack("addLiquidity",
		common.HexToAddress(params.Token0Address), common.HexToAddress(params.Token1Address),
		params.Amount0, params.Amount1, params.Amount0Min, params.Amount1Min,
		common.HexToAddress(params.Recipient), params.Deadline)
	if err != nil {
		return nil, fmt.Errorf("failed to pack addLiquidity calldata: %w", err)
	}
	gasEst, err := p.client.EstimateGas(ctx, ethereum.CallMsg{To: &p.routerAddress, Data: data})
	if err != nil {
		gasEst = 200000 // fallback
	}
	logger.Info("PancakeSwap add liquidity", "token0", params.Token0Address, "token1", params.Token1Address, "gas", gasEst)
	return p.signAndSend(ctx, p.routerAddress, data, big.NewInt(0), gasEst)
}
func (p *PancakeSwapProvider) RemoveLiquidity(ctx context.Context, params *RemoveLiquidityParams) (*SwapResult, error) {
	parsedABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[{"type":"address","name":"tokenA"},{"type":"address","name":"tokenB"},{"type":"uint256","name":"liquidity"},{"type":"uint256","name":"amountAMin"},{"type":"uint256","name":"amountBMin"},{"type":"address","name":"to"},{"type":"uint256","name":"deadline"}],"name":"removeLiquidity","outputs":[{"type":"uint256","name":"amountA"},{"type":"uint256","name":"amountB"}],"stateMutability":"nonpayable","type":"function"}]`))
	tokenA, tokenB, err := p.getTokensFromPool(ctx, params.PoolAddress)
	if err != nil {
		return nil, fmt.Errorf("failed to get tokens from pool: %w", err)
	}
	data, err := parsedABI.Pack("removeLiquidity",
		tokenA, tokenB, params.LPTokenAmount, params.Amount0Min, params.Amount1Min,
		common.HexToAddress(params.Recipient), params.Deadline)
	if err != nil {
		return nil, fmt.Errorf("failed to pack removeLiquidity calldata: %w", err)
	}
	gasEst, err := p.client.EstimateGas(ctx, ethereum.CallMsg{To: &p.routerAddress, Data: data})
	if err != nil {
		gasEst = 200000 // fallback
	}
	logger.Info("PancakeSwap remove liquidity", "pool", params.PoolAddress, "gas", gasEst)
	return p.signAndSend(ctx, p.routerAddress, data, big.NewInt(0), gasEst)
}

func (p *PancakeSwapProvider) GetPoolReserves(ctx context.Context, poolAddress string) (*big.Int, *big.Int, error) {
	reserveABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[],"name":"getReserves","outputs":[{"type":"uint112","name":"reserve0"},{"type":"uint112","name":"reserve1"},{"type":"uint32","name":"blockTimestampLast"}],"stateMutability":"view","type":"function"}]`))
	callData, _ := reserveABI.Pack("getReserves")
	addr := common.HexToAddress(poolAddress)
	result, err := p.client.CallContract(ctx, ethereum.CallMsg{To: &addr, Data: callData}, nil)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to call pool: %w", err)
	}
	var reserves struct {
		Reserve0, Reserve1 *big.Int
		BlockTimestampLast uint32
	}
	reserveABI.UnpackIntoInterface(&reserves, "getReserves", result)
	return reserves.Reserve0, reserves.Reserve1, nil
}

func (p *PancakeSwapProvider) EstimateGas(ctx context.Context, to string, data []byte) (*GasEstimate, error) {
	tAddr := common.HexToAddress(to)
	gasLimit, _ := p.client.EstimateGas(ctx, ethereum.CallMsg{To: &tAddr, Data: data})
	gasPrice, _ := p.client.SuggestGasPrice(ctx)
	return &GasEstimate{GasLimit: gasLimit, GasPrice: gasPrice, GasCostETH: new(big.Int).Mul(big.NewInt(int64(gasLimit)), gasPrice)}, nil
}

func (p *PancakeSwapProvider) GetTokenBalance(ctx context.Context, tokenAddress, userAddress string) (*big.Int, error) {
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

func (p *PancakeSwapProvider) GetNativeBalance(ctx context.Context, userAddress string) (*big.Int, error) {
	return p.client.BalanceAt(ctx, common.HexToAddress(userAddress), nil)
}

func (p *PancakeSwapProvider) GetTokenInfo(ctx context.Context, tokenAddress string) (*Token, error) {
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

func calcAmountOutPancake(amountIn, reserveIn, reserveOut *big.Int) *big.Int {
	amountInWithFee := new(big.Int).Mul(amountIn, big.NewInt(9975))
	numerator := new(big.Int).Mul(amountInWithFee, reserveOut)
	denominator := new(big.Int).Add(new(big.Int).Mul(reserveIn, big.NewInt(10000)), amountInWithFee)
	return new(big.Int).Div(numerator, denominator)
}

// getTokensFromPool queries the pool contract for token0 and token1 addresses
func (p *PancakeSwapProvider) getTokensFromPool(ctx context.Context, poolAddress string) (common.Address, common.Address, error) {
	parsedABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[],"name":"token0","outputs":[{"type":"address","name":""}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"token1","outputs":[{"type":"address","name":""}],"stateMutability":"view","type":"function"}]`))
	addr := common.HexToAddress(poolAddress)

	var token0, token1 common.Address
	if callData, err := parsedABI.Pack("token0"); err == nil {
		if result, err := p.client.CallContract(ctx, ethereum.CallMsg{To: &addr, Data: callData}, nil); err == nil {
			parsedABI.UnpackIntoInterface(&token0, "token0", result)
		}
	}
	if callData, err := parsedABI.Pack("token1"); err == nil {
		if result, err := p.client.CallContract(ctx, ethereum.CallMsg{To: &addr, Data: callData}, nil); err == nil {
			parsedABI.UnpackIntoInterface(&token1, "token1", result)
		}
	}
	if token0 == (common.Address{}) || token1 == (common.Address{}) {
		return common.Address{}, common.Address{}, fmt.Errorf("failed to retrieve token addresses from pool %s", poolAddress)
	}
	return token0, token1, nil
}

func calcPriceImpact(amountIn, amountOut, reserveIn, reserveOut *big.Int) float64 {
	if reserveOut.Cmp(big.NewInt(0)) == 0 {
		return 0
	}
	expectedOut := new(big.Int).Div(new(big.Int).Mul(amountIn, reserveOut), reserveIn)
	if expectedOut.Cmp(big.NewInt(0)) == 0 {
		return 0
	}
	diff := new(big.Int).Sub(expectedOut, amountOut)
	impactFloat := new(big.Float).Quo(new(big.Float).SetInt(diff), new(big.Float).SetInt(expectedOut))
	impactFloat.Mul(impactFloat, big.NewFloat(100))
	impact, _ := impactFloat.Float64()
	return impact
}
