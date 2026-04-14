package model

import "time"

// APIKey represents encrypted exchange API credentials
type APIKey struct {
	ID          string    `json:"id" gorm:"primaryKey"`
	UserID      string    `json:"user_id" gorm:"index;not null"`
	Exchange    string    `json:"exchange" gorm:"not null"`
	APIKey      string    `json:"api_key" gorm:"not null"` // Encrypted
	APISecret   string    `json:"api_secret" gorm:"not null"` // Encrypted
	Passphrase  string    `json:"passphrase"` // Encrypted
	Testnet     bool      `json:"testnet" gorm:"default:false"`
	IsActive    bool      `json:"is_active" gorm:"default:true"`
	CreatedAt   time.Time `json:"created_at" gorm:"autoCreateTime"`
	UpdatedAt   time.Time `json:"updated_at" gorm:"autoUpdateTime"`
	LastUsedAt  *time.Time `json:"last_used_at"`
}

// TableName specifies table name
func (APIKey) TableName() string {
	return "api_keys"
}
