# 📘 BookFinance - AI Financial Command Center

[![CI/CD Pipeline](https://github.com/bookchaowalit/booktrading/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/bookchaowalit/booktrading/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)

**BookFinance** is an AI-centered financial command center for capital protection, evidence tracking, market research, and controlled paper trading.

The default UI is observe-only: it shows what is happening, what is blocked, and what evidence is needed next. Action-heavy trading tools stay hidden behind Advanced mode.

---

## ⚠️ Current Operating Mode: Capital Protection

> **The trading bot is halted by design. No real money is at risk.**

| Status | Detail |
|--------|--------|
| Current decision | **WAIT** |
| Risk source | `paper_bot` for Polymarket / paper capital decisions |
| Paper kill switch | **ACTIVE** — 15.84% drawdown ($100.45 peak → $84.54) |
| Bot state | Halted — no new Polymarket / paper entries |
| Real money | **Blocked** — `POLY_DRY_RUN=true` enforced |
| Deploy | Manual only — gated behind `workflow_dispatch` |
| Legacy positions | 14 active, resolving naturally |
| Grid risk manager | Separate BTCTHB grid risk source; not used to clear paper-bot gates |
| Bankroll | $84.54 paper bankroll |

**What this means:**
- The default dashboard reads `/api/command-center` as the single source of truth
- The bot will NOT enter new positions until readiness gates pass and the kill switch is intentionally reset
- Paper-bot drawdown is the source for capital-protection decisions; grid risk is tracked separately
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
- **Grid Trading** - Automated buy/sell within price ranges (5 pairs: BTC, ETH, SOL, XRP, BNB)
- **Exchange Integrations** - Binance TH, Bitkub, Binance Global research and grid infrastructure
- **Leveraged Market MVP** - Binance USDⓈ-M perpetual futures in paper or Futures Testnet mode only
- **Paper Trading Fallback** - Safe testing without real money ($10K paper balance)
- **Paper Grid PnL** - Real-time profit & loss tracking for paper positions
- **Activity Feed** - Real-time bot activity tracking
- **Alerting System** - EventBus → AlertService pipeline for real-time notifications

### 🧠 AI & Analytics
- **AI Price Prediction** - 5 technical indicators (SMA/EMA/RSI/MACD/Bollinger)
- **Arbitrage Detection** - Find profit opportunities across exchanges (dedicated dashboard page)
- **Backtest vs Paper Comparison** - Side-by-side strategy performance view
- **Performance Charts** - Interactive portfolio visualization
- **Analytics Dashboard** - Comprehensive trading statistics
- **Evidence Gate Automation** - Automated evidence collection and readiness gate tracking
- **System Health Dashboard** - Live container/service health monitoring
- **Daily Report Auto-Generation** - Automated daily operational snapshot

### 💼 Multi-Exchange
- **Binance Thailand** - Full trading support
- **Binance Global** - Research/spot infrastructure plus USDⓈ-M Futures paper/testnet execution
- **Bitkub** - Thai exchange support
- **Balance Aggregation** - View all balances in one place

### 🎨 User Experience
- **32 Dashboard Pages** — comprehensive financial command center:
  - **Core 5 (observe-only):**
    - **Today (Command Center)** — "What to do now" — current decision, kill switch, capital, next triggers
    - **Evidence** — "What happened" — timeline, gates checklist, paper trading positions, activity feed
    - **Research** — "What's worth watching" — crypto candidates, Polymarket reviews, intelligence summary
    - **System** — "Is everything healthy" — component health, risk sources, grid/bot status (auto-refresh 30s)
    - **Daily Report** — "Operational snapshot" — trade journal summary, daily PnL, system overview
  - **Trading Pages:** arbitrage, polymarket, paper-trading, grid-trading, dca, copy-trading, rebalancing, trade-journal
  - **Analytics Pages:** analytics, backtest, portfolio, market-intel, sentiment
  - **Operations Pages:** alerts, monitoring, history, wallet, finance, bot, strategy
  - **Other:** ai-insights, news, dex, docs, settings, evidence
- **Route Consolidation** — Batch 1+2 extraction complete: 38 routes categorised into 5 keep-main, 14 extracted-to-component, 8 advanced-only, 11 hidden/deferred
- **Observe-Only Default** - No trade/start/configure controls in the main flow
- **Advanced Mode** - Action-heavy pages hidden unless `NEXT_PUBLIC_ADVANCED_UI=true`
- **Dark/Light Theme** - Automatic theme switching
- **Mobile Responsive** - Works on all devices
- **Toast Notifications** - Real-time alerts via EventBus → AlertService pipeline
- **Empty States** - Clear messaging when no data
- **Error Boundaries** - Graceful error handling with retry buttons on all pages

### 🔐 Safety & CI
- **CI/CD Pipeline** — automated testing, deploy gated (manual only)
- **Kill Switch** — auto-halt on drawdown threshold breach
- **Dry-Run Mode** — `POLY_DRY_RUN=true` prevents real execution
- **Safety Tests** — kill-switch, safety filters, monitor decision tree, grid safety, and command-center contracts
- **Docker Compose** — one-command local deployment
- **Automated Backups** — daily database backups

### 🌐 Internationalization
- **Thai (TH)** - Full Thai language support
- **English (EN)** - Complete English translations
- **200+ Translation Keys** - Comprehensive coverage

---

## ⚠️ Leveraged Market Scope

The leveraged module is deliberately narrow: Binance USDⓈ-M perpetual futures only. It does **not** yet cover
COIN-M futures, margin borrowing, options, leveraged tokens, CFDs, or every exchange. Futures mainnet execution is
refused by the engine even if production credentials are present.

Safe opt-in flow:

```bash
# Simulation with no exchange credentials
FUTURES_ENABLED=true
FUTURES_EXECUTION_MODE=paper

# Or Binance Futures Demo/Testnet (requires demo credentials)
FUTURES_ENABLED=true
FUTURES_EXECUTION_MODE=testnet
BINANCE_FUTURES_API_KEY=...
BINANCE_FUTURES_API_SECRET=...
```

The engine uses isolated margin, One-way Mode, per-position and account-wide notional caps, a 5x hard leverage
ceiling, risk-based sizing, exchange filters, exchange-side
stop-loss/take-profit orders, position reconciliation, and an automatic halt on ambiguous order state or a breached
liquidation buffer. These controls reduce operational risk; they do not make leverage more profitable or guarantee
returns.

Run the read-only preflight before enabling the background bot:

```bash
# Public Futures Demo connectivity + config/risk checks; no order placement
docker compose run --rm strategy python /app/scripts/futures_preflight.py

# One observe-only paper cycle; still no order placement
docker compose run --rm strategy python /app/scripts/futures_preflight.py --paper-cycle

# Explicitly allow an ephemeral simulated paper entry
docker compose run --rm strategy python /app/scripts/futures_preflight.py --paper-cycle --simulate-entry
```

The authenticated `GET /api/futures/preflight` endpoint exposes the same read-only readiness report. A successful
preflight is evidence that configuration and APIs are reachable, not evidence that the strategy is profitable.

### Financial engineering backtest

The repository now includes a deterministic, read-only comparison of Spot against USDⓈ-M Futures at 1x, 2x, 3x,
and 5x. It uses the same EMA/ADX close-of-bar signal for every variant, executes on the next candle open, and
accounts for configurable fees, slippage, funding payments, an isolated-margin liquidation approximation, turnover,
drawdown, Sharpe, Sortino, Calmar, win rate, and profit factor. The report includes full, in-sample, and holdout
out-of-sample segments; it does not optimize parameters or claim that leverage is profitable.

Run it from the strategy directory (public market data only; no credentials or orders):

```bash
python3 scripts/futures_backtest.py --symbol BTCUSDT --interval 1h --days 90
python3 scripts/futures_backtest.py --days 90 --json --output /tmp/bookfinance-backtest.json
```

The default assumptions are 5 bps fee per side, 2 bps adverse slippage per side, and 20% margin allocation. These
are explicit inputs, not a claim about a Binance account's fee tier. Spot is modeled as long/cash while Futures is
long/short; therefore Futures 1x isolates the effect of short access before comparing the extra leverage.

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
| **[docs/READINESS_CHECKLIST.md](docs/READINESS_CHECKLIST.md)** | Versioned readiness gates before dry-run, reset, micro-live, and production |
| **[docs/EVIDENCE_LOG.md](docs/EVIDENCE_LOG.md)** | State-change log for monitor, trial, research, and gate evidence |
| **[docs/CRYPTO_WATCHLIST.md](docs/CRYPTO_WATCHLIST.md)** | Crypto market watchlist and review notes |
| **[docs/BTCTHB_GRID_RESEARCH.md](docs/BTCTHB_GRID_RESEARCH.md)** | BTCTHB grid research and paper-trial context |
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

### Python Strategy Tests

```bash
docker compose exec strategy pytest /app/tests/ -v
```

Covers kill-switch logic, safety filters, dry-run enforcement, blocklist/allowlist, grid safety, monitor decisions, and `/api/command-center` contracts.

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
- [x] ~~Advanced trading strategies (DCA, Rebalancing)~~ — Dashboard pages exist (DCA, rebalancing, copy-trading)
- [x] ~~Slack/Discord notifications~~ — Alerting system operational (EventBus → AlertService)
- [x] ~~Backtesting with historical data~~ — Backtest vs Paper comparison view implemented
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
