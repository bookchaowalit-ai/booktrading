package websocket

import (
	"encoding/json"
	"log"
	"net/http"
	"sync"

	"github.com/gorilla/websocket"
	"trading-bot-system/backend/internal/domain/model"
)

// WebSocketBroadcasterImpl implements the WebSocketBroadcaster interface
type WebSocketBroadcasterImpl struct {
	clients    map[chan []byte]bool
	broadcast  chan []byte
	register   chan chan []byte
	unregister chan chan []byte
	mu         sync.RWMutex
	maxClients int
}

// NewWebSocketBroadcaster creates a new WebSocket broadcaster
func NewWebSocketBroadcaster(maxClients, queueSize int) *WebSocketBroadcasterImpl {
	return &WebSocketBroadcasterImpl{
		clients:    make(map[chan []byte]bool),
		broadcast:  make(chan []byte, queueSize),
		register:   make(chan chan []byte),
		unregister: make(chan chan []byte),
		maxClients: maxClients,
	}
}

// Run starts the broadcaster goroutine
func (w *WebSocketBroadcasterImpl) Run() {
	for {
		select {
		case client := <-w.register:
			w.mu.Lock()
			if len(w.clients) < w.maxClients {
				w.clients[client] = true
				log.Printf("WebSocket client connected. Total clients: %d", len(w.clients))
			} else {
				close(client)
				log.Println("WebSocket client rejected - max clients reached")
			}
			w.mu.Unlock()

		case client := <-w.unregister:
			w.mu.Lock()
			if _, ok := w.clients[client]; ok {
				delete(w.clients, client)
				close(client)
				log.Printf("WebSocket client disconnected. Total clients: %d", len(w.clients))
			}
			w.mu.Unlock()

		case message := <-w.broadcast:
			w.mu.RLock()
			for client := range w.clients {
				select {
				case client <- message:
				default:
					// Client buffer full, mark for removal
					go func(c chan []byte) {
						w.unregister <- c
					}(client)
				}
			}
			w.mu.RUnlock()
		}
	}
}

// BroadcastMarketData broadcasts market data to all connected clients
func (w *WebSocketBroadcasterImpl) BroadcastMarketData(data *model.MarketData) {
	message := map[string]interface{}{
		"type": "market_data",
		"data": data,
	}
	w.broadcastMessage(message)
}

// BroadcastBotStatus broadcasts bot status to all connected clients
func (w *WebSocketBroadcasterImpl) BroadcastBotStatus(status *model.BotStatus) {
	message := map[string]interface{}{
		"type": "bot_status",
		"data": status,
	}
	w.broadcastMessage(message)
}

// BroadcastOrderUpdate broadcasts order updates to all connected clients
func (w *WebSocketBroadcasterImpl) BroadcastOrderUpdate(order *model.Order) {
	message := map[string]interface{}{
		"type": "order_update",
		"data": order,
	}
	w.broadcastMessage(message)
}

// RegisterClient registers a new WebSocket client
func (w *WebSocketBroadcasterImpl) RegisterClient(ch chan []byte) {
	w.register <- ch
}

// UnregisterClient unregisters a WebSocket client
func (w *WebSocketBroadcasterImpl) UnregisterClient(ch chan []byte) {
	w.unregister <- ch
}

func (w *WebSocketBroadcasterImpl) broadcastMessage(message map[string]interface{}) {
	jsonData, err := json.Marshal(message)
	if err != nil {
		log.Printf("Failed to marshal message: %v", err)
		return
	}

	select {
	case w.broadcast <- jsonData:
	default:
		log.Println("Broadcast channel full, dropping message")
	}
}

// Upgrader for WebSocket connections
var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin: func(r *http.Request) bool {
		return true // Allow all origins for now
	},
}

// WSHandler handles WebSocket connections
type WSHandler struct {
	broadcaster *WebSocketBroadcasterImpl
}

// NewWSHandler creates a new WebSocket handler
func NewWSHandler(broadcaster *WebSocketBroadcasterImpl) *WSHandler {
	return &WSHandler{
		broadcaster: broadcaster,
	}
}

// HandleWebSocket handles WebSocket upgrade and connection
func (h *WSHandler) HandleWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("Failed to upgrade connection: %v", err)
		return
	}

	clientChan := make(chan []byte, 100)
	h.broadcaster.RegisterClient(clientChan)

	// Ensure client is unregistered on disconnect
	defer func() {
		h.broadcaster.UnregisterClient(clientChan)
		conn.Close()
	}()

	// Handle incoming messages (ping/pong, commands, etc.)
	go h.handleMessages(conn)

	// Send messages to client
	for message := range clientChan {
		if err := conn.WriteMessage(websocket.TextMessage, message); err != nil {
			log.Printf("Failed to send message: %v", err)
			return
		}
	}
}

func (h *WSHandler) handleMessages(conn *websocket.Conn) {
	for {
		_, message, err := conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				log.Printf("WebSocket error: %v", err)
			}
			break
		}

		// Process incoming message
		var msg map[string]interface{}
		if err := json.Unmarshal(message, &msg); err != nil {
			continue
		}

		// Handle different message types
		msgType, ok := msg["type"].(string)
		if !ok {
			continue
		}

		switch msgType {
		case "ping":
			// Respond with pong
			response := map[string]string{"type": "pong"}
			jsonData, _ := json.Marshal(response)
			conn.WriteMessage(websocket.TextMessage, jsonData)
		case "subscribe":
			// Handle subscription requests
			log.Printf("Subscription request: %v", msg)
		}
	}
}

// GetClientCount returns the number of connected clients
func (w *WebSocketBroadcasterImpl) GetClientCount() int {
	w.mu.RLock()
	defer w.mu.RUnlock()
	return len(w.clients)
}
