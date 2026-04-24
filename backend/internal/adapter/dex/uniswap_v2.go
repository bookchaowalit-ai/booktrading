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

// UniswapV2Provider implements Provider for Uniswap V2
type UniswapV2Provider struct {
	client        *ethclient.Client
	routerAddress common.Address
	factoryAddr   common.Address
	chainID       *big.Int
	signer        Signer
}

func NewUniswapV2Provider(client *ethclient.Client, cfg *config.DEXRouterConfig, chainID *big.Int) *UniswapV2Provider {
	return &UniswapV2Provider{
		client:        client,
		routerAddress: common.HexToAddress(cfg.RouterAddress),
		factoryAddr:   common.HexToAddress(cfg.FactoryAddress),
		chainID:       chainID,
	}
}

func (p *UniswapV2Provider) GetProvider() config.DEXProvider { return config.DEXUniswapV2 }

func (p *UniswapV2Provider) SetSigner(s Signer) { p.signer = s }

// signAndSend handles the full transaction signing and broadcasting flow
func (p *UniswapV2Provider) signAndSend(ctx context.Context, to common.Address, data []byte, value *big.Int, gasLimit uint64) (*SwapResult, error) {
	if p.signer == nil {
		return nil, fmt.Errorf("signer not set, cannot sign transaction")
	}

	client := p.signer.GetClient()
	if client == nil {
		return nil, fmt.Errorf("client not available")
	}

	from := p.signer.GetAddress()

	// Get nonce
	nonce, err := client.PendingNonceAt(ctx, from)
	if err != nil {
		return nil, fmt.Errorf("failed to get nonce: %w", err)
	}

	// Get gas price
	gasPrice, err := client.SuggestGasPrice(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to get gas price: %w", err)
	}

	// Create unsigned transaction
	tx := types.NewTransaction(nonce, to, value, gasLimit, gasPrice, data)

	// Sign transaction using the signer (which handles EIP155 signing internally)
	signedTx, err := p.signer.SignTransaction(ctx, tx)
	if err != nil {
		return nil, fmt.Errorf("failed to sign transaction: %w", err)
	}

	// Broadcast transaction
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

func (p *UniswapV2Provider) GetQuote(ctx context.Context, tokenIn, tokenOut string, amountIn *big.Int, slippagePct float64) (*Quote, error) {
	reserve0, reserve1, err := p.getPoolReservesForTokens(ctx, tokenIn, tokenOut)
	if err != nil {
		return nil, fmt.Errorf("failed to get pool reserves: %w", err)
	}
	amountOut := calcAmountOut(amountIn, reserve0, reserve1)
	priceImpact := calcPriceImpact(amountIn, amountOut, reserve0, reserve1)
	slippageMult := new(big.Float).SetFloat64(1.0 - slippagePct/100.0)
	amountOutMin, _ := new(big.Float).Mul(new(big.Float).SetInt(amountOut), slippageMult).Int(nil)
	return &Quote{AmountIn: amountIn, AmountOut: amountOut, AmountOutMin: amountOutMin, PriceImpact: priceImpact, MinimumReceived: amountOutMin, GasEstimate: 150000, DEXProvider: string(config.DEXUniswapV2)}, nil
}

func (p *UniswapV2Provider) Swap(ctx context.Context, params *SwapParams) (*SwapResult, error) {
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
	logger.Info("Uniswap V2 swap", "token_in", params.TokenInAddress, "gas", gasEst)
	return p.signAndSend(ctx, p.routerAddress, data, big.NewInt(0), gasEst)
}

func (p *UniswapV2Provider) CheckAllowance(ctx context.Context, tokenAddress, owner, spender string) (*big.Int, error) {
	allowanceABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[{"type":"address","name":"owner"},{"type":"address","name":"spender"}],"name":"allowance","outputs":[{"type":"uint256","name":""}],"stateMutability":"view","type":"function"}]`))
	data, _ := allowanceABI.Pack("allowance", common.HexToAddress(owner), common.HexToAddress(spender))
	addr := common.HexToAddress(tokenAddress)
	result, err := p.client.CallContract(ctx, ethereum.CallMsg{To: &addr, Data: data}, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to check allowance: %w", err)
	}
	var allowance *big.Int
	allowanceABI.UnpackIntoInterface(&allowance, "allowance", result)
	return allowance, nil
}

func (p *UniswapV2Provider) ApproveToken(ctx context.Context, params *ApproveParams) (*SwapResult, error) {
	approveABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[{"type":"address","name":"spender"},{"type":"uint256","name":"amount"}],"name":"approve","outputs":[{"type":"bool","name":""}],"stateMutability":"nonpayable","type":"function"}]`))
	data, err := approveABI.Pack("approve", common.HexToAddress(params.Spender), params.Amount)
	if err != nil {
		return nil, fmt.Errorf("failed to pack approve calldata: %w", err)
	}
	tokenAddr := common.HexToAddress(params.TokenAddress)
	gasEst, err := p.client.EstimateGas(ctx, ethereum.CallMsg{To: &tokenAddr, Data: data})
	if err != nil {
		gasEst = 50000 // fallback for approve
	}
	logger.Info("Uniswap V2 approve", "token", params.TokenAddress, "spender", params.Spender, "gas", gasEst)
	return p.signAndSend(ctx, tokenAddr, data, big.NewInt(0), gasEst)
}

func (p *UniswapV2Provider) GetLiquidityPools(ctx context.Context, userAddress string) ([]LiquidityPosition, error) {
	userAddr := common.HexToAddress(userAddress)
	var positions []LiquidityPosition

	// Query factory for all pairs up to a limit
	pairCountABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[],"name":"allPairsLength","outputs":[{"type":"uint256","name":""}],"stateMutability":"view","type":"function"}]`))
	allPairsABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[{"type":"uint256","name":""}],"name":"allPairs","outputs":[{"type":"address","name":""}],"stateMutability":"view","type":"function"}]`))
	balanceOfABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[{"type":"address","name":"account"}],"name":"balanceOf","outputs":[{"type":"uint256","name":""}],"stateMutability":"view","type":"function"}]`))
	totalSupplyABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[],"name":"totalSupply","outputs":[{"type":"uint256","name":""}],"stateMutability":"view","type":"function"}]`))
	getReservesABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[],"name":"getReserves","outputs":[{"type":"uint112","name":"reserve0"},{"type":"uint112","name":"reserve1"},{"type":"uint32","name":"blockTimestampLast"}],"stateMutability":"view","type":"function"}]`))

	callCount, err := p.client.CallContract(ctx, ethereum.CallMsg{To: &p.factoryAddr, Data: pairCountABI.Methods["allPairsLength"].ID}, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to get pair count: %w", err)
	}
	var pairCount *big.Int
	pairCountABI.UnpackIntoInterface(&pairCount, "allPairsLength", callCount)
	if pairCount == nil || pairCount.Cmp(big.NewInt(0)) == 0 {
		return positions, nil
	}

	// Limit to avoid excessive RPC calls — check up to 50 recent pairs
	maxCheck := uint64(50)
	count := pairCount.Uint64()
	if count > maxCheck {
		count = maxCheck
	}

	for i := uint64(0); i < count; i++ {
		pairIdxData, _ := allPairsABI.Pack("allPairs", big.NewInt(int64(i)))
		pairResult, err := p.client.CallContract(ctx, ethereum.CallMsg{To: &p.factoryAddr, Data: pairIdxData}, nil)
		if err != nil {
			continue
		}
		var pairAddr common.Address
		allPairsABI.UnpackIntoInterface(&pairAddr, "allPairs", pairResult)
		if pairAddr == (common.Address{}) {
			continue
		}

		// Check user's LP token balance
		balData, _ := balanceOfABI.Pack("balanceOf", userAddr)
		balResult, err := p.client.CallContract(ctx, ethereum.CallMsg{To: &pairAddr, Data: balData}, nil)
		if err != nil {
			continue
		}
		var lpBalance *big.Int
		balanceOfABI.UnpackIntoInterface(&lpBalance, "balanceOf", balResult)
		if lpBalance == nil || lpBalance.Cmp(big.NewInt(0)) == 0 {
			continue
		}

		// Get total supply
		tsData, _ := totalSupplyABI.Pack("totalSupply")
		tsResult, err := p.client.CallContract(ctx, ethereum.CallMsg{To: &pairAddr, Data: tsData}, nil)
		if err != nil {
			continue
		}
		var totalSupply *big.Int
		totalSupplyABI.UnpackIntoInterface(&totalSupply, "totalSupply", tsResult)
		if totalSupply == nil || totalSupply.Cmp(big.NewInt(0)) == 0 {
			continue
		}

		// Get reserves
		resData, _ := getReservesABI.Pack("getReserves")
		resResult, err := p.client.CallContract(ctx, ethereum.CallMsg{To: &pairAddr, Data: resData}, nil)
		if err != nil {
			continue
		}
		var reserves struct {
			Reserve0, Reserve1 *big.Int
			BlockTimestampLast uint32
		}
		getReservesABI.UnpackIntoInterface(&reserves, "getReserves", resResult)

		// Calculate user's underlying token amounts
		userAmount0 := new(big.Int).Mul(lpBalance, reserves.Reserve0)
		userAmount0 = userAmount0.Div(userAmount0, totalSupply)
		userAmount1 := new(big.Int).Mul(lpBalance, reserves.Reserve1)
		userAmount1 = userAmount1.Div(userAmount1, totalSupply)

		// Derive token0/token1 from pair contract
		token0Addr, token1Addr, err := p.getTokensFromPool(ctx, pairAddr.Hex())
		if err != nil {
			continue
		}
		t0, _ := p.GetTokenInfo(ctx, token0Addr.Hex())
		t1, _ := p.GetTokenInfo(ctx, token1Addr.Hex())

		positions = append(positions, LiquidityPosition{
			PoolAddress:   pairAddr.Hex(),
			Token0:        *t0,
			Token1:        *t1,
			LPTokenAmount: lpBalance,
			Token0Amount:  userAmount0,
			Token1Amount:  userAmount1,
		})
	}

	return positions, nil
}
func (p *UniswapV2Provider) AddLiquidity(ctx context.Context, params *AddLiquidityParams) (*SwapResult, error) {
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
	logger.Info("Uniswap V2 add liquidity", "token0", params.Token0Address, "token1", params.Token1Address, "gas", gasEst)
	return p.signAndSend(ctx, p.routerAddress, data, big.NewInt(0), gasEst)
}
func (p *UniswapV2Provider) RemoveLiquidity(ctx context.Context, params *RemoveLiquidityParams) (*SwapResult, error) {
	parsedABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[{"type":"address","name":"tokenA"},{"type":"address","name":"tokenB"},{"type":"uint256","name":"liquidity"},{"type":"uint256","name":"amountAMin"},{"type":"uint256","name":"amountBMin"},{"type":"address","name":"to"},{"type":"uint256","name":"deadline"}],"name":"removeLiquidity","outputs":[{"type":"uint256","name":"amountA"},{"type":"uint256","name":"amountB"}],"stateMutability":"nonpayable","type":"function"}]`))
	// Extract token addresses from pool address (simplified: params don't have token addresses)
	// For V2, we need token0 and token1 from the pool. Since RemoveLiquidityParams has PoolAddress,
	// we'll use the pool address directly. In V2 the router handles this.
	// We'll need to look up token addresses from the pool; for now use zero addresses as placeholder
	// and rely on the router's removeLiquidity which takes both token addresses.
	// Since we don't have token addresses in RemoveLiquidityParams, we derive from pool.
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
	logger.Info("Uniswap V2 remove liquidity", "pool", params.PoolAddress, "gas", gasEst)
	return p.signAndSend(ctx, p.routerAddress, data, big.NewInt(0), gasEst)
}

func (p *UniswapV2Provider) GetPoolReserves(ctx context.Context, poolAddress string) (*big.Int, *big.Int, error) {
	reserveABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[],"name":"getReserves","outputs":[{"type":"uint112","name":"reserve0"},{"type":"uint112","name":"reserve1"},{"type":"uint32","name":"blockTimestampLast"}],"stateMutability":"view","type":"function"}]`))
	callData, _ := reserveABI.Pack("getReserves")
	addr := common.HexToAddress(poolAddress)
	result, err := p.client.CallContract(ctx, ethereum.CallMsg{To: &addr, Data: callData}, nil)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to call contract: %w", err)
	}
	var reserves struct {
		Reserve0, Reserve1 *big.Int
		BlockTimestampLast uint32
	}
	reserveABI.UnpackIntoInterface(&reserves, "getReserves", result)
	return reserves.Reserve0, reserves.Reserve1, nil
}

func (p *UniswapV2Provider) EstimateGas(ctx context.Context, to string, data []byte) (*GasEstimate, error) {
	tAddr := common.HexToAddress(to)
	gasLimit, _ := p.client.EstimateGas(ctx, ethereum.CallMsg{To: &tAddr, Data: data})
	gasPrice, _ := p.client.SuggestGasPrice(ctx)
	return &GasEstimate{GasLimit: gasLimit, GasPrice: gasPrice, GasCostETH: new(big.Int).Mul(big.NewInt(int64(gasLimit)), gasPrice)}, nil
}

func (p *UniswapV2Provider) GetTokenBalance(ctx context.Context, tokenAddress, userAddress string) (*big.Int, error) {
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

func (p *UniswapV2Provider) GetNativeBalance(ctx context.Context, userAddress string) (*big.Int, error) {
	return p.client.BalanceAt(ctx, common.HexToAddress(userAddress), nil)
}

func (p *UniswapV2Provider) GetTokenInfo(ctx context.Context, tokenAddress string) (*Token, error) {
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

func (p *UniswapV2Provider) getPoolReservesForTokens(ctx context.Context, tokenIn, tokenOut string) (*big.Int, *big.Int, error) {
	parsedABI, _ := abi.JSON(strings.NewReader(`[{"inputs":[{"type":"address","name":"tokenA"},{"type":"address","name":"tokenB"}],"name":"getPair","outputs":[{"type":"address","name":"pair"}],"stateMutability":"view","type":"function"}]`))
	callData, _ := parsedABI.Pack("getPair", common.HexToAddress(tokenIn), common.HexToAddress(tokenOut))
	result, err := p.client.CallContract(ctx, ethereum.CallMsg{To: &p.factoryAddr, Data: callData}, nil)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to call factory: %w", err)
	}
	var pair common.Address
	parsedABI.UnpackIntoInterface(&pair, "getPair", result)
	if pair == (common.Address{}) {
		return nil, nil, fmt.Errorf("no pair found for tokens %s and %s", tokenIn, tokenOut)
	}
	return p.GetPoolReserves(ctx, pair.Hex())
}

// getTokensFromPool queries the pool contract for token0 and token1 addresses
func (p *UniswapV2Provider) getTokensFromPool(ctx context.Context, poolAddress string) (common.Address, common.Address, error) {
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

func calcAmountOut(amountIn, reserveIn, reserveOut *big.Int) *big.Int {
	amountInWithFee := new(big.Int).Mul(amountIn, big.NewInt(997))
	numerator := new(big.Int).Mul(amountInWithFee, reserveOut)
	denominator := new(big.Int).Add(new(big.Int).Mul(reserveIn, big.NewInt(1000)), amountInWithFee)
	return new(big.Int).Div(numerator, denominator)
}
