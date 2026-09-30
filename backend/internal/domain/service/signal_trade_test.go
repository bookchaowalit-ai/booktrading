package service

import (
	"context"
	"errors"
	"strings"
	"testing"

	"trading-bot-system/backend/internal/domain/model"
)

// recordingBroadcaster captures trade notifications and bot activity.
type recordingBroadcaster struct {
	MockWebSocketBroadcaster
	trades     []*model.TradeNotification
	activities []*model.BotActivity
}

func (r *recordingBroadcaster) BroadcastTradeNotification(t *model.TradeNotification) {
	r.trades = append(r.trades, t)
}

func (r *recordingBroadcaster) BroadcastBotActivity(a *model.BotActivity) {
	r.activities = append(r.activities, a)
}

func newSignalTestService(mode model.BotMode) (*BotServiceImpl, *recordingBroadcaster) {
	rb := &recordingBroadcaster{}
	svc := NewBotService(&MockBotStatusRepository{}, &MockRedisPublisher{}, rb)
	svc.botMode = mode
	svc.positions = make(map[string]*positionInfo)
	return svc, rb
}

func TestSignalTradeFailedOrderIsNotCountedOrLabelledPaper(t *testing.T) {
	for _, mode := range []model.BotMode{model.BotModeSignal, model.BotModeAuto} {
		svc, rb := newSignalTestService(mode)
		ex := &fakeGridExchange{fail: errors.New("exchange rejected order")}

		if ok := svc.signalTradeStep(context.Background(), "BTCUSDT", "BUY", 0.01, 100, ex.signal); ok {
			t.Fatalf("%s: failed order reported as success", mode)
		}
		if svc.tradesCount != 0 || svc.botStatus.TotalTrades != 0 {
			t.Fatalf("%s: failed order counted: tradesCount=%d total=%d", mode, svc.tradesCount, svc.botStatus.TotalTrades)
		}
		for _, tr := range rb.trades {
			if strings.Contains(tr.Type, "PAPER") {
				t.Fatalf("%s: failed order relabelled as %q", mode, tr.Type)
			}
		}
		if len(rb.trades) != 0 {
			t.Fatalf("%s: failed order produced %d trade notifications", mode, len(rb.trades))
		}
		if len(rb.activities) != 1 || rb.activities[0].Activity != "ORDER_FAILED" {
			t.Fatalf("%s: want one ORDER_FAILED activity, got %+v", mode, rb.activities)
		}
		if len(svc.positions) != 0 {
			t.Fatalf("%s: failed BUY opened a position", mode)
		}
	}
}

func TestSignalTradeSuccessIsCountedAndTracked(t *testing.T) {
	svc, rb := newSignalTestService(model.BotModeAuto)
	ex := &fakeGridExchange{}

	if ok := svc.signalTradeStep(context.Background(), "BTCUSDT", "BUY", 0.01, 100, ex.signal); !ok {
		t.Fatal("successful order reported as failure")
	}
	if svc.tradesCount != 1 || svc.botStatus.TotalTrades != 1 {
		t.Fatalf("tradesCount=%d total=%d, want 1", svc.tradesCount, svc.botStatus.TotalTrades)
	}
	if len(rb.trades) != 1 || rb.trades[0].Type != "SIGNAL_BUY" {
		t.Fatalf("want one SIGNAL_BUY notification, got %+v", rb.trades)
	}
	if pos := svc.positions["BTCUSDT"]; pos == nil || pos.entryPrice != 100 {
		t.Fatalf("auto BUY did not track position: %+v", pos)
	}
}

func TestSignalTradeNotPlacedAfterStop(t *testing.T) {
	svc, _ := newSignalTestService(model.BotModeSignal)
	ex := &fakeGridExchange{}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	if svc.signalTradeStep(ctx, "BTCUSDT", "BUY", 0.01, 100, ex.signal) {
		t.Fatal("order reported after stop")
	}
	if len(ex.orders) != 0 || svc.tradesCount != 0 {
		t.Fatalf("order placed after stop: orders=%v count=%d", ex.orders, svc.tradesCount)
	}
}
