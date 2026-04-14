package service

import (
	"fmt"
	"math"
	"sync"
	"time"

	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/logger"
)

// RiskManager enforces risk limits on trading operations
type RiskManager struct {
	mu sync.RWMutex

	config *model.RiskConfig

	// Tracking state
	peakValue     float64
	currentValue  float64
	dailyStartVal float64
	dailyTrades   int
	totalTrades   int
	wins          int
	losses        int
	grossProfit   float64
	grossLoss     float64
	tradeResults   []float64 // PnL per trade
	stopLossHits  int
	takeProfitHits int
	lastTradeAt   time.Time
	dailyResetAt  time.Time
}

// NewRiskManager creates a new risk manager
func NewRiskManager(config *model.RiskConfig, initialValue float64) *RiskManager {
	if config == nil {
		config = model.DefaultRiskConfig()
	}
	return &RiskManager{
		config:       config,
		peakValue:    initialValue,
		currentValue: initialValue,
		dailyStartVal: initialValue,
		dailyResetAt: time.Now(),
	}
}

// CheckTradeApproval checks if a new trade is allowed under risk limits
// Returns nil if approved, or a list of reasons if blocked
func (rm *RiskManager) CheckTradeApproval(symbol string, side model.OrderSide, quantity, price, portfolioValue float64) []string {
	rm.mu.Lock()
	defer rm.mu.Unlock()

	var blocked []string

	// Reset daily counters if new day
	now := time.Now()
	if now.After(rm.dailyResetAt.Add(24 * time.Hour)) {
		rm.dailyStartVal = rm.currentValue
		rm.dailyTrades = 0
		rm.dailyResetAt = now
	}

	// 1. Check daily loss limit
	dailyLoss := rm.dailyStartVal - rm.currentValue
	if rm.config.MaxDailyLossPercent > 0 {
		maxLoss := rm.dailyStartVal * (rm.config.MaxDailyLossPercent / 100)
		if dailyLoss >= maxLoss {
			blocked = append(blocked, fmt.Sprintf("daily loss limit reached: %.2f%% (max %.2f%%)",
				(dailyLoss/rm.dailyStartVal)*100, rm.config.MaxDailyLossPercent))
		}
	}

	// 2. Check max drawdown
	if rm.config.MaxDrawdownPercent > 0 {
		drawdown := 0.0
		if rm.peakValue > 0 {
			drawdown = (rm.peakValue - rm.currentValue) / rm.peakValue * 100
		}
		if drawdown >= rm.config.MaxDrawdownPercent {
			blocked = append(blocked, fmt.Sprintf("max drawdown reached: %.2f%% (max %.2f%%)",
				drawdown, rm.config.MaxDrawdownPercent))
		}
	}

	// 3. Check position size limit
	if rm.config.MaxPositionSizePercent > 0 {
		positionValue := quantity * price
		positionPct := 0.0
		if portfolioValue > 0 {
			positionPct = (positionValue / portfolioValue) * 100
		}
		if positionPct > rm.config.MaxPositionSizePercent {
			blocked = append(blocked, fmt.Sprintf("position size too large: %.2f%% (max %.2f%%)",
				positionPct, rm.config.MaxPositionSizePercent))
		}
	}

	// 4. Check max concurrent positions
	if rm.config.MaxConcurrentPositions > 0 && side == model.SideBuy {
		// This requires external position count; tracked by caller
		// Placeholder: the caller should pass current position count
	}

	// 5. Check trade cooldown
	if rm.config.TradeCooldownSec > 0 && !rm.lastTradeAt.IsZero() {
		elapsed := time.Since(rm.lastTradeAt).Seconds()
		if elapsed < float64(rm.config.TradeCooldownSec) {
			blocked = append(blocked, fmt.Sprintf("trade cooldown active: %.0fs remaining",
				float64(rm.config.TradeCooldownSec)-elapsed))
		}
	}

	return blocked
}

// RecordTrade records a completed trade for risk tracking
func (rm *RiskManager) RecordTrade(pnl float64, wasStopLoss, wasTakeProfit bool) {
	rm.mu.Lock()
	defer rm.mu.Unlock()

	rm.currentValue += pnl
	rm.totalTrades++
	rm.dailyTrades++
	rm.lastTradeAt = time.Now()
	rm.tradeResults = append(rm.tradeResults, pnl)

	if pnl > 0 {
		rm.wins++
		rm.grossProfit += pnl
	} else {
		rm.losses++
		rm.grossLoss += math.Abs(pnl)
	}

	if wasStopLoss {
		rm.stopLossHits++
		logger.Warn("Stop-loss triggered", "pnl", pnl)
	}
	if wasTakeProfit {
		rm.takeProfitHits++
		logger.Info("Take-profit triggered", "pnl", pnl)
	}

	// Update peak value
	if rm.currentValue > rm.peakValue {
		rm.peakValue = rm.currentValue
	}
}

// GetMetrics returns current risk metrics
func (rm *RiskManager) GetMetrics() *model.RiskMetrics {
	rm.mu.RLock()
	defer rm.mu.RUnlock()

	metrics := &model.RiskMetrics{
		CurrentValue:   rm.currentValue,
		PeakValue:      rm.peakValue,
		TotalTrades:    rm.totalTrades,
		TradesToday:    rm.dailyTrades,
		StopLossHits:   rm.stopLossHits,
		TakeProfitHits: rm.takeProfitHits,
		LastTradeAt:    rm.lastTradeAt,
	}

	// Drawdown
	if rm.peakValue > 0 {
		metrics.MaxDrawdown = (rm.peakValue - rm.currentValue) / rm.peakValue * 100
		metrics.CurrentDrawdown = metrics.MaxDrawdown
	}

	// Daily PnL
	dailyPnL := rm.currentValue - rm.dailyStartVal
	metrics.DailyPnL = dailyPnL
	if rm.dailyStartVal > 0 {
		metrics.DailyPnLPercent = (dailyPnL / rm.dailyStartVal) * 100
	}

	// Win rate
	if rm.totalTrades > 0 {
		metrics.WinRate = float64(rm.wins) / float64(rm.totalTrades) * 100
	}

	// Profit factor
	if rm.grossLoss > 0 {
		metrics.ProfitFactor = rm.grossProfit / rm.grossLoss
	} else if rm.grossProfit > 0 {
		metrics.ProfitFactor = rm.grossProfit
	}

	// Avg win / loss
	if rm.wins > 0 {
		metrics.AvgWin = rm.grossProfit / float64(rm.wins)
	}
	if rm.losses > 0 {
		metrics.AvgLoss = rm.grossLoss / float64(rm.losses)
	}

	// Sharpe ratio (simplified)
	if len(rm.tradeResults) > 1 {
		mean := 0.0
		for _, r := range rm.tradeResults {
			mean += r
		}
		mean /= float64(len(rm.tradeResults))

		variance := 0.0
		for _, r := range rm.tradeResults {
			variance += (r - mean) * (r - mean)
		}
		stdDev := math.Sqrt(variance / float64(len(rm.tradeResults)-1))

		if stdDev > 0 {
			metrics.SharpeRatio = (mean / stdDev) * math.Sqrt(252)
		}
	}

	return metrics
}

// ShouldStopBot checks if the bot should be stopped due to risk limits
func (rm *RiskManager) ShouldStopBot() (bool, string) {
	rm.mu.RLock()
	defer rm.mu.RUnlock()

	// Check daily loss
	if rm.config.MaxDailyLossPercent > 0 {
		dailyLoss := rm.dailyStartVal - rm.currentValue
		maxLoss := rm.dailyStartVal * (rm.config.MaxDailyLossPercent / 100)
		if dailyLoss >= maxLoss {
			return true, fmt.Sprintf("daily loss limit hit: lost %.2f%% (max %.2f%%)",
				(dailyLoss/rm.dailyStartVal)*100, rm.config.MaxDailyLossPercent)
		}
	}

	// Check max drawdown
	if rm.config.MaxDrawdownPercent > 0 {
		drawdown := 0.0
		if rm.peakValue > 0 {
			drawdown = (rm.peakValue - rm.currentValue) / rm.peakValue * 100
		}
		if drawdown >= rm.config.MaxDrawdownPercent {
			return true, fmt.Sprintf("max drawdown hit: %.2f%% (max %.2f%%)",
				drawdown, rm.config.MaxDrawdownPercent)
		}
	}

	return false, ""
}

// CalculatePositionSize calculates optimal position size based on risk config
// Uses percentage of portfolio capped by max position size
func (rm *RiskManager) CalculatePositionSize(portfolioValue float64, price float64) float64 {
	rm.mu.RLock()
	defer rm.mu.RUnlock()

	if price <= 0 || portfolioValue <= 0 {
		return 0
	}

	// Target position as percentage of portfolio
	targetValue := portfolioValue * (rm.config.MaxPositionSizePercent / 100)

	// Convert to quantity
	quantity := targetValue / price

	// Round down to reasonable precision
	return math.Floor(quantity*100000000) / 100000000
}

// UpdateConfig updates the risk configuration
func (rm *RiskManager) UpdateConfig(config *model.RiskConfig) {
	rm.mu.Lock()
	defer rm.mu.Unlock()
	rm.config = config
}

// GetConfig returns the current risk configuration
func (rm *RiskManager) GetConfig() *model.RiskConfig {
	rm.mu.RLock()
	defer rm.mu.RUnlock()
	return rm.config
}

// Reset resets all risk tracking state (but keeps config)
func (rm *RiskManager) Reset(initialValue float64) {
	rm.mu.Lock()
	defer rm.mu.Unlock()

	rm.peakValue = initialValue
	rm.currentValue = initialValue
	rm.dailyStartVal = initialValue
	rm.dailyTrades = 0
	rm.totalTrades = 0
	rm.wins = 0
	rm.losses = 0
	rm.grossProfit = 0
	rm.grossLoss = 0
	rm.tradeResults = nil
	rm.stopLossHits = 0
	rm.takeProfitHits = 0
	rm.lastTradeAt = time.Time{}
	rm.dailyResetAt = time.Now()
}
