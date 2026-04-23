package service

import (
	"math"
	"math/big"
	"testing"
)

// TestImpermanentLossCalculation tests IL calculation for various price ratios
func TestImpermanentLossCalculation(t *testing.T) {
	calc := NewILCalculator()

	tests := []struct {
		name       string
		priceRatio float64
		expectedIL float64
	}{
		{"no_change", 1.0, 0.0},
		{"2x_price_increase", 2.0, -5.72},
		{"0.5x_price_decrease", 0.5, -5.72},
		{"10x_price_increase", 10.0, -26.8},
		{"0.1x_price_decrease", 0.1, -26.8},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			il := calc.CalculateIL(tt.priceRatio)
			// Allow 0.1% tolerance
			if math.Abs(il-tt.expectedIL) > 0.1 {
				t.Errorf("CalculateIL(%f) = %f, want %f", tt.priceRatio, il, tt.expectedIL)
			}
		})
	}
}

// TestILWithFees tests IL calculation including fee earnings
func TestILWithFees(t *testing.T) {
	calc := NewILCalculator()

	// 2x price change: IL = 2*sqrt(2)/(1+2) - 1 = 2*1.414/3 - 1 = -0.0572 = -5.72%
	result := calc.CalculateILWithFees(2.0, 1000, 20, 30)

	expectedIL := -5.719
	if math.Abs(result.ImpermanentLossPct-expectedIL) > 0.1 {
		t.Errorf("Expected ~%f%% IL, got %f", expectedIL, result.ImpermanentLossPct)
	}

	// Fees should partially offset IL
	expectedFees := 1000 * 0.20 * (30.0 / 365.0) // ~$16.44
	if math.Abs(result.FeesEarnedUSD-expectedFees) > 0.01 {
		t.Errorf("Expected fees ~%f, got %f", expectedFees, result.FeesEarnedUSD)
	}
}

// TestILSeverity tests severity classification
func TestILSeverity(t *testing.T) {
	calc := NewILCalculator()

	tests := []struct {
		ilPct    float64
		expected string
	}{
		{0.5, "minimal"},
		{2.0, "low"},
		{4.0, "moderate"},
		{7.0, "high"},
		{15.0, "severe"},
	}

	for _, tt := range tests {
		t.Run(tt.expected, func(t *testing.T) {
			severity := calc.GetILSeverity(tt.ilPct)
			if severity != tt.expected {
				t.Errorf("GetILSeverity(%f) = %s, want %s", tt.ilPct, severity, tt.expected)
			}
		})
	}
}

// TestBreakEvenAPR tests break-even APR calculation
func TestBreakEvenAPR(t *testing.T) {
	calc := NewILCalculator()

	// 5% IL over 30 days requires ~60.8% APR to break even
	apr := calc.CalculateBreakEvenAPR(5.0, 30)
	expected := 5.0 * 365 / 30 // ~60.83

	if math.Abs(apr-expected) > 0.01 {
		t.Errorf("CalculateBreakEvenAPR(5, 30) = %f, want %f", apr, expected)
	}

	// Zero days should return 0
	if calc.CalculateBreakEvenAPR(5.0, 0) != 0 {
		t.Error("CalculateBreakEvenAPR with 0 days should return 0")
	}
}

// TestLPValueCalculation tests LP position value calculation
func TestLPValueCalculation(t *testing.T) {
	calc := NewILCalculator()

	// 1 ETH at $2000 + 1000 USDC at $1
	ethAmount := "1000000000000000000" // 1 ETH in wei
	usdcAmount := "1000000000"         // 1000 USDC (6 decimals)

	// Use big.Int parsing
	ethBig, _ := new(big.Int).SetString(ethAmount, 10)
	usdcBig, _ := new(big.Int).SetString(usdcAmount, 10)

	value := calc.CalculateLPValue(ethBig, usdcBig, 2000, 1, 18, 6)
	expected := 3000.0 // 1*2000 + 1000*1

	if math.Abs(value-expected) > 0.01 {
		t.Errorf("CalculateLPValue = %f, want %f", value, expected)
	}
}
