package service

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/logger"
)

// AlertService manages sending notifications to external channels
type AlertService struct {
	mu     sync.RWMutex
	config *model.AlertConfig
	queue  []*model.Alert
	client *http.Client
}

// NewAlertService creates a new alert service
func NewAlertService(config *model.AlertConfig) *AlertService {
	if config == nil {
		config = &model.AlertConfig{Enabled: false}
	}
	return &AlertService{
		config: config,
		queue:  make([]*model.Alert, 0),
		client: &http.Client{Timeout: 10 * time.Second},
	}
}

// Send sends an alert immediately
func (s *AlertService) Send(ctx context.Context, alertType model.AlertType, title, message string, data map[string]any) error {
	if !s.config.Enabled {
		return nil // Silently skip if alerts are disabled
	}

	// Check if this alert type is enabled
	if !s.isTypeEnabled(alertType) {
		return nil
	}

	alert := &model.Alert{
		ID:        uuid.New().String(),
		Type:      alertType,
		Title:     title,
		Message:   message,
		Data:      data,
		CreatedAt: time.Now(),
	}

	// Send to all enabled channels
	var errs []string

	if s.config.DiscordWebhookURL != "" {
		if err := s.sendToDiscord(ctx, alert); err != nil {
			errs = append(errs, fmt.Sprintf("discord: %v", err))
			logger.Error("Failed to send Discord alert", "error", err, "type", alertType)
		}
	}

	if s.config.TelegramBotToken != "" && s.config.TelegramChatID != "" {
		if err := s.sendToTelegram(ctx, alert); err != nil {
			errs = append(errs, fmt.Sprintf("telegram: %v", err))
			logger.Error("Failed to send Telegram alert", "error", err, "type", alertType)
		}
	}

	if s.config.CustomWebhookURL != "" {
		if err := s.sendToWebhook(ctx, alert); err != nil {
			errs = append(errs, fmt.Sprintf("webhook: %v", err))
			logger.Error("Failed to send webhook alert", "error", err, "type", alertType)
		}
	}

	if len(errs) > 0 {
		alert.Error = strings.Join(errs, "; ")
		return fmt.Errorf("alert delivery failures: %s", alert.Error)
	}

	alert.Sent = true
	now := time.Now()
	alert.SentAt = &now

	s.mu.Lock()
	s.queue = append(s.queue, alert)
	s.mu.Unlock()

	return nil
}

// isTypeEnabled checks if the alert type is enabled in config
func (s *AlertService) isTypeEnabled(alertType model.AlertType) bool {
	switch alertType {
	case model.AlertTypeTrade:
		return s.config.NotifyOnTrade
	case model.AlertTypeBotStart, model.AlertTypeBotStop:
		return s.config.NotifyOnBotStart
	case model.AlertTypeError:
		return s.config.NotifyOnError
	case model.AlertTypeRisk:
		return s.config.NotifyOnRisk
	case model.AlertTypePrice:
		return s.config.NotifyOnPrice
	}
	return false
}

// sendToDiscord sends a message via Discord webhook
func (s *AlertService) sendToDiscord(ctx context.Context, alert *model.Alert) error {
	// Discord embed format
	payload := map[string]any{
		"content": fmt.Sprintf("**%s**\n%s", alert.Title, alert.Message),
		"embeds": []map[string]any{
			{
				"title":       alert.Title,
				"description": alert.Message,
				"color":       s.alertColor(alert.Type),
				"timestamp":   alert.CreatedAt.Format(time.RFC3339),
				"footer": map[string]string{
					"text": "Trading Bot System",
				},
			},
		},
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, s.config.DiscordWebhookURL, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := s.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("discord returned %d: %s", resp.StatusCode, string(respBody))
	}

	return nil
}

// sendToTelegram sends a message via Telegram Bot API
func (s *AlertService) sendToTelegram(ctx context.Context, alert *model.Alert) error {
	text := fmt.Sprintf("🔔 *%s*\n\n%s", alert.Title, alert.Message)

	payload := map[string]string{
		"chat_id":                  s.config.TelegramChatID,
		"text":                     text,
		"parse_mode":               "Markdown",
		"disable_web_page_preview": "true",
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	endpoint := fmt.Sprintf("https://api.telegram.org/bot%s/sendMessage", s.config.TelegramBotToken)

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := s.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("telegram returned %d: %s", resp.StatusCode, string(respBody))
	}

	return nil
}

// sendToWebhook sends a POST request to a custom webhook URL
func (s *AlertService) sendToWebhook(ctx context.Context, alert *model.Alert) error {
	payload := map[string]any{
		"type":       string(alert.Type),
		"title":      alert.Title,
		"message":    alert.Message,
		"data":       alert.Data,
		"timestamp":  alert.CreatedAt.Format(time.RFC3339),
		"source":     "trading-bot",
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, s.config.CustomWebhookURL, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := s.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("webhook returned %d: %s", resp.StatusCode, string(respBody))
	}

	return nil
}

// SendTest sends a test alert to verify configuration
func (s *AlertService) SendTest(ctx context.Context) error {
	return s.Send(ctx, model.AlertTypeBotStart, "Test Alert", "This is a test alert from the Trading Bot System. If you received this, your notification configuration is working correctly.", nil)
}

// GetHistory returns recent alerts
func (s *AlertService) GetHistory(limit int) []*model.Alert {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if limit <= 0 || limit > len(s.queue) {
		limit = len(s.queue)
	}

	result := make([]*model.Alert, limit)
	copy(result, s.queue[len(s.queue)-limit:])
	return result
}

// UpdateConfig updates the alert configuration
func (s *AlertService) UpdateConfig(config *model.AlertConfig) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.config = config
}

// GetConfig returns the current alert configuration
func (s *AlertService) GetConfig() *model.AlertConfig {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.config
}

// alertColor returns a Discord color based on alert type
func (s *AlertService) alertColor(alertType model.AlertType) int {
	switch alertType {
	case model.AlertTypeTrade:
		return 0x00FF00 // Green
	case model.AlertTypeBotStart:
		return 0x0099FF // Blue
	case model.AlertTypeBotStop:
		return 0xFF9900 // Orange
	case model.AlertTypeError:
		return 0xFF0000 // Red
	case model.AlertTypeRisk:
		return 0xFF3300 // Red-orange
	case model.AlertTypePrice:
		return 0x9900FF // Purple
	default:
		return 0x808080 // Gray
	}
}

// SendPriceAlert sends a price alert notification
func (s *AlertService) SendPriceAlert(ctx context.Context, symbol string, price float64, direction string) error {
	return s.Send(ctx, model.AlertTypePrice,
		fmt.Sprintf("📈 %s Price Alert", symbol),
		fmt.Sprintf("%s reached **$%.2f**", symbol, price),
		map[string]any{"symbol": symbol, "price": price, "direction": direction},
	)
}

// SendTradeAlert sends a trade execution notification
func (s *AlertService) SendTradeAlert(ctx context.Context, symbol, side string, quantity, price, pnl float64) error {
	emoji := "🟢"
	if side == "SELL" {
		emoji = "🔴"
	}

	title := fmt.Sprintf("%s %s Executed", emoji, side)
	msg := fmt.Sprintf("Sold/Bought **%.6f %s** at **$%.2f**", quantity, symbol, price)
	if pnl != 0 {
		msg += fmt.Sprintf("\nPnL: **$%.2f**", pnl)
	}

	return s.Send(ctx, model.AlertTypeTrade, title, msg,
		map[string]any{"symbol": symbol, "side": side, "quantity": quantity, "price": price, "pnl": pnl},
	)
}

// SendBotStatusAlert sends bot start/stop notification
func (s *AlertService) SendBotStatusAlert(ctx context.Context, started bool, symbol string, reason string) error {
	var alertType model.AlertType
	var title, msg string

	if started {
		alertType = model.AlertTypeBotStart
		title = "🤖 Bot Started"
		msg = fmt.Sprintf("Trading bot started for **%s**", symbol)
	} else {
		alertType = model.AlertTypeBotStop
		title = "⏹️ Bot Stopped"
		msg = fmt.Sprintf("Trading bot stopped for **%s**", symbol)
	}

	if reason != "" {
		msg += fmt.Sprintf("\nReason: %s", reason)
	}

	return s.Send(ctx, alertType, title, msg, map[string]any{"symbol": symbol, "reason": reason})
}

// SendErrorAlert sends an error notification
func (s *AlertService) SendErrorAlert(ctx context.Context, err error, context string) error {
	return s.Send(ctx, model.AlertTypeError,
		"❌ System Error",
		fmt.Sprintf("Error in **%s**: %s", context, err.Error()),
		map[string]any{"context": context, "error": err.Error()},
	)
}

// SendRiskAlert sends a risk limit warning
func (s *AlertService) SendRiskAlert(ctx context.Context, metric, value, limit string) error {
	return s.Send(ctx, model.AlertTypeRisk,
		"⚠️ Risk Limit Warning",
		fmt.Sprintf("%s has reached **%s** (limit: %s). Bot may stop soon.", metric, value, limit),
		map[string]any{"metric": metric, "value": value, "limit": limit},
	)
}
