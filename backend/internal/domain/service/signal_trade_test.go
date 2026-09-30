package service

import (
	"context"
	"errors"
	"strings"
	"testing"
	"time"

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

		if ok := svc.signalTradeStep(context.Background(), newSignalOrderBook(), "BTCUSDT", "BUY", 0.01, 100, ex); ok {
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

	if ok := svc.signalTradeStep(context.Background(), newSignalOrderBook(), "BTCUSDT", "BUY", 0.01, 100, ex); !ok {
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

	if svc.signalTradeStep(ctx, newSignalOrderBook(), "BTCUSDT", "BUY", 0.01, 100, ex) {
		t.Fatal("order reported after stop")
	}
	if len(ex.orders) != 0 || svc.tradesCount != 0 {
		t.Fatalf("order placed after stop: orders=%v count=%d", ex.orders, svc.tradesCount)
	}
}

func signalClock(book *signalOrderBook) *time.Time {
	now := time.Unix(1_700_000_000, 0)
	book.now = func() time.Time { return now }
	return &now
}

func TestSignalExitWithUnknownOutcomeIsNeverResentBlindly(t *testing.T) {
	svc, rb := newSignalTestService(model.BotModeAuto)
	svc.positions["BTCUSDT"] = &positionInfo{entryPrice: 100, quantity: 0.01}
	book := newSignalOrderBook()
	signalClock(book)
	ex := newScriptedExchange()
	ctx := context.Background()

	ex.placeErr = timeoutErr{}
	if svc.signalTradeStep(ctx, book, "BTCUSDT", "SELL", 0.01, 90, ex) {
		t.Fatal("an unknown outcome must not report the exit as done")
	}
	if book.pending["BTCUSDT"] == nil || svc.tradesCount != 0 || len(rb.trades) != 0 {
		t.Fatal("unknown exit must stay pending and uncounted")
	}

	// Stop-loss fires again while the lookup cannot tell: nothing is sent.
	ex.lookupErr = errors.New("lookup timed out")
	for i := 0; i < 3; i++ {
		if svc.signalTradeStep(ctx, book, "BTCUSDT", "SELL", 0.01, 90, ex) {
			t.Fatal("exit reported done without confirmation")
		}
	}
	if len(ex.placed) != 1 {
		t.Fatalf("exit re-sent while its outcome was unknown: %v", ex.placed)
	}

	// The exchange did fill it: the next check closes the position without a
	// second order.
	ex.lookupErr = nil
	ex.status[ex.placed[0]] = gridOrderReport{state: gridOrderFilled, executedQty: 0.01}
	if !svc.signalTradeStep(ctx, book, "BTCUSDT", "SELL", 0.01, 90, ex) {
		t.Fatal("reconciled exit must be reported as done")
	}
	if len(ex.placed) != 1 || svc.tradesCount != 1 || book.pending["BTCUSDT"] != nil {
		t.Fatalf("placed=%v trades=%d pending=%v", ex.placed, svc.tradesCount, book.pending["BTCUSDT"])
	}
	if _, open := svc.positions["BTCUSDT"]; open {
		t.Fatal("filled exit must close the position")
	}
}

func TestSignalUnknownOrderNotFoundAfterGraceIsRetried(t *testing.T) {
	svc, _ := newSignalTestService(model.BotModeSignal)
	book := newSignalOrderBook()
	now := signalClock(book)
	ex := newScriptedExchange()
	ctx := context.Background()

	ex.placeErr = timeoutErr{}
	svc.signalTradeStep(ctx, book, "BTCUSDT", "BUY", 0.01, 100, ex)

	*now = now.Add(gridUnknownGrace - time.Second)
	if svc.signalTradeStep(ctx, book, "BTCUSDT", "BUY", 0.01, 100, ex) || len(ex.placed) != 1 {
		t.Fatalf("not-found inside grace must keep waiting: %v", ex.placed)
	}
	*now = now.Add(2 * time.Second)
	if !svc.signalTradeStep(ctx, book, "BTCUSDT", "BUY", 0.01, 100, ex) {
		t.Fatal("after grace the order is proven absent and the signal may be placed")
	}
	if len(ex.placed) != 2 || ex.placed[0] == ex.placed[1] || svc.tradesCount != 1 {
		t.Fatalf("placed=%v trades=%d", ex.placed, svc.tradesCount)
	}
}

func TestSignalOpenOrderIsPendingThenCancelledWhenStale(t *testing.T) {
	svc, _ := newSignalTestService(model.BotModeAuto)
	book := newSignalOrderBook()
	now := signalClock(book)
	ex := newScriptedExchange()
	ctx := context.Background()

	ex.placeResp = gridOrderReport{state: gridOrderOpen}
	if svc.signalTradeStep(ctx, book, "BTCUSDT", "BUY", 0.01, 100, ex) {
		t.Fatal("an open order is not a fill")
	}
	if len(svc.positions) != 0 || svc.tradesCount != 0 {
		t.Fatal("an open order must not open a position or be counted")
	}
	id := ex.placed[0]
	ex.status[id] = gridOrderReport{state: gridOrderOpen}

	*now = now.Add(gridOrderMaxAge)
	svc.signalTradeStep(ctx, book, "BTCUSDT", "BUY", 0.01, 100, ex)
	if len(ex.cancels) != 1 || ex.cancels[0] != id || len(ex.placed) != 1 {
		t.Fatalf("cancels=%v placed=%v", ex.cancels, ex.placed)
	}

	// Cancelled after a partial fill: the partial entry is tracked, and the
	// call proceeds with a new order since the old one is final.
	ex.status[id] = gridOrderReport{state: gridOrderDone, executedQty: 0.004}
	ex.placeResp = gridOrderReport{state: gridOrderFilled, executedQty: 0.01}
	svc.signalTradeStep(ctx, book, "BTCUSDT", "BUY", 0.01, 100, ex)
	if pos := svc.positions["BTCUSDT"]; pos == nil || pos.quantity != 0.014 {
		t.Fatalf("position = %+v", pos)
	}
	if svc.tradesCount != 2 {
		t.Fatalf("trades = %d, want 2", svc.tradesCount)
	}
}

func TestSignalSellIsCappedToTrackedPosition(t *testing.T) {
	svc, rb := newSignalTestService(model.BotModeAuto)
	svc.positions["BTCUSDT"] = &positionInfo{entryPrice: 100, quantity: 0.004}
	book := newSignalOrderBook()
	ex := &fakeGridExchange{}
	if !svc.signalTradeStep(context.Background(), book, "BTCUSDT", "SELL", 0.01, 100, ex) {
		t.Fatal("exit failed")
	}
	if _, open := svc.positions["BTCUSDT"]; open {
		t.Fatal("capped exit must close the position")
	}
	if len(rb.trades) != 1 || rb.trades[0].Quantity != 0.004 {
		t.Fatalf("exit must sell only the tracked 0.004, got %+v", rb.trades)
	}
}
