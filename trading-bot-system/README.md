# Trading Bot System

A full-stack Real-time Trading Bot System with Hexagonal Architecture, featuring:

- **Backend (Golang)**: Execution & Data Hub with WebSocket connectivity to exchanges
- **Strategy Service (Python/FastAPI)**: Technical analysis engine with RSI and EMA calculations
- **Frontend (Next.js 14)**: Real-time monitoring dashboard
- **Redis Pub/Sub**: Inter-service communication
- **Docker**: Complete containerization for easy deployment

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Trading Bot System                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐    │
│  │   Frontend   │         │    Backend   │         │   Strategy   │    │
│  │  (Next.js)   │◄───────►│   (Golang)   │◄───────►│   (Python)   │    │
│  │   Port 3000  │  WebSocket│Port 8080/81│  gRPC   │   Port 8000  │    │
│  └──────────────┘         └──────────────┘Port 9000└──────────────┘    │
│         │                       │                        │              │
│         │                       │                        │              │
│         ▼                       ▼                        ▼              │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                         Redis Pub/Sub                            │   │
│  │                    market_data | order_signals                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    External Exchange (Binance)                    │   │
│  │                      WebSocket + REST API                         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Communication Patterns

| Service Communication      | Method      | Port  | Purpose                          |
|---------------------------|-------------|-------|----------------------------------|
| Frontend → Backend         | HTTP REST   | 8080  | API commands (orders, bot ctrl)  |
| Frontend → Backend         | WebSocket   | 8081  | Real-time data streaming         |
| Strategy → Backend         | **gRPC**    | 9000  | **Order execution, bot control** |
| Backend → Strategy         | Redis Pub/Sub| 6379 | Market data distribution         |

## Hexagonal Architecture

The system follows Hexagonal Architecture (Ports & Adapters) principles:

### Backend (Go)
```
internal/
├── domain/           # Core business logic
│   ├── model/        # Domain models
│   ├── repository/   # Repository interfaces
│   └── service/      # Service interfaces
├── port/             # Ports (interfaces)
│   ├── input/        # Input ports (handlers)
│   └── output/       # Output ports (external services)
└── adapter/          # Adapters (implementations)
    ├── http/         # HTTP handlers
    ├── websocket/    # WebSocket broadcaster
    ├── redis/        # Redis pub/sub
    ├── exchange/     # Exchange connectors
    └── repository/   # Repository implementations
```

### Strategy Service (Python)
```
strategy/
├── core/             # Core business logic
│   ├── domain/       # Domain models
│   └── service/      # Technical analysis services
├── infrastructure/   # External adapters
│   ├── redis/        # Redis adapter
│   └── api/          # FastAPI application
└── config/           # Configuration
```

## Features

### Backend (Golang)
- ✅ Real-time market data streaming via WebSocket (Binance)
- ✅ REST API for order management (Buy/Sell)
- ✅ WebSocket server for real-time frontend updates
- ✅ Redis Pub/Sub for inter-service communication
- ✅ In-memory repositories (easily replaceable with database)
- ✅ Clean error handling and logging

### Strategy Service (Python)
- ✅ RSI (Relative Strength Index) calculation
- ✅ EMA (Exponential Moving Average) calculation
- ✅ MACD calculation
- ✅ Automated signal generation (RSI < 30 = Buy, RSI > 70 = Sell)
- ✅ Signal strength calculation
- ✅ REST API for monitoring and configuration

### Frontend (Next.js 14)
- ✅ Real-time price charts with Recharts
- ✅ Bot control (Start/Stop)
- ✅ Technical indicators display
- ✅ Portfolio tracking
- ✅ Trade history
- ✅ Dark mode support
- ✅ Responsive design

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 20+ (for local development)
- Go 1.21+ (for local development)
- Python 3.11+ (for local development)

### Option 1: Docker Compose (Recommended)

1. **Clone the repository**
```bash
cd trading-bot-system
```

2. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your exchange API credentials (optional for testnet)
```

3. **Start all services**
```bash
docker-compose up -d
```

4. **Access the services**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8080
- Strategy API: http://localhost:8000
- Redis: localhost:6379

5. **View logs**
```bash
docker-compose logs -f
```

6. **Stop all services**
```bash
docker-compose down
```

### Option 2: Local Development

#### Backend (Go)
```bash
cd backend
go mod download
go run ./cmd
```

#### Strategy Service (Python)
```bash
cd strategy
pip install -r requirements.txt
python -m strategy.app.main
```

#### Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev
```

#### Redis
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

## API Documentation

### Backend API (Port 8080)

#### Bot Control
```bash
# Start Bot
POST /api/bot/start

# Stop Bot
POST /api/bot/stop

# Get Bot Status
GET /api/bot/status
```

#### Orders
```bash
# Create Order
POST /api/orders
{
  "symbol": "BTCUSDT",
  "side": "BUY",
  "quantity": 0.001
}

# Get All Orders
GET /api/orders

# Get Order by ID
GET /api/orders/{id}

# Cancel Order
DELETE /api/orders/{id}
```

#### Portfolio & Trades
```bash
# Get Portfolio
GET /api/portfolio

# Get Trade History
GET /api/trades?limit=50

# Health Check
GET /api/health
```

### Strategy API (Port 8000)

#### Technical Indicators
```bash
# Get All Indicators
GET /api/indicators

# Get Indicators for Symbol
GET /api/indicators/{symbol}
```

#### Strategy Configuration
```bash
# Get Config
GET /api/strategy/config

# Update Config
POST /api/strategy/config
{
  "rsi_period": 14,
  "ema_period": 14,
  "rsi_oversold": 30.0,
  "rsi_overbought": 70.0,
  "min_signal_strength": 0.5
}

# Reset Strategy
POST /api/strategy/reset
```

## Trading Strategy

The default strategy uses RSI and EMA indicators:

### Buy Signal
- **Condition**: RSI < 30 (Oversold)
- **Confirmation**: Price below EMA
- **Signal Strength**: Based on RSI deviation from 30

### Sell Signal
- **Condition**: RSI > 70 (Overbought)
- **Confirmation**: Price above EMA
- **Signal Strength**: Based on RSI deviation from 70

### Configuration
Modify strategy parameters via:
- Environment variables
- REST API: `POST /api/strategy/config`

## Data Flow

1. **Market Data Flow**
```
Binance WebSocket → Backend → Redis (market_data) → Strategy Service
                                          ↓
                                    Frontend (WebSocket)
```

2. **Order Signal Flow**
```
Strategy Service → Redis (order_signals) → Backend → Exchange API
```

## Extending the System

### Adding a New Exchange
1. Create new adapter in `backend/internal/adapter/exchange/`
2. Implement `ExchangeDataStream` and `OrderExecutor` interfaces
3. Update configuration to support new exchange

### Adding a New Strategy
1. Create new strategy class in `strategy/core/service/`
2. Implement signal generation logic
3. Update `MultiSymbolStrategy` to use new strategy

### Adding a New Database
1. Create repository implementation in `backend/internal/adapter/repository/`
2. Implement repository interfaces
3. Update dependency injection in `main.go`

## Monitoring & Debugging

### Health Checks
```bash
# Backend
curl http://localhost:8080/api/health

# Strategy
curl http://localhost:8000/api/health

# Redis
docker exec trading-bot-redis redis-cli ping
```

### Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f strategy
docker-compose logs -f frontend
```

## Security Considerations

⚠️ **Important**: This is a boilerplate/demo system. For production use:

1. **API Keys**: Never commit API keys to version control
2. **Authentication**: Add authentication to all APIs
3. **Rate Limiting**: Implement rate limiting
4. **Error Handling**: Add comprehensive error handling
5. **Testing**: Write comprehensive tests
6. **Monitoring**: Add proper monitoring and alerting

## Testing

### Backend Tests
```bash
cd backend
go test ./...
```

### Strategy Tests
```bash
cd strategy
pytest
```

### Frontend Tests
```bash
cd frontend
npm test
```

## Performance Optimization

- **Backend**: Connection pooling, async processing
- **Strategy**: Caching, batch calculations
- **Frontend**: Memoization, virtual scrolling for large lists
- **Redis**: Persistence configuration, memory optimization

## Troubleshooting

### Backend won't start
- Check Redis connection: `docker-compose logs redis`
- Verify ports are not in use: `lsof -i :8080`

### Strategy service errors
- Check Python dependencies: `pip install -r requirements.txt`
- Verify Redis connectivity

### Frontend issues
- Clear browser cache
- Check API endpoints in browser console
- Verify environment variables

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions are welcome! Please read CONTRIBUTING.md for guidelines.

## Support

For issues and questions:
- GitHub Issues: Report bugs
- Discussions: Ask questions

---

**Built with ❤️ using Hexagonal Architecture**
