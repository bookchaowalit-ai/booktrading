package http

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"sync"
	"time"
)

// NewsHandler handles news and sentiment endpoints
type NewsHandler struct {
	mu              sync.RWMutex
	cachedSentiment *cachedMarketSentiment
}

type cachedMarketSentiment struct {
	data      MarketSentiment
	fetchedAt time.Time
}

func NewNewsHandler() *NewsHandler { return &NewsHandler{} }

// NewsArticle represents a news article
type NewsArticle struct {
	ID             string    `json:"id"`
	Title          string    `json:"title"`
	Summary        string    `json:"summary"`
	Source         string    `json:"source"`
	Author         string    `json:"author"`
	PublishedAt    time.Time `json:"publishedAt"`
	URL            string    `json:"url"`
	Symbols        []string  `json:"symbols"`
	Categories     []string  `json:"categories"`
	Sentiment      float64   `json:"sentiment"`
	SentimentLabel string    `json:"sentimentLabel"`
	RelevanceScore float64   `json:"relevanceScore"`
}

// NewsResponse is the paginated news response
type NewsResponse struct {
	Articles []NewsArticle `json:"articles"`
	Total    int           `json:"total"`
	Page     int           `json:"page"`
	PageSize int           `json:"pageSize"`
}

// SentimentAnalysis for a symbol
type SentimentAnalysis struct {
	Symbol           string  `json:"symbol"`
	OverallSentiment float64 `json:"overallSentiment"`
	SentimentLabel   string  `json:"sentimentLabel"`
	Confidence       float64 `json:"confidence"`
	Recommendation   string  `json:"recommendation"`
	SignalStrength   string  `json:"signalStrength"`
	UpdatedAt        string  `json:"updatedAt"`
}

// SentimentHistory point
type SentimentHistoryPoint struct {
	Timestamp string  `json:"timestamp"`
	Sentiment float64 `json:"sentiment"`
	Label     string  `json:"label"`
}

// SentimentResponse wraps sentiment + history
type SentimentResponse struct {
	Sentiment SentimentAnalysis       `json:"sentiment"`
	History   []SentimentHistoryPoint `json:"history"`
}

// TradingSignal represents a signal
type TradingSignal struct {
	ID              string    `json:"id"`
	Symbol          string    `json:"symbol"`
	Direction       string    `json:"direction"`
	EntryPrice      float64   `json:"entryPrice"`
	TargetPrices    []float64 `json:"targetPrices"`
	StopLoss        float64   `json:"stopLoss"`
	Leverage        int       `json:"leverage"`
	Confidence      float64   `json:"confidence"`
	Strength        string    `json:"strength"`
	Timeframe       string    `json:"timeframe"`
	Reasoning       []string  `json:"reasoning"`
	RiskRewardRatio float64   `json:"riskRewardRatio"`
	CreatedAt       string    `json:"createdAt"`
	Status          string    `json:"status"`
}

// TradingSignalsResponse wraps signals
type TradingSignalsResponse struct {
	Signals []TradingSignal `json:"signals"`
	Total   int             `json:"total"`
}

// MarketSentiment represents overall market sentiment
type MarketSentiment struct {
	Overall         float64  `json:"overall"`
	Label           string   `json:"label"`
	Crypto          float64  `json:"crypto"`
	Stocks          float64  `json:"stocks"`
	Forex           float64  `json:"forex"`
	Commodities     float64  `json:"commodities"`
	FearGreedIndex  int      `json:"fearGreedIndex"`
	TrendingSymbols []string `json:"trendingSymbols"`
	UpdatedAt       string   `json:"updatedAt"`
}

// GetNews handles GET /api/news — fetches from CoinGecko trending + news feed
func (h *NewsHandler) GetNews(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	articles := h.fetchCoinGeckoNews()
	resp := NewsResponse{
		Articles: articles,
		Total:    len(articles),
		Page:     1,
		PageSize: 20,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

// fetchCoinGeckoNews fetches top crypto news from CoinGecko public API
func (h *NewsHandler) fetchCoinGeckoNews() []NewsArticle {
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get("https://api.coingecko.com/api/v3/news?per_page=20")
	if err != nil || resp.StatusCode != http.StatusOK {
		return h.fallbackNews()
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return h.fallbackNews()
	}

	var cgResp struct {
		Data []struct {
			Title       string `json:"title"`
			Description string `json:"description"`
			URL         string `json:"url"`
			Author      string `json:"author"`
			PublishedAt int64  `json:"updated_at"`
			News        struct {
				Author string `json:"author"`
			} `json:"news"`
		} `json:"data"`
	}

	if err := json.Unmarshal(body, &cgResp); err != nil {
		return h.fallbackNews()
	}

	articles := make([]NewsArticle, 0, len(cgResp.Data))
	for i, a := range cgResp.Data {
		published := time.Unix(a.PublishedAt, 0)
		if a.PublishedAt == 0 {
			published = time.Now().Add(-time.Duration(i) * time.Hour)
		}
		articles = append(articles, NewsArticle{
			ID:             fmt.Sprintf("cg-%d", i),
			Title:          a.Title,
			Summary:        a.Description,
			Source:         "CoinGecko",
			Author:         a.Author,
			PublishedAt:    published,
			URL:            a.URL,
			Symbols:        []string{"BTC", "ETH"},
			Categories:     []string{"crypto"},
			Sentiment:      0.5,
			SentimentLabel: "neutral",
			RelevanceScore: 0.9,
		})
	}
	return articles
}

// fallbackNews returns minimal offline articles when fetch fails
func (h *NewsHandler) fallbackNews() []NewsArticle {
	return []NewsArticle{}
}

// fngSentimentLabel converts Fear & Greed score (0-100) to common label
func fngSentimentLabel(score int) string {
	switch {
	case score <= 20:
		return "extreme_fear"
	case score <= 40:
		return "fear"
	case score <= 60:
		return "neutral"
	case score <= 80:
		return "greed"
	default:
		return "extreme_greed"
	}
}

// fngToFloat converts 0-100 index to -1..+1 sentiment range
func fngToFloat(score int) float64 {
	return (float64(score)-50.0) / 50.0
}

// GetSentiment handles GET /api/sentiment/{symbol}
func (h *NewsHandler) GetSentiment(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	prefix := "/api/sentiment/"
	symbol := r.URL.Path[len(prefix):]
	if symbol == "" {
		symbol = "BTC"
	}
	symbol = strings.ToUpper(symbol)

	ms := h.getMarketSentimentCached()
	sentiment := fngToFloat(ms.FearGreedIndex)
	label := fngSentimentLabel(ms.FearGreedIndex)
	confidence := 0.75

	recommendation := "NEUTRAL"
	strength := "moderate"
	if sentiment > 0.4 {
		recommendation = "BUY"
		strength = "strong"
	} else if sentiment < -0.4 {
		recommendation = "SELL"
		strength = "strong"
	}

	resp := SentimentResponse{
		Sentiment: SentimentAnalysis{
			Symbol:           symbol,
			OverallSentiment: sentiment,
			SentimentLabel:   label,
			Confidence:       confidence,
			Recommendation:   recommendation,
			SignalStrength:   strength,
			UpdatedAt:        ms.UpdatedAt,
		},
		History: []SentimentHistoryPoint{},
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

// GetSignals handles GET /api/signals
func (h *NewsHandler) GetSignals(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	resp := TradingSignalsResponse{
		Signals: []TradingSignal{},
		Total:   0,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

// GetMarketSentiment handles GET /api/market/sentiment — fetches Fear & Greed from Alternative.me
func (h *NewsHandler) GetMarketSentiment(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	resp := h.getMarketSentimentCached()
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

// getMarketSentimentCached returns cached sentiment or fetches fresh data (TTL 10 min)
func (h *NewsHandler) getMarketSentimentCached() MarketSentiment {
	h.mu.RLock()
	if h.cachedSentiment != nil && time.Since(h.cachedSentiment.fetchedAt) < 10*time.Minute {
		data := h.cachedSentiment.data
		h.mu.RUnlock()
		return data
	}
	h.mu.RUnlock()

	data := h.fetchMarketSentiment()

	h.mu.Lock()
	h.cachedSentiment = &cachedMarketSentiment{data: data, fetchedAt: time.Now()}
	h.mu.Unlock()

	return data
}

// fetchMarketSentiment fetches Fear & Greed from Alternative.me and trending from CoinGecko
func (h *NewsHandler) fetchMarketSentiment() MarketSentiment {
	result := MarketSentiment{
		Overall:         0,
		Label:           "neutral",
		Crypto:          0,
		FearGreedIndex:  50,
		TrendingSymbols: []string{},
		UpdatedAt:       time.Now().UTC().Format(time.RFC3339),
	}

	client := &http.Client{Timeout: 5 * time.Second}

	// Fear & Greed index
	if resp, err := client.Get("https://api.alternative.me/fng/"); err == nil && resp.StatusCode == 200 {
		defer resp.Body.Close()
		var fng struct {
			Data []struct {
				Value               string `json:"value"`
				ValueClassification string `json:"value_classification"`
			} `json:"data"`
		}
		if body, err := io.ReadAll(resp.Body); err == nil {
			if json.Unmarshal(body, &fng) == nil && len(fng.Data) > 0 {
				score := 0
				fmt.Sscanf(fng.Data[0].Value, "%d", &score)
				result.FearGreedIndex = score
				result.Crypto = fngToFloat(score)
				result.Overall = result.Crypto
				result.Label = fngSentimentLabel(score)
			}
		}
	}

	// Trending symbols from CoinGecko
	if resp, err := client.Get("https://api.coingecko.com/api/v3/search/trending"); err == nil && resp.StatusCode == 200 {
		defer resp.Body.Close()
		var trending struct {
			Coins []struct {
				Item struct {
					Symbol string `json:"symbol"`
				} `json:"item"`
			} `json:"coins"`
		}
		if body, err := io.ReadAll(resp.Body); err == nil {
			if json.Unmarshal(body, &trending) == nil {
				for _, c := range trending.Coins {
					sym := strings.ToUpper(c.Item.Symbol)
					if sym != "" {
						result.TrendingSymbols = append(result.TrendingSymbols, sym)
					}
				}
			}
		}
	}

	return result
}
