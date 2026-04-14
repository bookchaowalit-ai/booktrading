package service

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"trading-bot-system/backend/internal/logger"
)

// TelegramBotService manages the Telegram bot interface
type TelegramBotService struct {
	botToken     string
	botURL       string
	httpClient   *http.Client
	pool         *pgxpool.Pool
	mu           sync.RWMutex
	offset       int64
	running      bool
	ctx          context.Context
	cancel       context.CancelFunc

	// Callbacks to other services
	statusCallback   func() map[string]any // returns bot status
	balanceCallback  func() map[string]any // returns portfolio balance
	pnlCallback      func() map[string]any // returns PnL metrics
	startBotCallback func() error
	stopBotCallback  func() error
	paperCallback    func() map[string]any // returns paper trading portfolio
}

// NewTelegramBotService creates a new Telegram bot service
func NewTelegramBotService(
	botToken string,
	pool *pgxpool.Pool,
	statusCallback func() map[string]any,
	balanceCallback func() map[string]any,
	pnlCallback func() map[string]any,
	startBotCallback func() error,
	stopBotCallback func() error,
	paperCallback func() map[string]any,
) *TelegramBotService {
	ctx, cancel := context.WithCancel(context.Background())
	return &TelegramBotService{
		botToken:         botToken,
		botURL:           fmt.Sprintf("https://api.telegram.org/bot%s", botToken),
		httpClient:       &http.Client{Timeout: 10 * time.Second},
		pool:             pool,
		ctx:              ctx,
		cancel:           cancel,
		statusCallback:   statusCallback,
		balanceCallback:  balanceCallback,
		pnlCallback:      pnlCallback,
		startBotCallback: startBotCallback,
		stopBotCallback:  stopBotCallback,
		paperCallback:    paperCallback,
	}
}

// Start begins polling for updates
func (s *TelegramBotService) Start() error {
	if s.botToken == "" {
		logger.Warn("Telegram bot token not set, Telegram integration disabled")
		return nil
	}

	s.running = true

	// Get initial offset
	if err := s.deleteWebhook(); err != nil {
		logger.Error("Failed to delete webhook", "error", err)
	}

	go s.pollUpdates()
	logger.Info("Telegram bot started")
	return nil
}

// Stop stops polling
func (s *TelegramBotService) Stop() {
	s.cancel()
	s.running = false
	logger.Info("Telegram bot stopped")
}

// deleteWebhook removes any existing webhook
func (s *TelegramBotService) deleteWebhook() error {
	resp, err := s.httpClient.Get(s.botURL + "/deleteWebhook")
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	return nil
}

// pollUpdates continuously polls for new messages
func (s *TelegramBotService) pollUpdates() {
	for {
		select {
		case <-s.ctx.Done():
			return
		default:
			updates, err := s.getUpdates(s.offset, 100, 30)
			if err != nil {
				logger.Error("Failed to get updates", "error", err)
				time.Sleep(5 * time.Second)
				continue
			}

			for _, update := range updates {
				if update.ID >= s.offset {
					s.offset = update.ID + 1
				}
				if update.Message != nil {
					s.handleMessage(update.Message)
				}
			}
		}
	}
}

type telegramUpdate struct {
	ID      int64           `json:"update_id"`
	Message *telegramMessage `json:"message"`
}

type telegramMessage struct {
	ChatID int64 `json:"chat_id"`
	From   struct {
		ID        int64  `json:"id"`
		Username  string `json:"username"`
		FirstName string `json:"first_name"`
		LastName  string `json:"last_name"`
	} `json:"from"`
	Text string `json:"text"`
	Date int64  `json:"date"`
}

type telegramResponse struct {
	OK     bool             `json:"ok"`
	Result []telegramUpdate `json:"result"`
}

// getUpdates fetches updates from Telegram API
func (s *TelegramBotService) getUpdates(offset int64, limit int, timeout int) ([]telegramUpdate, error) {
	url := fmt.Sprintf("%s/getUpdates?offset=%d&limit=%d&timeout=%d",
		s.botURL, offset, limit, timeout)

	resp, err := s.httpClient.Get(url)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	var result telegramResponse
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, err
	}

	if !result.OK {
		return nil, fmt.Errorf("telegram API returned error")
	}

	return result.Result, nil
}

// sendMessage sends a text message to a chat
func (s *TelegramBotService) sendMessage(chatID int64, text string) error {
	url := fmt.Sprintf("%s/sendMessage?chat_id=%d&text=%s&parse_mode=Markdown",
		s.botURL, chatID, urlEncode(text))

	resp, err := s.httpClient.Post(url, "", nil)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	return nil
}

// handleMessage processes incoming messages and sends responses
func (s *TelegramBotService) handleMessage(msg *telegramMessage) {
	if msg.Text == "" {
		return
	}

	text := strings.TrimSpace(msg.Text)
	chatID := msg.ChatID

	// Check authorization
	authorized, err := s.isAuthorized(msg.From.ID)
	if err != nil {
		logger.Error("Failed to check telegram authorization", "error", err)
		s.sendMessage(chatID, "❌ Error checking authorization. Please try again.")
		return
	}

	if !authorized {
		s.sendMessage(chatID, "🔒 Your Telegram account is not authorized to access the trading bot. Please contact an administrator for access.")
		return
	}

	command := strings.ToLower(text)

	switch {
	case command == "/start":
		s.sendMessage(chatID, s.getWelcomeMessage())

	case command == "/help":
		s.sendMessage(chatID, s.getHelpMessage())

	case command == "/status":
		s.handleStatus(chatID)

	case command == "/balance":
		s.handleBalance(chatID)

	case command == "/pnl":
		s.handlePnL(chatID)

	case command == "/startbot":
		s.handleStartBot(chatID)

	case command == "/stopbot":
		s.handleStopBot(chatID)

	case command == "/paper":
		s.handlePaperTrading(chatID)

	default:
		s.sendMessage(chatID, fmt.Sprintf("⚠️ Unknown command: `%s`\n\nType /help for available commands.", text))
	}
}

func (s *TelegramBotService) getWelcomeMessage() string {
	return `🤖 *Trading Bot Control Panel*

Welcome! Here you can monitor and control your trading bot from Telegram.

Type */help* to see all available commands.`
}

func (s *TelegramBotService) getHelpMessage() string {
	return `📋 *Available Commands*

/status — Check bot status and runtime info
/balance — View exchange portfolio balance
/pnl — View profit & loss metrics
/startbot — Start the trading bot
/stopbot — Stop the trading bot
/paper — View paper trading portfolio
/help — Show this help message`
}

func (s *TelegramBotService) handleStatus(chatID int64) {
	status := s.statusCallback()

	msg := fmt.Sprintf(`🤖 *Bot Status*

Status: %v
Started: %v
Total Trades: %v
Total PnL: $%v`,
		status["isActive"],
		status["startedAt"],
		status["totalTrades"],
		status["totalProfit"],
	)

	s.sendMessage(chatID, msg)
}

func (s *TelegramBotService) handleBalance(chatID int64) {
	balance := s.balanceCallback()

	msg := "💰 *Portfolio Balance*\n\n"
	if balances, ok := balance["balances"].([]map[string]any); ok {
		for _, b := range balances {
			symbol := b["symbol"]
			bal := b["balance"]
			msg += fmt.Sprintf("%s: %.6f\n", symbol, bal)
		}
	} else {
		msg += "No balances available."
	}

	s.sendMessage(chatID, msg)
}

func (s *TelegramBotService) handlePnL(chatID int64) {
	pnl := s.pnlCallback()

	msg := fmt.Sprintf(`📊 *Profit & Loss*

Win Rate: %.1f%%
Profit Factor: %.2f
Avg Win: $%.2f
Avg Loss: $%.2f
Best Trade: $%.2f
Worst Trade: $%.2f
Sharpe Ratio: %.2f`,
		pnl["winRate"],
		pnl["profitFactor"],
		pnl["avgWin"],
		pnl["avgLoss"],
		pnl["bestTrade"],
		pnl["worstTrade"],
		pnl["sharpeRatio"],
	)

	s.sendMessage(chatID, msg)
}

func (s *TelegramBotService) handleStartBot(chatID int64) {
	err := s.startBotCallback()
	if err != nil {
		s.sendMessage(chatID, fmt.Sprintf("❌ Failed to start bot: %s", err.Error()))
		return
	}
	s.sendMessage(chatID, "✅ Trading bot started successfully!")
}

func (s *TelegramBotService) handleStopBot(chatID int64) {
	err := s.stopBotCallback()
	if err != nil {
		s.sendMessage(chatID, fmt.Sprintf("❌ Failed to stop bot: %s", err.Error()))
		return
	}
	s.sendMessage(chatID, "⏹️ Trading bot stopped successfully!")
}

func (s *TelegramBotService) handlePaperTrading(chatID int64) {
	portfolio := s.paperCallback()

	msg := fmt.Sprintf(`📄 *Paper Trading Portfolio*

Total Value: $%.2f
Initial Balance: $%.2f
Total PnL: $%.2f (%.2f%%)
Win Rate: %dW / %dL
Total Trades: %d`,
		portfolio["totalValue"],
		portfolio["initialBalance"],
		portfolio["totalPnL"],
		portfolio["totalPnLPercent"],
		portfolio["winTrades"],
		portfolio["lossTrades"],
		portfolio["totalTrades"],
	)

	s.sendMessage(chatID, msg)
}

func (s *TelegramBotService) isAuthorized(telegramID int64) (bool, error) {
	var authorized bool
	err := s.pool.QueryRow(s.ctx,
		"SELECT is_authorized FROM telegram_users WHERE telegram_id = $1",
		telegramID,
	).Scan(&authorized)

	if err != nil {
		// User not found in DB
		return false, nil
	}

	return authorized, nil
}

// AuthorizeUser adds or updates a telegram user's authorization
func (s *TelegramBotService) AuthorizeUser(telegramID int64, username, firstName, lastName string, authorizedBy string) error {
	_, err := s.pool.Exec(s.ctx, `
		INSERT INTO telegram_users (telegram_id, username, first_name, last_name, is_authorized, authorized_by, updated_at)
		VALUES ($1, $2, $3, $4, true, $5, NOW())
		ON CONFLICT (telegram_id) DO UPDATE SET
			username = $2,
			first_name = $3,
			last_name = $4,
			is_authorized = true,
			authorized_by = $5,
			updated_at = NOW()
	`, telegramID, username, firstName, lastName, authorizedBy)

	if err != nil {
		return fmt.Errorf("failed to authorize user: %w", err)
	}

	logger.Info("Authorized Telegram user", "telegram_id", telegramID, "username", username)
	return nil
}

func urlEncode(s string) string {
	// Simple URL encoding for markdown text
	s = strings.ReplaceAll(s, " ", "+")
	s = strings.ReplaceAll(s, "\n", "%0A")
	s = strings.ReplaceAll(s, "*", "%2A")
	s = strings.ReplaceAll(s, "_", "%5F")
	s = strings.ReplaceAll(s, "[", "%5B")
	s = strings.ReplaceAll(s, "]", "%5D")
	s = strings.ReplaceAll(s, "(", "%28")
	s = strings.ReplaceAll(s, ")", "%29")
	s = strings.ReplaceAll(s, "{", "%7B")
	s = strings.ReplaceAll(s, "}", "%7D")
	s = strings.ReplaceAll(s, "#", "%23")
	return s
}
