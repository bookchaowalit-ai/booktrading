package http

import (
	"context"
	"encoding/json"
	"math"
	"net/http"
	"time"

	"trading-bot-system/backend/internal/port/input"
)

// PerformanceHandler computes performance metrics from trade history
type PerformanceHandler struct {
	tradeHistoryHandler input.TradeHistoryHandler
}

// NewPerformanceHandler creates a new performance handler
func NewPerformanceHandler(handler input.TradeHistoryHandler) *PerformanceHandler {
	return &PerformanceHandler{tradeHistoryHandler: handler}
}

// PerformanceMetrics holds computed trading metrics
type PerformanceMetrics struct {
	TotalTrades        int     `json:"totalTrades"`
	WinningTrades      int     `json:"winningTrades"`
	LosingTrades       int     `json:"losingTrades"`
	WinRate            float64 `json:"winRate"`
	TotalPnL           float64 `json:"totalPnL"`
	TotalPnLPercent    float64 `json:"totalPnLPercent"`
	AvgWin             float64 `json:"avgWin"`
	AvgLoss            float64 `json:"avgLoss"`
	ProfitFactor       float64 `json:"profitFactor"`
	BestTrade          float64 `json:"bestTrade"`
	WorstTrade         float64 `json:"worstTrade"`
	AvgTradeDuration   string  `json:"avgTradeDuration"`
	SharpeRatio        float64 `json:"sharpeRatio"`
	MaxDrawdown        float64 `json:"maxDrawdown"`
	MaxDrawdownPercent float64 `json:"maxDrawdownPercent"`
}

// GetPerformance handles GET /api/performance
func (h *PerformanceHandler) GetPerformance(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Second)
	defer cancel()

	trades, err := h.tradeHistoryHandler.GetTradeHistory(ctx, 1000)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	metrics := computePerformanceMetrics(trades)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(metrics)
}

// computePerformanceMetrics calculates all metrics from raw trades
func computePerformanceMetrics(trades interface{}) PerformanceMetrics {
	// trades is []model.TradeHistory — use reflection-free approach via JSON round-trip
	b, _ := json.Marshal(trades)
	var rows []struct {
		ID         string  `json:"id"`
		Price      float64 `json:"price"`
		Quantity   float64 `json:"quantity"`
		Total      float64 `json:"total"`
		Fee        float64 `json:"fee"`
		Side       string  `json:"side"`
		ExecutedAt string  `json:"executed_at"`
	}
	json.Unmarshal(b, &rows)

	if len(rows) == 0 {
		return PerformanceMetrics{}
	}

	// Pair BUY → SELL trades to compute P&L per round-trip
	var pnls []float64
	var grossWin, grossLoss float64
	var winning, losing int
	totalPnL := 0.0

	// Simple approach: treat every SELL as a realized trade
	// BUY cost approximated by matching chronologically
	var buyPool []struct{ price, qty float64 }
	for _, t := range rows {
		if t.Side == "BUY" {
			buyPool = append(buyPool, struct{ price, qty float64 }{t.Price, t.Quantity})
		} else if t.Side == "SELL" && len(buyPool) > 0 {
			buy := buyPool[0]
			buyPool = buyPool[1:]
			qty := math.Min(buy.qty, t.Quantity)
			pnl := (t.Price - buy.price) * qty
			pnls = append(pnls, pnl)
			totalPnL += pnl
			if pnl >= 0 {
				winning++
				grossWin += pnl
			} else {
				losing++
				grossLoss += math.Abs(pnl)
			}
		}
	}

	total := len(pnls)
	if total == 0 {
		return PerformanceMetrics{TotalTrades: len(rows)}
	}

	winRate := float64(winning) / float64(total) * 100
	avgWin := 0.0
	if winning > 0 {
		avgWin = grossWin / float64(winning)
	}
	avgLoss := 0.0
	if losing > 0 {
		avgLoss = -(grossLoss / float64(losing))
	}
	profitFactor := 0.0
	if grossLoss > 0 {
		profitFactor = grossWin / grossLoss
	}

	// Best / worst
	best, worst := pnls[0], pnls[0]
	for _, p := range pnls {
		if p > best {
			best = p
		}
		if p < worst {
			worst = p
		}
	}

	// Max drawdown
	cumulative := 0.0
	peak := 0.0
	maxDD := 0.0
	for _, p := range pnls {
		cumulative += p
		if cumulative > peak {
			peak = cumulative
		}
		dd := peak - cumulative
		if dd > maxDD {
			maxDD = dd
		}
	}

	maxDDPct := 0.0
	if peak > 0 {
		maxDDPct = -(maxDD / peak * 100)
	}

	// Sharpe ratio (simple: mean/stddev of pnl)
	mean := totalPnL / float64(total)
	variance := 0.0
	for _, p := range pnls {
		diff := p - mean
		variance += diff * diff
	}
	variance /= float64(total)
	stddev := math.Sqrt(variance)
	sharpe := 0.0
	if stddev > 0 {
		sharpe = mean / stddev
	}

	totalPnLPct := 0.0
	if len(rows) > 0 && rows[0].Price > 0 {
		totalPnLPct = totalPnL / (rows[0].Price * rows[0].Quantity) * 100
	}

	return PerformanceMetrics{
		TotalTrades:        len(rows),
		WinningTrades:      winning,
		LosingTrades:       losing,
		WinRate:            math.Round(winRate*100) / 100,
		TotalPnL:           math.Round(totalPnL*100) / 100,
		TotalPnLPercent:    math.Round(totalPnLPct*100) / 100,
		AvgWin:             math.Round(avgWin*100) / 100,
		AvgLoss:            math.Round(avgLoss*100) / 100,
		ProfitFactor:       math.Round(profitFactor*100) / 100,
		BestTrade:          math.Round(best*100) / 100,
		WorstTrade:         math.Round(worst*100) / 100,
		AvgTradeDuration:   "N/A",
		SharpeRatio:        math.Round(sharpe*100) / 100,
		MaxDrawdown:        math.Round(-maxDD*100) / 100,
		MaxDrawdownPercent: math.Round(maxDDPct*100) / 100,
	}
}
