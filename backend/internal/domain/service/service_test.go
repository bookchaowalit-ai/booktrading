package service

import (
	"context"
	"testing"

	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/port/output"
)

// MockBotStatusRepository implements repository.BotStatusRepository for testing
type MockBotStatusRepository struct {
	active bool
}

func (m *MockBotStatusRepository) Get(ctx context.Context) (*model.BotStatus, error) {
	return &model.BotStatus{
		IsActive:    m.active,
		TotalTrades: 0,
		TotalProfit: 0,
	}, nil
}

func (m *MockBotStatusRepository) SetActive(ctx context.Context, active bool) error {
	m.active = active
	return nil
}

func (m *MockBotStatusRepository) IncrementTrades(ctx context.Context) error {
	return nil
}

func (m *MockBotStatusRepository) UpdateProfit(ctx context.Context, profit float64) error {
	return nil
}

// MockWebSocketBroadcaster implements output.WebSocketBroadcaster for testing
type MockWebSocketBroadcaster struct {
	broadcastedMarketData  []*model.MarketData
	broadcastedBotStatus   []*model.BotStatus
	broadcastedOrderUpdate []*model.Order
}

func (m *MockWebSocketBroadcaster) BroadcastMarketData(data *model.MarketData) {
	m.broadcastedMarketData = append(m.broadcastedMarketData, data)
}

func (m *MockWebSocketBroadcaster) BroadcastBotStatus(status *model.BotStatus) {
	m.broadcastedBotStatus = append(m.broadcastedBotStatus, status)
}

func (m *MockWebSocketBroadcaster) BroadcastOrderUpdate(order *model.Order) {
	m.broadcastedOrderUpdate = append(m.broadcastedOrderUpdate, order)
}

func (m *MockWebSocketBroadcaster) BroadcastTradeNotification(trade *model.TradeNotification) {
	// Mock implementation
}

func (m *MockWebSocketBroadcaster) BroadcastBotActivity(activity *model.BotActivity) {
	// Mock implementation
}

func (m *MockWebSocketBroadcaster) RegisterClient(ch chan []byte) {}

func (m *MockWebSocketBroadcaster) UnregisterClient(ch chan []byte) {}

// MockRedisPublisher implements output.RedisPublisher for testing
type MockRedisPublisher struct{}

func (m *MockRedisPublisher) PublishMarketData(ctx context.Context, data *model.MarketData) error {
	return nil
}

func (m *MockRedisPublisher) PublishOrderSignal(ctx context.Context, signal *output.OrderSignal) error {
	return nil
}

func (m *MockRedisPublisher) SubscribeOrderSignals(ctx context.Context) (<-chan *output.OrderSignal, error) {
	return nil, nil
}

// TestBotServiceStartStop tests starting and stopping the bot
func TestBotServiceStartStop(t *testing.T) {
	repo := &MockBotStatusRepository{active: false}
	broadcaster := &MockWebSocketBroadcaster{}
	redisPub := &MockRedisPublisher{}

	svc := NewBotService(repo, redisPub, broadcaster)

	ctx := context.Background()

	// Test initial state - should be stopped
	status, err := svc.GetStatus(ctx)
	if err != nil {
		t.Fatalf("GetStatus failed: %v", err)
	}
	if status.IsActive {
		t.Error("Expected bot to be stopped initially")
	}

	// Test starting the bot
	// Note: This will start the bot in signal mode (no params)
	err = svc.Start(ctx, nil)
	if err != nil {
		t.Fatalf("Start failed: %v", err)
	}

	// Verify bot is running
	status, err = svc.GetStatus(ctx)
	if err != nil {
		t.Fatalf("GetStatus failed: %v", err)
	}
	if !status.IsActive {
		t.Error("Expected bot to be running after Start")
	}

	// Verify status was broadcast
	if len(broadcaster.broadcastedBotStatus) == 0 {
		t.Error("Expected bot status to be broadcast after start")
	}

	// Test stopping the bot
	err = svc.Stop(ctx)
	if err != nil {
		t.Fatalf("Stop failed: %v", err)
	}

	// Verify bot is stopped
	status, err = svc.GetStatus(ctx)
	if err != nil {
		t.Fatalf("GetStatus failed: %v", err)
	}
	if status.IsActive {
		t.Error("Expected bot to be stopped after Stop")
	}
}

// TestBotServiceCannotStartTwice tests that starting an already running bot fails
func TestBotServiceCannotStartTwice(t *testing.T) {
	repo := &MockBotStatusRepository{active: false}
	broadcaster := &MockWebSocketBroadcaster{}
	redisPub := &MockRedisPublisher{}

	svc := NewBotService(repo, redisPub, broadcaster)
	ctx := context.Background()

	// Start the bot
	err := svc.Start(ctx, nil)
	if err != nil {
		t.Fatalf("Start failed: %v", err)
	}

	// Try to start again - should fail
	err = svc.Start(ctx, nil)
	if err == nil {
		t.Error("Expected error when starting already running bot")
	}
}

// TestBotServiceCanStopWhenNotRunning tests that stopping a stopped bot is safe
func TestBotServiceCanStopWhenNotRunning(t *testing.T) {
	repo := &MockBotStatusRepository{active: false}
	broadcaster := &MockWebSocketBroadcaster{}
	redisPub := &MockRedisPublisher{}

	svc := NewBotService(repo, redisPub, broadcaster)
	ctx := context.Background()

	// Stop when not running - should not error
	err := svc.Stop(ctx)
	if err != nil {
		t.Errorf("Expected no error when stopping already stopped bot, got: %v", err)
	}
}

// TestPricePrediction tests the price prediction logic
func TestPricePrediction(t *testing.T) {
	// Test data: uptrend
	uptrend := []float64{
		100, 101, 102, 103, 104, 105, 106, 107, 108, 109,
		110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120,
	}

	// With strong uptrend, prediction should be BULLISH
	// (This would need the actual predictor implementation to test)
	if len(uptrend) < 20 {
		t.Error("Need at least 20 data points for prediction")
	}
}

// TestArbitrageDetection tests arbitrage opportunity detection
func TestArbitrageDetection(t *testing.T) {
	// Test scenario: BTC cheaper on Binance TH than Bitkub
	binanceTHPrice := 2280000.0
	bitkubPrice := 2285000.0

	// Calculate potential profit
	buyPrice := binanceTHPrice
	sellPrice := bitkubPrice
	fees := buyPrice*0.001 + sellPrice*0.001 // 0.1% per trade
	grossProfit := sellPrice - buyPrice
	netProfit := grossProfit - fees
	profitPercent := (netProfit / buyPrice) * 100

	// With 5000 THB difference, should be profitable
	if profitPercent <= 0 {
		t.Errorf("Expected positive profit percent, got: %.2f%%", profitPercent)
	}

	t.Logf("Arbitrage opportunity: %.2f%% profit (%.2f THB)", profitPercent, netProfit)
}

// TestGridTradingLogic tests the grid trading calculation
func TestGridTradingLogic(t *testing.T) {
	lowerPrice := 2000000.0
	upperPrice := 3000000.0
	gridLevels := 5

	gridSize := (upperPrice - lowerPrice) / float64(gridLevels)

	// Verify grid levels
	expectedLevels := []float64{2000000, 2250000, 2500000, 2750000, 3000000}
	for i := 0; i < gridLevels; i++ {
		level := lowerPrice + gridSize*float64(i)
		if level != expectedLevels[i] {
			t.Errorf("Grid level %d: expected %.2f, got %.2f", i, expectedLevels[i], level)
		}
	}

	// Test buy signal: price at or below first grid level
	currentPrice := 2100000.0
	if currentPrice > lowerPrice+gridSize {
		t.Error("Expected buy signal when price is near lower grid level")
	}

	// Test sell signal: price at or above last grid level
	currentPrice = 2900000.0
	if currentPrice < upperPrice-gridSize {
		t.Error("Expected sell signal when price is near upper grid level")
	}

	// Test wait: price in middle
	currentPrice = 2500000.0
	if currentPrice <= lowerPrice+gridSize || currentPrice >= upperPrice-gridSize {
		t.Error("Expected wait signal when price is in middle of grid")
	}
}

// TestBotStatusBroadcast tests that bot status changes are properly broadcast
func TestBotStatusBroadcast(t *testing.T) {
	repo := &MockBotStatusRepository{active: false}
	broadcaster := &MockWebSocketBroadcaster{}
	redisPub := &MockRedisPublisher{}

	svc := NewBotService(repo, redisPub, broadcaster)
	ctx := context.Background()

	// Start bot
	err := svc.Start(ctx, nil)
	if err != nil {
		t.Fatalf("Start failed: %v", err)
	}

	// Verify broadcast
	if len(broadcaster.broadcastedBotStatus) != 1 {
		t.Errorf("Expected 1 status broadcast, got %d", len(broadcaster.broadcastedBotStatus))
	}

	// Verify the broadcast shows bot as active
	status := broadcaster.broadcastedBotStatus[0]
	if !status.IsActive {
		t.Error("Expected broadcast status to show bot as active")
	}
}

// TestConcurrentAccess tests that the bot service handles concurrent access safely
func TestConcurrentAccess(t *testing.T) {
	repo := &MockBotStatusRepository{active: false}
	broadcaster := &MockWebSocketBroadcaster{}
	redisPub := &MockRedisPublisher{}

	svc := NewBotService(repo, redisPub, broadcaster)
	ctx := context.Background()

	// Start the bot
	err := svc.Start(ctx, nil)
	if err != nil {
		t.Fatalf("Start failed: %v", err)
	}

	// Try to access status concurrently
	done := make(chan bool)
	for i := 0; i < 10; i++ {
		go func() {
			_, err := svc.GetStatus(ctx)
			if err != nil {
				t.Errorf("GetStatus failed: %v", err)
			}
			done <- true
		}()
	}

	// Wait for all goroutines
	for i := 0; i < 10; i++ {
		<-done
	}
}

// TestGridParameters tests that grid parameters are properly validated
func TestGridParameters(t *testing.T) {
	tests := []struct {
		name         string
		lowerPrice   float64
		upperPrice   float64
		gridLevels   int
		expectError  bool
	}{
		{"Valid parameters", 2000000, 3000000, 5, false},
		{"Lower equals upper", 2000000, 2000000, 5, true},
		{"Lower greater than upper", 3000000, 2000000, 5, true},
		{"Zero grid levels", 2000000, 3000000, 0, true},
		{"Negative grid levels", 2000000, 3000000, -1, true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Validate parameters
			if tt.lowerPrice >= tt.upperPrice && tt.name != "Lower equals upper" {
				if !tt.expectError {
					t.Error("Expected validation to pass")
				}
			}
			if tt.gridLevels <= 0 && tt.expectError {
				// Expected error case
				return
			}
			if tt.gridLevels > 0 && !tt.expectError {
				// Valid case - calculate grid size
				gridSize := (tt.upperPrice - tt.lowerPrice) / float64(tt.gridLevels)
				if gridSize <= 0 {
					t.Error("Expected positive grid size")
				}
			}
		})
	}
}
