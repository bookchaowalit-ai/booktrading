package service

import (
	"net/http"
	"sync"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"trading-bot-system/backend/internal/logger"
)

// MetricsService exposes Prometheus metrics
type MetricsService struct {
	registry *prometheus.Registry

	// HTTP metrics
	httpRequestsTotal   *prometheus.CounterVec
	httpRequestDuration *prometheus.HistogramVec

	// Trading metrics
	tradesTotal       prometheus.Counter
	tradesSuccess     prometheus.Counter
	tradesFailed      prometheus.Counter
	tradePnL          prometheus.Gauge
	tradeWinRate      prometheus.Gauge
	activeBots        prometheus.Gauge
	paperTradesTotal  prometheus.Counter
	paperPnL          prometheus.Gauge

	// Bot metrics
	botStartsTotal prometheus.Counter
	botStopsTotal  prometheus.Counter
	botUptime      *prometheus.GaugeVec

	// System metrics
	redisConnections    prometheus.Gauge
	dbQueryDuration     *prometheus.HistogramVec
	dbQueryTotal        *prometheus.CounterVec
	exchangeAPICalls    *prometheus.CounterVec
	exchangeAPIErrors   *prometheus.CounterVec
	exchangeAPILatency  *prometheus.HistogramVec
	riskChecks          prometheus.Counter
	riskCheckBlocks     prometheus.Counter
	alertsSent          *prometheus.CounterVec
	alertsFailed        *prometheus.CounterVec

	// Uptime tracking
	startTime time.Time
	mu        sync.Mutex
}

// NewMetricsService creates a new metrics service
func NewMetricsService() *MetricsService {
	registry := prometheus.NewRegistry()

	ms := &MetricsService{
		registry:  registry,
		startTime: time.Now(),

		// HTTP
		httpRequestsTotal: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total number of HTTP requests",
		}, []string{"method", "path", "status"}),

		httpRequestDuration: prometheus.NewHistogramVec(prometheus.HistogramOpts{
			Name:    "http_request_duration_seconds",
			Help:    "HTTP request duration in seconds",
			Buckets: prometheus.DefBuckets,
		}, []string{"method", "path"}),

		// Trading
		tradesTotal: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "trades_total",
			Help: "Total number of trades executed",
		}),

		tradesSuccess: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "trades_success_total",
			Help: "Total number of successful trades",
		}),

		tradesFailed: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "trades_failed_total",
			Help: "Total number of failed trades",
		}),

		tradePnL: prometheus.NewGauge(prometheus.GaugeOpts{
			Name: "trade_pnl_total",
			Help: "Total profit and loss from trades",
		}),

		tradeWinRate: prometheus.NewGauge(prometheus.GaugeOpts{
			Name: "trade_win_rate",
			Help: "Current win rate percentage (0-100)",
		}),

		activeBots: prometheus.NewGauge(prometheus.GaugeOpts{
			Name: "active_bots",
			Help: "Number of currently active trading bots",
		}),

		paperTradesTotal: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "paper_trades_total",
			Help: "Total number of paper trades executed",
		}),

		paperPnL: prometheus.NewGauge(prometheus.GaugeOpts{
			Name: "paper_pnl_total",
			Help: "Total paper trading profit and loss",
		}),

		// Bot
		botStartsTotal: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "bot_starts_total",
			Help: "Total number of bot starts",
		}),

		botStopsTotal: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "bot_stops_total",
			Help: "Total number of bot stops",
		}),

		botUptime: prometheus.NewGaugeVec(prometheus.GaugeOpts{
			Name: "bot_uptime_seconds",
			Help: "Bot uptime in seconds",
		}, []string{"symbol"}),

		// System
		redisConnections: prometheus.NewGauge(prometheus.GaugeOpts{
			Name: "redis_connections",
			Help: "Number of active Redis connections",
		}),

		dbQueryDuration: prometheus.NewHistogramVec(prometheus.HistogramOpts{
			Name:    "db_query_duration_seconds",
			Help:    "Database query duration in seconds",
			Buckets: []float64{0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5},
		}, []string{"operation"}),

		dbQueryTotal: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "db_queries_total",
			Help: "Total number of database queries",
		}, []string{"operation", "status"}),

		exchangeAPICalls: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "exchange_api_calls_total",
			Help: "Total number of exchange API calls",
		}, []string{"exchange", "method"}),

		exchangeAPIErrors: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "exchange_api_errors_total",
			Help: "Total number of exchange API errors",
		}, []string{"exchange", "method"}),

		exchangeAPILatency: prometheus.NewHistogramVec(prometheus.HistogramOpts{
			Name:    "exchange_api_latency_seconds",
			Help:    "Exchange API latency in seconds",
			Buckets: []float64{0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5},
		}, []string{"exchange", "method"}),

		riskChecks: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "risk_checks_total",
			Help: "Total number of risk checks performed",
		}),

		riskCheckBlocks: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "risk_check_blocks_total",
			Help: "Total number of trades blocked by risk manager",
		}),

		alertsSent: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "alerts_sent_total",
			Help: "Total number of alerts sent",
		}, []string{"channel", "type"}),

		alertsFailed: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "alerts_failed_total",
			Help: "Total number of failed alert deliveries",
		}, []string{"channel", "type"}),
	}

	// Register all collectors
	registry.MustRegister(
		ms.httpRequestsTotal,
		ms.httpRequestDuration,
		ms.tradesTotal,
		ms.tradesSuccess,
		ms.tradesFailed,
		ms.tradePnL,
		ms.tradeWinRate,
		ms.activeBots,
		ms.paperTradesTotal,
		ms.paperPnL,
		ms.botStartsTotal,
		ms.botStopsTotal,
		ms.botUptime,
		ms.redisConnections,
		ms.dbQueryDuration,
		ms.dbQueryTotal,
		ms.exchangeAPICalls,
		ms.exchangeAPIErrors,
		ms.exchangeAPILatency,
		ms.riskChecks,
		ms.riskCheckBlocks,
		ms.alertsSent,
		ms.alertsFailed,
	)

	// Add process-level metrics (Go runtime, goroutines)
	registry.MustRegister(prometheus.NewProcessCollector(prometheus.ProcessCollectorOpts{}))
	registry.MustRegister(prometheus.NewGoCollector())

	logger.Info("Prometheus metrics service initialized")
	return ms
}

// Handler returns an HTTP handler for the /metrics endpoint
func (ms *MetricsService) Handler() http.Handler {
	return promhttp.HandlerFor(ms.registry, promhttp.HandlerOpts{
		EnableOpenMetrics: true,
	})
}

// ObserveHTTPRequest records an HTTP request metric
func (ms *MetricsService) ObserveHTTPRequest(method, path string, status int, duration time.Duration) {
	ms.httpRequestsTotal.WithLabelValues(method, path, string(rune(status))).Inc()
	ms.httpRequestDuration.WithLabelValues(method, path).Observe(duration.Seconds())
}

// RecordTrade records a trade metric
func (ms *MetricsService) RecordTrade(success bool, pnl float64) {
	ms.mu.Lock()
	defer ms.mu.Unlock()

	ms.tradesTotal.Inc()
	if success {
		ms.tradesSuccess.Inc()
		ms.tradePnL.Add(pnl)
	} else {
		ms.tradesFailed.Inc()
	}
}

// UpdateWinRate updates the win rate gauge
func (ms *MetricsService) UpdateWinRate(rate float64) {
	ms.tradeWinRate.Set(rate)
}

// UpdateActiveBots updates the active bots gauge
func (ms *MetricsService) UpdateActiveBots(count float64) {
	ms.activeBots.Set(count)
}

// RecordPaperTrade records a paper trade
func (ms *MetricsService) RecordPaperTrade(pnl float64) {
	ms.paperTradesTotal.Inc()
	ms.paperPnL.Add(pnl)
}

// RecordBotStart records a bot start
func (ms *MetricsService) RecordBotStart(symbol string) {
	ms.botStartsTotal.Inc()
	ms.botUptime.WithLabelValues(symbol).Set(0)
}

// RecordBotStop records a bot stop
func (ms *MetricsService) RecordBotStop() {
	ms.botStopsTotal.Inc()
}

// UpdateBotUptime updates bot uptime
func (ms *MetricsService) UpdateBotUptime(symbol string, seconds float64) {
	ms.botUptime.WithLabelValues(symbol).Set(seconds)
}

// UpdateRedisConnections updates Redis connection count
func (ms *MetricsService) UpdateRedisConnections(count float64) {
	ms.redisConnections.Set(count)
}

// ObserveDBQuery records a database query
func (ms *MetricsService) ObserveDBQuery(operation string, duration time.Duration, success bool) {
	ms.dbQueryDuration.WithLabelValues(operation).Observe(duration.Seconds())
	status := "success"
	if !success {
		status = "error"
	}
	ms.dbQueryTotal.WithLabelValues(operation, status).Inc()
}

// ObserveExchangeAPI records an exchange API call
func (ms *MetricsService) ObserveExchangeAPI(exchange, method string, duration time.Duration, success bool) {
	ms.exchangeAPICalls.WithLabelValues(exchange, method).Inc()
	ms.exchangeAPILatency.WithLabelValues(exchange, method).Observe(duration.Seconds())
	if !success {
		ms.exchangeAPIErrors.WithLabelValues(exchange, method).Inc()
	}
}

// RecordRiskCheck records a risk check
func (ms *MetricsService) RecordRiskCheck(blocked bool) {
	ms.riskChecks.Inc()
	if blocked {
		ms.riskCheckBlocks.Inc()
	}
}

// RecordAlert records an alert delivery
func (ms *MetricsService) RecordAlert(channel, alertType string, success bool) {
	if success {
		ms.alertsSent.WithLabelValues(channel, alertType).Inc()
	} else {
		ms.alertsFailed.WithLabelValues(channel, alertType).Inc()
	}
}

// Uptime returns the service uptime in seconds
func (ms *MetricsService) Uptime() float64 {
	return time.Since(ms.startTime).Seconds()
}
