package service

import (
	"context"
	"math"
	"testing"
	"time"

	"trading-bot-system/backend/internal/domain/model"
)

func approxEq(a, b float64) bool { return math.Abs(a-b) < 1e-9 }

// A marketable SELL limit far below the market must execute at the market
// price, not at the limit (which would book an invented loss).
func TestPaperMarketableLimitFillsAtMarket(t *testing.T) {
	e := NewPaperEngine(1000, 0, nil)
	if _, err := e.PlaceOrder(context.Background(), "BTC", model.SideBuy, 1, 0, 100); err != nil {
		t.Fatal(err)
	}
	sell, err := e.PlaceOrder(context.Background(), "BTC", model.SideSell, 1, 1, 100)
	if err != nil {
		t.Fatal(err)
	}
	if sell.Status != model.PaperOrderStatusFilled || !approxEq(sell.Price, 100) {
		t.Fatalf("sell filled at %v (%s), want 100", sell.Price, sell.Status)
	}
	if !approxEq(e.GetPortfolio().CurrentBalance, 1000) {
		t.Fatalf("balance %v, want 1000", e.GetPortfolio().CurrentBalance)
	}

	buy, err := e.PlaceOrder(context.Background(), "ETH", model.SideBuy, 1, 500, 100)
	if err != nil {
		t.Fatal(err)
	}
	if !approxEq(buy.Price, 100) {
		t.Fatalf("marketable buy limit filled at %v, want 100", buy.Price)
	}
}

// Two resting SELL limits for the whole position: only the first may fill.
// The second used to sell inventory that no longer existed and credit cash.
func TestPaperPendingSellCannotOversellPosition(t *testing.T) {
	e := NewPaperEngine(1000, 0, nil)
	ctx := context.Background()
	if _, err := e.PlaceOrder(ctx, "BTC", model.SideBuy, 1, 0, 100); err != nil {
		t.Fatal(err)
	}
	a, _ := e.PlaceOrder(ctx, "BTC", model.SideSell, 1, 110, 100)
	b, _ := e.PlaceOrder(ctx, "BTC", model.SideSell, 1, 110, 100)
	e.UpdatePrice("BTC", 120)

	filled := 0
	for _, o := range []*model.PaperOrder{a, b} {
		if o.Status == model.PaperOrderStatusFilled {
			filled++
		}
	}
	if filled != 1 {
		t.Fatalf("filled %d sells of a 1-unit position, want 1", filled)
	}
	if got := e.GetPortfolio().CurrentBalance; !approxEq(got, 1010) {
		t.Fatalf("balance %v, want 1010", got)
	}
}

// Two resting BUY limits that each fit the balance alone must not both fill.
func TestPaperPendingBuyCannotOverspend(t *testing.T) {
	e := NewPaperEngine(100, 0, nil)
	ctx := context.Background()
	a, _ := e.PlaceOrder(ctx, "BTC", model.SideBuy, 1, 90, 100)
	b, _ := e.PlaceOrder(ctx, "BTC", model.SideBuy, 1, 90, 100)
	e.UpdatePrice("BTC", 80)
	if a.Status == model.PaperOrderStatusFilled && b.Status == model.PaperOrderStatusFilled {
		t.Fatal("both buys filled; balance went negative")
	}
	if got := e.GetPortfolio().CurrentBalance; got < 0 {
		t.Fatalf("balance %v < 0", got)
	}
}

// Closing a whole position must publish its realized PnL, not 0.
func TestPaperFullCloseEventCarriesPnL(t *testing.T) {
	e := NewPaperEngine(1000, 0, nil)
	bus := NewEventBus()
	got := make(chan float64, 4)
	bus.Subscribe(EventPaperTrade, func(_ context.Context, ev Event) {
		if ev.Data["side"] == string(model.SideSell) {
			got <- ev.Data["pnl"].(float64)
		}
	})
	e.SetEventBus(bus)
	ctx := context.Background()
	if _, err := e.PlaceOrder(ctx, "BTC", model.SideBuy, 2, 0, 100); err != nil {
		t.Fatal(err)
	}
	if _, err := e.PlaceOrder(ctx, "BTC", model.SideSell, 2, 0, 110); err != nil {
		t.Fatal(err)
	}
	select {
	case pnl := <-got:
		if !approxEq(pnl, 20) {
			t.Fatalf("event pnl %v, want 20", pnl)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("no sell event")
	}
}
