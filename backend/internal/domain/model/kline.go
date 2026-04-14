package model

import "time"

// Kline represents a single candlestick (OHLCV) bar for a trading pair.
type Kline struct {
	Time         time.Time `json:"time"`
	Symbol       string    `json:"symbol"`
	IntervalType string    `json:"interval_type"`
	Open         float64   `json:"open"`
	High         float64   `json:"high"`
	Low          float64   `json:"low"`
	Close        float64   `json:"close"`
	Volume       float64   `json:"volume"`
	CloseTime    time.Time `json:"close_time"`
	QuoteVolume  float64   `json:"quote_volume"`
	Trades       int       `json:"trades"`
}
