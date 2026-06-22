# 📘 BookFinance - Crypto Trading Bot

[![CI/CD Pipeline](https://github.com/bookchaowalit/booktrading/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/bookchaowalit/booktrading/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)

**BookFinance** is a crypto trading bot with AI predictions, arbitrage detection, multi-exchange support, and real-time monitoring.

---

## ⚠️ Current Operating Mode: Capital Protection

> **The trading bot is halted by design. No real money is at risk.**

| Status | Detail |
|--------|--------|
| Kill switch | **ACTIVE** — triggered at 15.8% drawdown |
| Bot state | Halted — no new trades |
| Real money | **Blocked** — `POLY_DRY_RUN=true` enforced |
| Deploy | Manual only — gated behind `workflow_dispatch` |
| Legacy positions | 20 open, waiting for resolution |
| Bankroll | $84.54 |

**What this means:**
- The bot will NOT enter new positions until the kill switch is manually reset
- Paper trading runs in dry-run mode (simulates but never executes)
- Production deploy requires explicit `workflow_dispatch` with `deploy_production=true`
- See [strategy/RUNBOOK.md](strategy/RUNBOOK.md) for the full decision tree

### Daily Monitor

```bash
docker compose exec strategy python /app/scripts/monitor.py
```

This outputs a structured decision block: current state, reason, and what trigger would advance to the next stage.

---

## 🚀 Features

### 🤖 Trading Bot
- **Grid Trading** - Automated buy/sell within price ranges
- **Real Exchange Orders** - Trades on Binance TH, Bitkub, Binance Global
- **Paper Trading Fallback** - Safe testing without real money
- **Activity Feed** - Real-time bot activity tracking

### 🧠 AI & Analytics
- **AI Price Prediction** - 5 technical indicators (SMA/EMA/RSI/MACD/Bollinger)
- **Arbitrage Detection** - Find profit opportunities across exchanges
- **Performance Charts** - Interactive portfolio visualization
- **Analytics Dashboard** - Comprehensive trading statistics

### 💼 Multi-Exchange
- **Binance Thailand** - Full trading support
- **Binance Global** - Testnet and live trading
- **Bitkub** - Thai exchange support
- **Balance Aggregation** - View all balances in one place

### 🎨 User Experience
- **Grouped Sidebar** - Organized navigation with expand/collapse
- **Dark/Light Theme** - Automatic theme switching
- **Keyboard Shortcuts** - 13 shortcuts for faster operation
- **Mobile Responsive** - Works on all devices
- **Toast Notifications** - Real-time alerts
- **Empty States** - Clear messaging when no data
- **Error Boundaries** - Graceful error handling

### 🔐 Safety & CI
- **CI/CD Pipeline** — automated testing, deploy gated (manual only)
- **Kill Switch** — auto-halt on drawdown threshold breach
- **Dry-Run Mode** — `POLY_DRY_RUN=true` prevents real execution
- **Safety Tests** — 53 passing (kill-switch + safety filters)
- **Docker Compose** — one-command local deployment
- **Automated Backups** — daily database backups

### 🌐 Internationalization
- **Thai (TH)** - Full Thai language support
- **English (EN)** - Complete English translations
- **200+ Translation Keys** - Comprehensive coverage

---

## 📦 Quick Start

### Prerequisites
- Docker & Docker Compose
- 2GB+ RAM, 2+ CPU cores
- Domain name (for production)

### Development

```bash
# Clone repository
git clone https://github.com/your-username/bookfinance.git
cd bookfinance

# Start all services
docker compose up -d --build

# Access application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8080
# Strategy API: http://localhost:8000
```

### Production

```bash
# Edit environment variables
cp .env.example .env
nano .env

# Deploy
./deploy.sh production

# Or manually
docker compose -f docker-compose.prod.yml up -d --build
```

See **[PRODUCTION.md](PRODUCTION.md)** for full deployment guide.

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| **[strategy/RUNBOOK.md](strategy/RUNBOOK.md)** | Operational playbook — decision tree, safety rules |
| **[USER_GUIDE.md](USER_GUIDE.md)** | Complete user guide |
| **[API.md](API.md)** | Full API documentation |
| **[PRODUCTION.md](PRODUCTION.md)** | Production deployment guide |
| **[.env.example](.env.example)** | Safe-by-default environment config |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Caddy (Reverse Proxy)                 │
│              Automatic HTTPS + TLS Termination           │
└──────────────┬──────────────────────────┬────────────────┘
               │                          │
    ┌──────────▼──────────┐    ┌──────────▼──────────────┐
    │   Frontend (Next.js)│    │    Backend (Go)         │
    │   - Dashboard UI    │    │   - HTTP API            │
    │   - Real-time WS    │    │   - WebSocket Server    │
    │   - Charts & Graphs │    │   - gRPC Server         │
    └─────────────────────┘    └──────┬──────────────────┘
                                      │
              ┌───────────────────────┼───────────────────┐
              │                       │                   │
    ┌─────────▼────────┐   ┌─────────▼────────┐  ┌───────▼────────┐
    │   PostgreSQL     │   │      Redis       │  │   Strategy     │
    │   (TimescaleDB)  │   │   (Message Broker)│  │   (Python)     │
    │   - User Data    │   │   - Pub/Sub      │  │   - AI Predict │
    │   - Trades       │   │   - Cache        │  │   - Arbitrage  │
    │   - History      │   │   - Sessions     │  │   - Telegram   │
    └──────────────────┘   └──────────────────┘  └────────────────┘
```

---

## 🗂️ Project Structure

```
bookfinance/
├── backend/                    # Go backend
│   ├── cmd/                   # Main application entry
│   ├── internal/              # Internal packages
│   │   ├── adapter/           # External adapters (HTTP, DB, Exchange)
│   │   ├── domain/            # Business logic
│   │   └── port/              # Interface definitions
│   └── migrations/            # Database migrations
├── frontend/                   # Next.js frontend
│   ├── src/
│   │   ├── app/               # Next.js pages
│   │   ├── components/        # React components
│   │   ├── services/          # API clients
│   │   └── hooks/             # Custom hooks
│   └── public/                # Static assets
├── strategy/                   # Python strategy service
│   └── app/
│       ├── predictor.py       # AI price prediction
│       ├── arbitrage.py       # Arbitrage detection
│       └── telegram_bot.py    # Telegram bot
├── .github/workflows/          # CI/CD pipeline
├── monitoring/                 # Prometheus/Grafana config
├── scripts/                    # Utility scripts
├── deploy.sh                   # Deployment script
├── docker-compose.yml          # Development compose
├── docker-compose.prod.yml     # Production compose
└── Caddyfile                   # Reverse proxy config
```

---

## 🧪 Testing

### Python Safety Tests (53 passing)

```bash
docker compose exec strategy pytest /app/tests/ -v
```

Covers kill-switch logic, safety filters, dry-run enforcement, blocklist/allowlist.

### Backend Tests

```bash
docker compose exec backend go test -v ./...
```

### Frontend Tests

```bash
docker compose exec frontend npm test
```

### Run All Tests (CI)

```bash
./scripts/test.sh
```

---

## 🔧 Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DB_PASSWORD` | ✅ | Database password |
| `REDIS_PASSWORD` | ✅ | Redis password |
| `ENCRYPTION_KEY` | ✅ | 32+ char encryption key |
| `FIRST_ADMIN_EMAIL` | ✅ | Admin email |
| `FIRST_ADMIN_PASSWORD` | ✅ | Admin password |
| `EXCHANGE_PROVIDER` | ⚠️ | Default: `binance_th` |
| `BINANCE_TH_API_KEY` | ⚠️ | Binance TH API key |
| `BINANCE_TH_API_SECRET` | ⚠️ | Binance TH API secret |
| `FRONTEND_URL` | ⚠️ | Your domain URL |

See `.env.example` for all available variables.

---

## 📊 Monitoring

### System Health

Access health check: `http://localhost:8080/api/health`

### Metrics

Backend exposes Prometheus metrics at: `http://localhost:9090/metrics`

### Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f strategy
```

---

## 🚀 Roadmap

- [ ] Multi-user support with RBAC
- [ ] Mobile app (React Native)
- [ ] Advanced trading strategies (DCA, Rebalancing)
- [ ] Slack/Discord notifications
- [ ] Backtesting with historical data
- [ ] Copy trading functionality
- [ ] Advanced risk management
- [ ] Portfolio optimization algorithms

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🆘 Support

- **Documentation**: See [USER_GUIDE.md](USER_GUIDE.md)
- **API Reference**: See [API.md](API.md)
- **Deployment**: See [PRODUCTION.md](PRODUCTION.md)
- **Issues**: Open a GitHub issue
- **Email**: admin@your-domain.com

---

**Made with ❤️ for crypto traders everywhere!** 🚀
