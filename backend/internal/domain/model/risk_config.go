package model

import "time"

// RiskConfig holds risk management configuration for a trading bot
type RiskConfig struct {
	// Stop-loss: percentage from entry price to trigger exit
	StopLossPercent float64 `json:"stop_loss_percent"`

	// Take-profit: percentage from entry price to trigger exit
	TakeProfitPercent float64 `json:"take_profit_percent"`

	// Max position size as percentage of total portfolio (0-100)
	MaxPositionSizePercent float64 `json:"max_position_size_percent"`

	// Max daily loss as percentage of initial balance (0-100). Bot stops if hit.
	MaxDailyLossPercent float64 `json:"max_daily_loss_percent"`

	// Max drawdown as percentage of peak portfolio value (0-100). Bot stops if hit.
	MaxDrawdownPercent float64 `json:"max_drawdown_percent"`

	// Max concurrent positions (0 = unlimited)
	MaxConcurrentPositions int `json:"max_concurrent_positions"`

	// Cooldown between trades in seconds to prevent overtrading
	TradeCooldownSec int `json:"trade_cooldown_sec"`

	// Trailing stop: if true, stop-loss follows price upward
	TrailingStop bool `json:"trailing_stop"`

	// Trailing stop distance as percentage from highest price
	TrailingStopPercent float64 `json:"trailing_stop_percent"`
}

// RiskMetrics holds real-time risk metrics for monitoring
type RiskMetrics struct {
	// Current drawdown from peak
	CurrentDrawdown float64 `json:"current_drawdown"`

	// Max drawdown observed
	MaxDrawdown float64 `json:"max_drawdown"`

	// Peak portfolio value
	PeakValue float64 `json:"peak_value"`

	// Current portfolio value
	CurrentValue float64 `json:"current_value"`

	// Today's PnL
	DailyPnL float64 `json:"daily_pnl"`

	// Daily PnL as percentage
	DailyPnLPercent float64 `json:"daily_pnl_percent"`

	// Sharpe ratio (annualized, 252 trading days)
	SharpeRatio float64 `json:"sharpe_ratio"`

	// Win rate percentage (0-100)
	WinRate float64 `json:"win_rate"`

	// Profit factor (gross profit / gross loss)
	ProfitFactor float64 `json:"profit_factor"`

	// Average win
	AvgWin float64 `json:"avg_win"`

	// Average loss
	AvgLoss float64 `json:"avg_loss"`

	// Number of trades today
	TradesToday int `json:"trades_today"`

	// Number of trades total
	TotalTrades int `json:"total_trades"`

	// Number of stop-loss triggered
	StopLossHits int `json:"stop_loss_hits"`

	// Number of take-profit triggered
	TakeProfitHits int `json:"take_profit_hits"`

	// Last trade time
	LastTradeAt time.Time `json:"last_trade_at"`

	// Risk checks that would block new trades
	BlockedReasons []string `json:"blocked_reasons,omitempty"`
}

// DefaultRiskConfig returns a conservative risk configuration
func DefaultRiskConfig() *RiskConfig {
	return &RiskConfig{
		StopLossPercent:        5.0,
		TakeProfitPercent:      10.0,
		MaxPositionSizePercent: 25.0,
		MaxDailyLossPercent:    3.0,
		MaxDrawdownPercent:     10.0,
		MaxConcurrentPositions: 3,
		TradeCooldownSec:       60,
		TrailingStop:           false,
		TrailingStopPercent:    2.0,
	}
}
