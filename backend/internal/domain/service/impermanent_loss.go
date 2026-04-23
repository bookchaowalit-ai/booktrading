package service

import (
	"math"
	"math/big"
)

// ImpermanentLossResult contains the results of IL calculation
type ImpermanentLossResult struct {
	ImpermanentLossPct    float64 `json:"il_percentage"`     // IL as percentage
	CurrentValueUSD       float64 `json:"current_value_usd"`  // Current LP position value
	HODLValueUSD          float64 `json:"hold_value_usd"`     // Value if simply held
	LossUSD               float64 `json:"loss_usd"`           // Absolute loss in USD
	Token0Ratio           float64 `json:"token0_ratio"`       // Token0 price ratio change
	FeesEarnedUSD         float64 `json:"fees_earned_usd"`    // Fees earned from LP
	NetResultUSD          float64 `json:"net_result_usd"`     // Net result (fees - IL)
	IsProfitable          bool    `json:"is_profitable"`      // Whether fees > IL
}

// ILCalculator calculates impermanent loss for LP positions
type ILCalculator struct{}

// NewILCalculator creates a new impermanent loss calculator
func NewILCalculator() *ILCalculator {
	return &ILCalculator{}
}

// CalculateIL calculates impermanent loss for a position
// priceRatio = current_price_token0 / initial_price_token0
func (c *ILCalculator) CalculateIL(priceRatio float64) float64 {
	if priceRatio <= 0 {
		return 0
	}

	// IL formula: 2 * sqrt(priceRatio) / (1 + priceRatio) - 1
	sqrtRatio := math.Sqrt(priceRatio)
	il := 2*sqrtRatio/(1+priceRatio) - 1

	return il * 100 // Return as percentage
}

// CalculateILWithFees calculates IL including fee earnings
func (c *ILCalculator) CalculateILWithFees(priceRatio, initialDepositUSD, feeAPR, daysHeld float64) *ImpermanentLossResult {
	// Calculate IL percentage
	ilPct := c.CalculateIL(priceRatio)

	// Calculate current LP position value (after IL)
	currentValue := initialDepositUSD * (1 + ilPct/100)

	// Calculate HODL value (what it would be worth if just held)
	// If price ratio changed, token0 changed in value
	hodlValue := initialDepositUSD * (1 + (priceRatio-1)/2)

	// Calculate absolute loss
	lossUSD := hodlValue - currentValue

	// Calculate fees earned (simplified)
	feesEarned := initialDepositUSD * (feeAPR / 100) * (daysHeld / 365)

	// Calculate net result
	netResult := feesEarned - lossUSD

	return &ImpermanentLossResult{
		ImpermanentLossPct: ilPct,
		CurrentValueUSD:    currentValue,
		HODLValueUSD:       hodlValue,
		LossUSD:            lossUSD,
		Token0Ratio:        priceRatio,
		FeesEarnedUSD:      feesEarned,
		NetResultUSD:       netResult,
		IsProfitable:       feesEarned > lossUSD,
	}
}

// CalculateLPValue calculates the current value of an LP position
func (c *ILCalculator) CalculateLPValue(token0Amount, token1Amount *big.Int, token0PriceUSD, token1PriceUSD float64, token0Decimals, token1Decimals uint8) float64 {
	// Convert from wei to token units
	token0Multiplier := new(big.Float).SetFloat64(math.Pow(10, float64(token0Decimals)))
	token1Multiplier := new(big.Float).SetFloat64(math.Pow(10, float64(token1Decimals)))

	token0Float := new(big.Float).Quo(new(big.Float).SetInt(token0Amount), token0Multiplier)
	token1Float := new(big.Float).Quo(new(big.Float).SetInt(token1Amount), token1Multiplier)

	token0Value, _ := token0Float.Float64()
	token1Value, _ := token1Float.Float64()

	return token0Value*token0PriceUSD + token1Value*token1PriceUSD
}

// GetILSeverity returns a severity level for the IL
func (c *ILCalculator) GetILSeverity(ilPct float64) string {
	absIL := math.Abs(ilPct)
	switch {
	case absIL < 1:
		return "minimal"
	case absIL < 3:
		return "low"
	case absIL < 5:
		return "moderate"
	case absIL < 10:
		return "high"
	default:
		return "severe"
	}
}

// CalculateBreakEvenAPR calculates the minimum APR needed to break even with IL
func (c *ILCalculator) CalculateBreakEvenAPR(ilPct, daysHeld float64) float64 {
	if daysHeld <= 0 {
		return 0
	}
	// APR = |IL| * 365 / daysHeld
	return math.Abs(ilPct) * 365 / daysHeld
}
