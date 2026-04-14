package model

import "time"

// AlertType represents the type of alert notification
type AlertType string

const (
	AlertTypeTrade      AlertType = "TRADE"
	AlertTypeBotStart  AlertType = "BOT_START"
	AlertTypeBotStop    AlertType = "BOT_STOP"
	AlertTypeError      AlertType = "ERROR"
	AlertTypeRisk       AlertType = "RISK"
	AlertTypePrice      AlertType = "PRICE"
)

// AlertChannel represents the delivery channel for alerts
type AlertChannel string

const (
	ChannelDiscord   AlertChannel = "DISCORD"
	ChannelTelegram  AlertChannel = "TELEGRAM"
	ChannelEmail     AlertChannel = "EMAIL"
	ChannelWebhook   AlertChannel = "WEBHOOK"
)

// Alert represents a notification to be sent to external channels
type Alert struct {
	ID        string       `json:"id"`
	Type      AlertType    `json:"type"`
	Channel   AlertChannel `json:"channel"`
	Title     string       `json:"title"`
	Message   string       `json:"message"`
	Data      map[string]any `json:"data,omitempty"`
	CreatedAt time.Time    `json:"created_at"`
	Sent      bool         `json:"sent"`
	SentAt    *time.Time   `json:"sent_at,omitempty"`
	Error     string       `json:"error,omitempty"`
}

// AlertConfig holds configuration for alert delivery
type AlertConfig struct {
	Enabled bool `json:"enabled"`

	// Discord webhook URL
	DiscordWebhookURL string `json:"discord_webhook_url,omitempty"`

	// Telegram bot token and chat ID
	TelegramBotToken string `json:"telegram_bot_token,omitempty"`
	TelegramChatID   string `json:"telegram_chat_id,omitempty"`

	// Email SMTP configuration
	EmailSMTPHost string `json:"email_smtp_host,omitempty"`
	EmailSMTPPort int    `json:"email_smtp_port,omitempty"`
	EmailUsername string `json:"email_username,omitempty"`
	EmailPassword string `json:"email_password,omitempty"`
	EmailTo       string `json:"email_to,omitempty"`

	// Custom webhook URL
	CustomWebhookURL string `json:"custom_webhook_url,omitempty"`

	// Which alert types to enable
	NotifyOnTrade     bool `json:"notify_on_trade"`
	NotifyOnBotStart  bool `json:"notify_on_bot_start"`
	NotifyOnError     bool `json:"notify_on_error"`
	NotifyOnRisk      bool `json:"notify_on_risk"`
	NotifyOnPrice     bool `json:"notify_on_price"`
}
