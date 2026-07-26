package http

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"trading-bot-system/backend/internal/adapter/redis"
	"trading-bot-system/backend/internal/domain/service"
	"trading-bot-system/backend/internal/logger"
)

// MoneyDashboardHandler handles the money dashboard endpoint
type MoneyDashboardHandler struct {
	redisAdapter *redis.RedisAdapter
	paperEngine  *service.PaperEngine
}

// NewMoneyDashboardHandler creates a new money dashboard handler
func NewMoneyDashboardHandler(redisAdapter *redis.RedisAdapter, paperEngine *service.PaperEngine) *MoneyDashboardHandler {
	return &MoneyDashboardHandler{
		redisAdapter: redisAdapter,
		paperEngine:  paperEngine,
	}
}

// MoneyDashboardResponse represents the aggregated PnL from all bots
type MoneyDashboardResponse struct {
	Timestamp      time.Time         `json:"timestamp"`
	TotalPaperPnL  float64           `json:"total_paper_pnl_thb"`
	TotalRealPnL   float64           `json:"total_real_pnl_thb"`
	GrandTotalPnL  float64           `json:"grand_total_pnl_thb"`
	Bots           []BotPnL          `json:"bots"`
	PaperPortfolio *PortfolioSummary `json:"paper_portfolio"`
	RealBalances   []BalanceInfo     `json:"real_balances"`
}

type BotPnL struct {
	Name         string  `json:"name"`
	Type         string  `json:"type"` // "paper" or "real"
	Status       string  `json:"status"`
	TotalTrades  int     `json:"total_trades"`
	WinRate      float64 `json:"win_rate_pct"`
	PnL          float64 `json:"pnl_thb"`
	Capital      float64 `json:"capital_thb"`
	LastActivity string  `json:"last_activity"`
}

type PortfolioSummary struct {
	InitialBalance  float64 `json:"initial_balance"`
	CurrentValue    float64 `json:"current_value"`
	TotalPnL        float64 `json:"total_pnl"`
	TotalPnLPct     float64 `json:"total_pnl_pct"`
	TotalTrades     int     `json:"total_trades"`
	WinTrades       int     `json:"win_trades"`
	LossTrades      int     `json:"loss_trades"`
}

type BalanceInfo struct {
	Asset string  `json:"asset"`
	Free  float64 `json:"free"`
	Total float64 `json:"total"`
}

// RegisterRoutes registers the money dashboard routes
func (h *MoneyDashboardHandler) RegisterRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/dashboard/money", h.GetMoneyDashboard)
}

// GetMoneyDashboard returns aggregated PnL from all trading bots
func (h *MoneyDashboardHandler) GetMoneyDashboard(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	client := h.redisAdapter.GetClient()

	resp := MoneyDashboardResponse{
		Timestamp: time.Now(),
		Bots:      make([]BotPnL, 0),
	}

	// 1. Arbitrage Paper Bot
	arbData, err := client.Get(ctx, "arbitrage_paper:state").Result()
	if err == nil {
		var arbState map[string]interface{}
		if json.Unmarshal([]byte(arbData), &arbState) == nil {
			capital, _ := arbState["capital_thb"].(float64)
			pnl, _ := arbState["total_pnl_thb"].(float64)
			trades, _ := arbState["total_trades"].(float64)
			wins, _ := arbState["winning_trades"].(float64)
			lastScan, _ := arbState["last_scan_at"].(float64)

			winRate := 0.0
			if trades > 0 {
				winRate = (wins / trades) * 100
			}

			lastActivity := ""
			if lastScan > 0 {
				lastActivity = time.Unix(int64(lastScan), 0).UTC().Format(time.RFC3339)
			}

			resp.Bots = append(resp.Bots, BotPnL{
				Name:         "Arbitrage Paper",
				Type:         "paper",
				Status:       "running",
				TotalTrades:  int(trades),
				WinRate:      winRate,
				PnL:          pnl,
				Capital:      capital,
				LastActivity: lastActivity,
			})
			resp.TotalPaperPnL += pnl
		}
	}

	// 2. Polymarket Paper Bot
	polyData, err := client.Get(ctx, "poly_paper:state").Result()
	if err == nil {
		var polyState map[string]interface{}
		if json.Unmarshal([]byte(polyData), &polyState) == nil {
			bankroll, _ := polyState["bankroll"].(float64)
			pnl, _ := polyState["total_pnl"].(float64)
			trades, _ := polyState["total_trades"].(float64)
			wins, _ := polyState["winning_trades"].(float64)
			killSwitch, _ := polyState["kill_switch_active"].(bool)

			winRate := 0.0
			if trades > 0 {
				winRate = (wins / trades) * 100
			}

			status := "running"
			if killSwitch {
				status = "kill_switch_active"
			}

			resp.Bots = append(resp.Bots, BotPnL{
				Name:        "Polymarket Paper",
				Type:        "paper",
				Status:      status,
				TotalTrades: int(trades),
				WinRate:     winRate,
				PnL:         pnl,
				Capital:     bankroll,
			})
			resp.TotalPaperPnL += pnl
		}
	}

	// 3. Grid Bots (real trading)
	gridPairs := []string{"BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "BTCTHB", "ETHTHB", "SOLTHB", "XRPTHB", "BNBTHB"}
	for _, pair := range gridPairs {
		key := "real_grid:" + pair + ":state"
		gridData, err := client.Get(ctx, key).Result()
		if err == nil {
			var gridState map[string]interface{}
			if json.Unmarshal([]byte(gridData), &gridState) == nil {
				pnl, _ := gridState["total_pnl"].(float64)
				trades, _ := gridState["total_trades"].(float64)
				if trades > 0 {
					resp.Bots = append(resp.Bots, BotPnL{
						Name:        "Grid " + pair,
						Type:        "real",
						Status:      "running",
						TotalTrades: int(trades),
						PnL:         pnl,
					})
					resp.TotalRealPnL += pnl
				}
			}
		}
	}

	// 3b. DCA Bot (accumulation — bear market strategy)
	dcaSymbols := []string{"BTCTHB", "ETHTHB"}
	for _, sym := range dcaSymbols {
		key := "dca_bot:" + sym + ":state"
		dcaHash, err := client.HGetAll(ctx, key).Result()
		if err == nil && len(dcaHash) > 0 {
			spent := parseFloat(dcaHash["total_spent_thb"])
			realized := parseFloat(dcaHash["realized_pnl_thb"])
			unrealized := parseFloat(dcaHash["unrealized_pnl_thb"])
			buys := parseInt(dcaHash["buy_trades"])
			sells := parseInt(dcaHash["sell_trades"])
			halted := dcaHash["halted"] == "True" || dcaHash["halted"] == "true"

			pnl := realized + unrealized
			totalTrades := buys + sells
			status := "running"
			if halted {
				status = "halted"
			}

			resp.Bots = append(resp.Bots, BotPnL{
				Name:        "DCA " + sym,
				Type:        "real",
				Status:      status,
				TotalTrades: totalTrades,
				PnL:         pnl,
				Capital:     spent,
			})
			resp.TotalRealPnL += pnl
		}
	}

	// 3c. Trend Following Bot (rides trends)
	trendSymbols := []string{"BTCTHB", "ETHTHB", "BNBTHB"}
	for _, sym := range trendSymbols {
		key := "trend_bot:" + sym + ":state"
		trendHash, err := client.HGetAll(ctx, key).Result()
		if err == nil && len(trendHash) > 0 {
			realized := parseFloat(trendHash["realized_pnl_thb"])
			wins := parseFloat(trendHash["win_trades"])
			totalT := parseFloat(trendHash["total_trades"])
			cost := parseFloat(trendHash["position_cost_thb"])
			halted := trendHash["halted"] == "True" || trendHash["halted"] == "true"

			status := "running"
			if halted {
				status = "halted"
			}

			winRate := 0.0
			if totalT > 0 {
				winRate = (wins / totalT) * 100
			}

			resp.Bots = append(resp.Bots, BotPnL{
				Name:        "Trend " + sym,
				Type:        "real",
				Status:      status,
				TotalTrades: int(totalT),
				WinRate:     winRate,
				PnL:         realized,
				Capital:     cost,
			})
			resp.TotalRealPnL += realized
		}
	}

	// 3d. Futures Bot (bear market shorts — Binance Global)
	futuresSymbols := []string{"BTCUSDT", "ETHUSDT"}
	for _, sym := range futuresSymbols {
		key := "futures_bot:" + sym + ":state"
		futuresHash, err := client.HGetAll(ctx, key).Result()
		if err == nil && len(futuresHash) > 0 {
			realized := parseFloat(futuresHash["realized_pnl"])
			unrealized := parseFloat(futuresHash["unrealized_pnl"])
			wins := parseFloat(futuresHash["win_trades"])
			totalT := parseFloat(futuresHash["total_trades"])
			halted := futuresHash["halted"] == "True" || futuresHash["halted"] == "true"

			pnl := realized + unrealized
			status := "running"
			if halted {
				status = "halted"
			}

			winRate := 0.0
			if totalT > 0 {
				winRate = (wins / totalT) * 100
			}

			resp.Bots = append(resp.Bots, BotPnL{
				Name:        "Futures " + sym,
				Type:        "futures",
				Status:      status,
				TotalTrades: int(totalT),
				WinRate:     winRate,
				PnL:         pnl,
				Capital:     0,
			})
			resp.TotalRealPnL += pnl
		}
	}

	// 4. Paper Trading Portfolio
	portfolio := h.paperEngine.GetPortfolio()
	if portfolio != nil {
		resp.PaperPortfolio = &PortfolioSummary{
			InitialBalance: portfolio.InitialBalance,
			CurrentValue:   portfolio.TotalValue,
			TotalPnL:       portfolio.TotalPnL,
			TotalPnLPct:    portfolio.TotalPnLPercent,
			TotalTrades:    portfolio.TotalTrades,
			WinTrades:      portfolio.WinTrades,
			LossTrades:     portfolio.LossTrades,
		}
		resp.TotalPaperPnL += portfolio.TotalPnL
	}

	// 5. Real Balances from Binance TH
	realBalances := getRealBalancesFromContext(r)
	if realBalances != nil {
		resp.RealBalances = realBalances
	}

	resp.GrandTotalPnL = resp.TotalPaperPnL + resp.TotalRealPnL

	logger.Info("Money dashboard requested",
		"paper_pnl", resp.TotalPaperPnL,
		"real_pnl", resp.TotalRealPnL,
		"bots", len(resp.Bots),
	)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

// Helper to get balances from request context (set by middleware or handler)
func getRealBalancesFromContext(r *http.Request) []BalanceInfo {
	if balances, ok := r.Context().Value("real_balances").([]BalanceInfo); ok {
		return balances
	}
	return nil
}

// MoneyDashboardHandlerWithBalances wraps the handler to inject real balances
func (h *MoneyDashboardHandler) MoneyDashboardHandlerWithBalances(balances []BalanceInfo) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ctx := context.WithValue(r.Context(), "real_balances", balances)
		h.GetMoneyDashboard(w, r.WithContext(ctx))
	}
}

// Helper functions to parse Redis hash values
func parseFloat(s string) float64 {
	if s == "" {
		return 0
	}
	var f float64
	fmt.Sscanf(s, "%f", &f)
	return f
}

func parseInt(s string) int {
	if s == "" {
		return 0
	}
	var i int
	fmt.Sscanf(s, "%d", &i)
	return i
}
