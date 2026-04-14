package service

import (
	"context"
	"sync"

	"trading-bot-system/backend/internal/logger"
)

// EventType represents the type of system event
type EventType string

const (
	EventBotStart    EventType = "bot_start"
	EventBotStop     EventType = "bot_stop"
	EventTradeExec   EventType = "trade_executed"
	EventRiskAlert   EventType = "risk_alert"
	EventPaperTrade  EventType = "paper_trade"
	EventSystemError EventType = "system_error"
)

// Event represents a system event
type Event struct {
	Type EventType
	Data map[string]any
}

// Handler is a function that processes events
type EventHandler func(ctx context.Context, event Event)

// EventBus is a simple in-memory event bus
type EventBus struct {
	mu       sync.RWMutex
	handlers map[EventType][]EventHandler
}

// NewEventBus creates a new event bus
func NewEventBus() *EventBus {
	return &EventBus{
		handlers: make(map[EventType][]EventHandler),
	}
}

// Subscribe registers a handler for an event type
func (bus *EventBus) Subscribe(eventType EventType, handler EventHandler) {
	bus.mu.Lock()
	defer bus.mu.Unlock()
	bus.handlers[eventType] = append(bus.handlers[eventType], handler)
}

// Publish fires an event to all registered handlers (async)
func (bus *EventBus) Publish(ctx context.Context, event Event) {
	bus.mu.RLock()
	handlers := make([]EventHandler, len(bus.handlers[event.Type]))
	copy(handlers, bus.handlers[event.Type])
	bus.mu.RUnlock()

	for _, h := range handlers {
		go func(handler EventHandler) {
			defer func() {
				if r := recover(); r != nil {
					logger.Error("Event handler panicked", "event", event.Type, "panic", r)
				}
			}()
			handler(ctx, event)
		}(h)
	}
}
