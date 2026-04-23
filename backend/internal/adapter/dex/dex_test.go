package dex

import (
	"math/big"
	"testing"
)

// TestAmountOutCalculation tests the Uniswap V2 amount out calculation
func TestAmountOutCalculation(t *testing.T) {
	amountIn, _ := new(big.Int).SetString("1000000000000000000", 10)    // 1 ETH
	reserveIn, _ := new(big.Int).SetString("100000000000000000000", 10) // 100 ETH
	reserveOut, _ := new(big.Int).SetString("200000000000", 10)         // 200000 USDC (6 decimals)

	amountOut := calcAmountOut(amountIn, reserveIn, reserveOut)

	// Should produce a positive output
	if amountOut.Cmp(big.NewInt(0)) <= 0 {
		t.Error("calcAmountOut should produce positive output")
	}
}

// TestPancakeSwapAmountOut tests PancakeSwap's lower fee (0.25% vs 0.3%)
func TestPancakeSwapAmountOut(t *testing.T) {
	amountIn, _ := new(big.Int).SetString("1000000000000000000", 10)
	reserveIn, _ := new(big.Int).SetString("100000000000000000000", 10)
	reserveOut, _ := new(big.Int).SetString("200000000000", 10)

	uniOut := calcAmountOut(amountIn, reserveIn, reserveOut)
	pancakeOut := calcAmountOutPancake(amountIn, reserveIn, reserveOut)

	// PancakeSwap should give slightly more output (lower fee)
	if pancakeOut.Cmp(uniOut) <= 0 {
		t.Errorf("PancakeSwap should give more than Uniswap: pancake=%s, uni=%s", pancakeOut, uniOut)
	}
}

// TestPriceImpact tests price impact calculation
func TestPriceImpact(t *testing.T) {
	amountIn, _ := new(big.Int).SetString("1000000000000000000", 10)       // 1 ETH
	reserveIn, _ := new(big.Int).SetString("100000000000000000000000", 10) // 100K ETH
	reserveOut, _ := new(big.Int).SetString("200000000000000", 10)         // 200B USDC

	amountOut := calcAmountOut(amountIn, reserveIn, reserveOut)
	impact := calcPriceImpact(amountIn, amountOut, reserveIn, reserveOut)

	// Small trade should have < 1% impact
	if impact > 1.0 {
		t.Errorf("Small trade price impact = %f%%, should be < 1.0%%", impact)
	}

	// Large trade should have higher impact
	largeAmountIn, _ := new(big.Int).SetString("100000000000000000000", 10) // 100 ETH
	largeAmountOut := calcAmountOut(largeAmountIn, reserveIn, reserveOut)
	largeImpact := calcPriceImpact(largeAmountIn, largeAmountOut, reserveIn, reserveOut)

	if largeImpact <= impact {
		t.Errorf("Large trade impact (%f) should be > small trade impact (%f)", largeImpact, impact)
	}
}

// TestZeroImpact tests price impact with zero reserves
func TestZeroImpact(t *testing.T) {
	amountIn := big.NewInt(1e18)
	reserveIn := big.NewInt(1e18)
	reserveOut := big.NewInt(0)

	impact := calcPriceImpact(amountIn, big.NewInt(0), reserveIn, reserveOut)
	if impact != 0 {
		t.Errorf("Zero reserve should have 0 impact, got %f", impact)
	}
}
