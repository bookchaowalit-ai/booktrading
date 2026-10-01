package service

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/port/input"
	"trading-bot-system/backend/internal/port/output"
)

type failingBotStatusRepo struct{ MockBotStatusRepository }

func (f *failingBotStatusRepo) SetActive(ctx context.Context, active bool) error {
	return errors.New("db unavailable")
}

// recordingSubscriber records the context handed to every subscription so a
// test can prove each run's goroutine is bound to its own lifetime.
type recordingSubscriber struct {
	MockRedisPublisher
	mu   sync.Mutex
	ctxs []context.Context
}

func (r *recordingSubscriber) SubscribeOrderSignals(ctx context.Context) (<-chan *output.OrderSignal, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.ctxs = append(r.ctxs, ctx)
	return make(chan *output.OrderSignal), nil
}

func (r *recordingSubscriber) snapshot() []context.Context {
	r.mu.Lock()
	defer r.mu.Unlock()
	return append([]context.Context(nil), r.ctxs...)
}

func validGrid() *input.BotStartParams {
	return &input.BotStartParams{
		Symbol:     "BTCUSDT",
		Quantity:   0.001,
		GridLevels: 5,
		LowerPrice: 90,
		UpperPrice: 110,
		Investment: 100,
		BotMode:    "GRID",
	}
}

func TestStartRejectsUnsafeGridParams(t *testing.T) {
	cases := map[string]func(p *input.BotStartParams){
		"zero grid levels":      func(p *input.BotStartParams) { p.GridLevels = 0 },
		"negative grid levels":  func(p *input.BotStartParams) { p.GridLevels = -3 },
		"zero quantity":         func(p *input.BotStartParams) { p.Quantity = 0 },
		"inverted range":        func(p *input.BotStartParams) { p.LowerPrice, p.UpperPrice = 110, 90 },
		"flat range":            func(p *input.BotStartParams) { p.UpperPrice = p.LowerPrice },
		"zero lower price":      func(p *input.BotStartParams) { p.LowerPrice = 0 },
		"explicit grid no symb": func(p *input.BotStartParams) { p.Symbol = "" },
	}
	for name, mutate := range cases {
		t.Run(name, func(t *testing.T) {
			svc := NewBotService(&MockBotStatusRepository{}, &MockRedisPublisher{}, &MockWebSocketBroadcaster{})
			p := validGrid()
			mutate(p)
			if err := svc.Start(context.Background(), p); err == nil {
				t.Fatal("expected Start to reject unsafe grid parameters")
			}
			if svc.IsRunning(context.Background()) {
				t.Fatal("bot must not be running after a rejected start")
			}
		})
	}
}

func TestStartGridWithValidParams(t *testing.T) {
	svc := NewBotService(&MockBotStatusRepository{}, &MockRedisPublisher{}, &MockWebSocketBroadcaster{})
	if err := svc.Start(context.Background(), validGrid()); err != nil {
		t.Fatalf("Start failed: %v", err)
	}
	if err := svc.Stop(context.Background()); err != nil {
		t.Fatalf("Stop failed: %v", err)
	}
}

func TestStartDoesNotLeaveBotRunningWhenStatusPersistFails(t *testing.T) {
	svc := NewBotService(&failingBotStatusRepo{}, &MockRedisPublisher{}, &MockWebSocketBroadcaster{})
	if err := svc.Start(context.Background(), nil); err == nil {
		t.Fatal("expected Start to fail when the status repository fails")
	}
	if svc.IsRunning(context.Background()) {
		t.Fatal("bot must not report running when start failed")
	}
}

func TestRestartDoesNotReviveStaleLoop(t *testing.T) {
	sub := &recordingSubscriber{}
	svc := NewBotService(&MockBotStatusRepository{}, sub, &MockWebSocketBroadcaster{})
	ctx := context.Background()

	if err := svc.Start(ctx, nil); err != nil {
		t.Fatalf("first Start failed: %v", err)
	}
	waitForSubscriptions(t, sub, 1)
	if err := svc.Stop(ctx); err != nil {
		t.Fatalf("Stop failed: %v", err)
	}
	if err := svc.Start(ctx, nil); err != nil {
		t.Fatalf("second Start failed: %v", err)
	}
	ctxs := waitForSubscriptions(t, sub, 2)

	if ctxs[0].Err() == nil {
		t.Fatal("first run's loop context must stay cancelled after a restart")
	}
	if ctxs[1].Err() != nil {
		t.Fatal("second run's loop context must be live")
	}
	if err := svc.Stop(ctx); err != nil {
		t.Fatalf("final Stop failed: %v", err)
	}
	if ctxs[1].Err() == nil {
		t.Fatal("second run's loop context must be cancelled by Stop")
	}
}

func waitForSubscriptions(t *testing.T, sub *recordingSubscriber, n int) []context.Context {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if ctxs := sub.snapshot(); len(ctxs) >= n {
			return ctxs
		}
		time.Sleep(5 * time.Millisecond)
	}
	t.Fatalf("expected %d subscriptions", n)
	return nil
}

func TestGridAction(t *testing.T) {
	grid := gridParams{symbol: "BTCUSDT", quantity: 1, gridLevels: 4, lowerPrice: 100, upperPrice: 200}
	// gridSize = 25 -> BUY at <=125, SELL at >=175
	cases := []struct {
		name  string
		grid  gridParams
		price float64
		want  string
	}{
		{"bottom band buys", grid, 110, "BUY"},
		{"band edge buys", grid, 125, "BUY"},
		{"middle waits", grid, 150, ""},
		{"top band sells", grid, 180, "SELL"},
		{"zero price never trades", grid, 0, ""},
		{"negative price never trades", grid, -1, ""},
		{"zero levels never trades", gridParams{gridLevels: 0, lowerPrice: 100, upperPrice: 200}, 50, ""},
		{"inverted range never trades", gridParams{gridLevels: 4, lowerPrice: 200, upperPrice: 100}, 50, ""},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, _ := gridAction(tc.grid, tc.price)
			if got != tc.want {
				t.Fatalf("gridAction(%v) = %q, want %q", tc.price, got, tc.want)
			}
		})
	}
}

func TestWithSignalDefaults(t *testing.T) {
	got := withSignalDefaults(input.SignalConfig{})
	if got.MinStrength != 0.5 || got.StopLossPct != 0.05 || got.TakeProfitPct != 0.10 {
		t.Fatalf("unexpected defaults: %+v", got)
	}
	custom := withSignalDefaults(input.SignalConfig{MinStrength: 0.8, StopLossPct: 0.02, TakeProfitPct: 0.03})
	if custom.MinStrength != 0.8 || custom.StopLossPct != 0.02 || custom.TakeProfitPct != 0.03 {
		t.Fatalf("explicit values must be preserved: %+v", custom)
	}
}

func TestResolveBotMode(t *testing.T) {
	if resolveBotMode(nil) != model.BotModeSignal {
		t.Fatal("nil params must default to signal mode")
	}
	if resolveBotMode(&input.BotStartParams{Symbol: "BTCUSDT"}) != model.BotModeGrid {
		t.Fatal("symbol without explicit mode implies grid mode")
	}
	if resolveBotMode(&input.BotStartParams{BotMode: "AUTO"}) != model.BotModeAuto {
		t.Fatal("AUTO must map to auto mode")
	}
	if resolveBotMode(&input.BotStartParams{BotMode: "bogus"}) != model.BotModeSignal {
		t.Fatal("unknown modes must fall back to signal mode")
	}
}
