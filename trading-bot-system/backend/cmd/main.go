package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"trading-bot-system/backend/internal/adapter/exchange"
	httpadapter "trading-bot-system/backend/internal/adapter/http"
	repositoryadapter "trading-bot-system/backend/internal/adapter/repository"
	"trading-bot-system/backend/internal/adapter/redis"
	"trading-bot-system/backend/internal/adapter/websocket"
	"trading-bot-system/backend/internal/adapter/database"
	"trading-bot-system/backend/internal/config"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/adapter/grpcserver"
	"trading-bot-system/backend/internal/domain/service"
)

func main() {
	// Load configuration
	cfg := config.LoadConfig()

	// Initialize Redis adapter
	redisAdapter := redis.NewRedisAdapter(
		cfg.Redis.Host,
		cfg.Redis.Port,
		cfg.Redis.Password,
		cfg.Redis.DB,
	)

	// Initialize PostgreSQL database
	db, err := database.NewPostgresDB(database.Config{
		Host:     cfg.Database.Host,
		Port:     cfg.Database.Port,
		User:     cfg.Database.User,
		Password: cfg.Database.Password,
		DBName:   cfg.Database.DBName,
		SSLMode:  cfg.Database.SSLMode,
	})
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()

	// Run database migrations
	log.Println("Running database migrations...")
	databaseURL := fmt.Sprintf(
		"postgres://%s:%s@%s:%s/%s?sslmode=%s",
		cfg.Database.User,
		cfg.Database.Password,
		cfg.Database.Host,
		cfg.Database.Port,
		cfg.Database.DBName,
		cfg.Database.SSLMode,
	)
	if err := database.RunMigrations(databaseURL); err != nil {
		log.Printf("Warning: Migration error: %v", err)
		// Continue anyway - migrations might have already run
	}

	// Initialize repositories (using PostgreSQL)
	orderRepo := repositoryadapter.NewPostgresOrderRepository(db.Pool)
	portfolioRepo := repositoryadapter.NewPostgresPortfolioRepository(db.Pool)
	tradeHistoryRepo := repositoryadapter.NewPostgresTradeHistoryRepository(db.Pool)
	botStatusRepo := repositoryadapter.NewPostgresBotStatusRepository(db.Pool)
	marketDataRepo := repositoryadapter.NewPostgresMarketDataRepository(db.Pool)
	apiKeyRepo := database.NewAPIKeyRepository(db.Pool)
	prefsRepo := database.NewUserPreferencesRepository(db.Pool)

	// Initialize exchange manager (handles multiple exchanges)
	exchangeManager := exchange.NewExchangeManager(&cfg.Exchange, apiKeyRepo)

	// Initialize exchange adapters (get credentials from APIKeys map)
	binanceKey := cfg.Exchange.APIKeys[string(config.ExchangeBinance)]
	var binanceStream *exchange.BinanceAdapter
	var binanceExecutor *exchange.BinanceOrderExecutor
	
	if binanceKey != nil && binanceKey.Enabled {
		binanceStream = exchange.NewBinanceAdapter(
			binanceKey.APIKey,
			binanceKey.APISecret,
			binanceKey.UseTestnet,
		)
		binanceExecutor = exchange.NewBinanceOrderExecutor(
			binanceKey.APIKey,
			binanceKey.APISecret,
			binanceKey.UseTestnet,
		)
	} else {
		// Create with empty credentials (will fail gracefully)
		binanceStream = exchange.NewBinanceAdapter("", "", true)
		binanceExecutor = exchange.NewBinanceOrderExecutor("", "", true)
	}

	// Initialize WebSocket broadcaster
	wsBroadcaster := websocket.NewWebSocketBroadcaster(
		cfg.WebSocket.MaxClients,
		cfg.WebSocket.BroadcastQueue,
	)

	// Start WebSocket broadcaster goroutine
	go wsBroadcaster.Run()

	// Initialize services
	orderService := service.NewOrderService(
		orderRepo,
		tradeHistoryRepo,
		binanceExecutor,
		wsBroadcaster,
	)

	marketDataService := service.NewMarketDataService(
		binanceStream,
		marketDataRepo,
		redisAdapter,
		wsBroadcaster,
	)

	botService := service.NewBotService(
		botStatusRepo,
		redisAdapter,
		wsBroadcaster,
	)

	portfolioService := service.NewPortfolioService(portfolioRepo)
	tradeHistoryService := service.NewTradeHistoryService(tradeHistoryRepo)

	// Initialize gRPC server
	grpcServer := grpcserver.NewGRPCServer(
		cfg.GRPC.Port,
		orderService,
		botService,
		marketDataService,
	)

	// Create HTTP handlers (services already implement the handler interfaces)
	orderHandler := httpadapter.NewOrderHandler(orderService)
	botHandler := httpadapter.NewBotHandler(botService)
	portfolioHandler := httpadapter.NewPortfolioHandler(portfolioService)
	tradeHistoryHandler := httpadapter.NewTradeHistoryHandler(tradeHistoryService)
	healthHandler := httpadapter.NewHealthHandler()
	exchangeHandler := httpadapter.NewExchangeHandler(exchangeManager)
	settingsHandler := httpadapter.NewSettingsHandler(cfg, prefsRepo)
	tradingHandler := httpadapter.NewTradingHandler()
	newsHandler := httpadapter.NewNewsHandler()
	authHandler := httpadapter.NewAuthHandler()
	notificationHandler := httpadapter.NewNotificationHandler(db.Pool)
	performanceHandler := httpadapter.NewPerformanceHandler(tradeHistoryService)
	journalHandler := httpadapter.NewJournalHandler(db.Pool)
	sltpHandler := httpadapter.NewSLTPHandler()

	// Setup router
	router := httpadapter.NewRouter(authHandler)
	router.RegisterOrderRoutes(orderHandler)
	router.RegisterBotRoutes(botHandler)
	router.RegisterPortfolioRoutes(portfolioHandler)
	router.RegisterTradeHistoryRoutes(tradeHistoryHandler)
	router.RegisterHealthRoute(healthHandler)
	router.RegisterExchangeRoutes(exchangeHandler)
	router.RegisterSettingsRoutes(settingsHandler)
	router.RegisterTradingRoutes(tradingHandler)
	router.RegisterNewsRoutes(newsHandler)
	router.RegisterAuthRoutes(authHandler)
	router.RegisterNotificationRoutes(notificationHandler)
	router.RegisterPerformanceRoutes(performanceHandler)
	router.RegisterJournalRoutes(journalHandler)
	router.RegisterSLTPRoutes(sltpHandler)

	// Add logging middleware
	handler := httpadapter.Logger(router)

	// Create HTTP server
	httpServer := &http.Server{
		Addr:         ":" + cfg.Server.Port,
		Handler:      handler,
		ReadTimeout:  cfg.Server.ReadTimeout,
		WriteTimeout: cfg.Server.WriteTimeout,
	}

	// Create WebSocket server
	wsHandler := websocket.NewWSHandler(wsBroadcaster)
	wsServer := &http.Server{
		Addr: ":" + cfg.WebSocket.Port,
	}
	http.HandleFunc("/ws", wsHandler.HandleWebSocket)

	// Connect to Binance WebSocket
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	if err := binanceStream.Connect(ctx); err != nil {
		log.Printf("Note: Binance WebSocket not connected (will retry on demand): %v", err)
	} else {
		// Start streaming for default symbols
		go func() {
			time.Sleep(2 * time.Second) // Wait for connection to stabilize
			if err := marketDataService.StartStreaming(ctx, model.BTCUSDT); err != nil {
				log.Printf("Note: BTCUSDT streaming not started: %v", err)
			}
			if err := marketDataService.StartStreaming(ctx, model.ETHUSDT); err != nil {
				log.Printf("Note: ETHUSDT streaming not started: %v", err)
			}
		}()
	}

	// Start HTTP server in goroutine
	go func() {
		log.Printf("Starting HTTP server on port %s", cfg.Server.Port)
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("HTTP server error: %v", err)
		}
	}()

	// Start WebSocket server in goroutine
	go func() {
		log.Printf("Starting WebSocket server on port %s", cfg.WebSocket.Port)
		if err := wsServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("WebSocket server error: %v", err)
		}
	}()

	// Start gRPC server
	if err := grpcServer.Start(); err != nil {
		log.Printf("Warning: Failed to start gRPC server: %v", err)
	}

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down servers...")

	// Graceful shutdown
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer shutdownCancel()

	if err := httpServer.Shutdown(shutdownCtx); err != nil {
		log.Printf("HTTP server shutdown error: %v", err)
	}

	if err := wsServer.Shutdown(shutdownCtx); err != nil {
		log.Printf("WebSocket server shutdown error: %v", err)
	}

	// Stop gRPC server
	grpcServer.Stop()

	// Shutdown market data service
	marketDataService.Shutdown()

	if err := redisAdapter.Close(); err != nil {
		log.Printf("Redis connection close error: %v", err)
	}

	log.Println("Servers stopped")
}
