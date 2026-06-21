# BookFinance API Documentation

## Base URLs

| Service | URL | Description |
|---------|-----|-------------|
| **Backend API** | `http://localhost:8080` | Main API (auth, bot, orders, etc.) |
| **WebSocket** | `ws://localhost:8081/ws` | Real-time updates |
| **Strategy API** | `http://localhost:8000` | AI predictions, arbitrage, real grid bot |

---

## 🔐 Authentication

Most endpoints require authentication via Bearer token:

```
Authorization: Bearer <your-token>
```

Get token from `POST /api/auth/login`

---

## 🤖 Bot Endpoints

### Start Bot
```http
POST /api/bot/start
Content-Type: application/json
Authorization: Bearer <token>

{
  "symbol": "BTCTHB",
  "lowerPrice": 2000000,
  "upperPrice": 3000000,
  "gridLevels": 5,
  "investmentAmount": 500
}
```

**Response:** `200 OK`

### Stop Bot
```http
POST /api/bot/stop
Authorization: Bearer <token>
```

**Response:** `200 OK`

### Get Bot Status
```http
GET /api/bot/status
Authorization: Bearer <token>
```

**Response:**
```json
{
  "is_active": true,
  "started_at": "2026-04-13T08:00:00Z",
  "total_trades": 156,
  "total_profit": 12543.20,
  "bot_mode": "GRID"
}
```

---

## 💰 Exchange Endpoints

### Get Current Exchange Balances
```http
GET /api/exchange/balances
Authorization: Bearer <token>
```

**Response:**
```json
{
  "balances": [
    {"currency": "THB", "free": 500.00, "locked": 0, "total": 500.00}
  ],
  "cached": false,
  "exchange": "binance_th"
}
```

### Refresh All Balances
```http
POST /api/exchange/balances
Authorization: Bearer <token>
```

### Get All Exchange Balances
```http
GET /api/exchange/all-balances
Authorization: Bearer <token>
```

**Response:**
```json
{
  "exchanges": {
    "binance_th": {
      "connected": true,
      "balances": [...],
      "totalTHB": 500.00,
      "totalUSDT": 0,
      "balanceCount": 1
    }
  },
  "totalTHB": 500.00,
  "totalUSDT": 0,
  "exchangeCount": 1,
  "cached": false,
  "timestamp": "2026-04-13T08:00:00Z"
}
```

---

## 📊 Portfolio Endpoints

### Get Portfolio
```http
GET /api/portfolio
Authorization: Bearer <token>
```

### Get Trade History
```http
GET /api/trades?limit=50
Authorization: Bearer <token>
```

---

## ⚙️ Settings Endpoints

### Export Configuration
```http
POST /api/settings/export
Authorization: Bearer <token>
```

### Import Configuration
```http
POST /api/settings/import
Content-Type: application/json
Authorization: Bearer <token>

{
  "preferences": {
    "language": "en",
    "theme": "dark",
    "notifications": {
      "trade_executions": true,
      "price_alerts": true
    }
  }
}
```

### Reset Settings
```http
POST /api/settings/reset
Authorization: Bearer <token>
```

---

## 🧠 AI/Strategy Endpoints

### Price Prediction
```http
POST /strategy-api/api/ai/predict
Content-Type: application/json

{
  "prices": [2280000, 2281000, 2282000, 2283000, 2284000],
  "symbol": "BTCTHB"
}
```

**Response:**
```json
{
  "symbol": "BTCTHB",
  "prediction": "BULLISH",
  "confidence": 0.75,
  "current_price": 2284000,
  "recommendation": "BUY",
  "indicators": {
    "rsi_14": 35.5,
    "macd": 150.25,
    "sma_7": 2281500,
    "sma_20": 2275000
  },
  "message": "Prediction: BULLISH (75.0% confidence)"
}
```

### Get Arbitrage Opportunities
```http
GET /strategy-api/api/arbitrage/opportunities?limit=10
```

**Response:**
```json
{
  "opportunities": [
    {
      "symbol": "BTC",
      "buy_exchange": "binance_th",
      "buy_price": 2280000.00,
      "sell_exchange": "bitkub",
      "sell_price": 2285000.00,
      "profit_percent": 0.18,
      "net_profit": 4000.00,
      "timestamp": "2026-04-13T08:00:00Z"
    }
  ],
  "count": 1
}
```

### Update Price (for Arbitrage Detection)
```http
POST /strategy-api/api/arbitrage/update-price?exchange=binance_th&symbol=BTCTHB&price=2280000&volume=100
```

---

## 🤖 Real Grid Bot Endpoints (Strategy API)

These endpoints control the **real** BTCTHB grid bot trading on Binance TH.

### Get Real Grid Status
```http
GET /api/real-grid/status
```

**Response:**
```json
{
  "enabled": true,
  "running": true,
  "symbols": {
    "BTCTHB": {
      "last_price": 2097671.0,
      "active_buys": 6,
      "active_sells": 4,
      "trades_executed": 0,
      "daily_pnl": 0.0,
      "halted": false
    }
  }
}
```

### Kill Switch (Halt Bot)
```http
POST /api/real-grid/kill
```

**Response:**
```json
{
  "enabled": false,
  "message": "Real grid bot disabled"
}
```

### Resume Bot
```http
POST /api/real-grid/enable
```

**Response:**
```json
{
  "enabled": true,
  "message": "Real grid bot enabled"
}
```

---

## 📊 Daily Report Endpoint (Strategy API)

Export comprehensive daily report for audit and monitoring.

### Get Daily Report
```http
GET /api/report/daily?symbol=BTCTHB
```

**Response:**
```json
{
  "symbol": "BTCTHB",
  "bot_enabled": true,
  "bot_running": true,
  "symbol_state": {
    "last_price": 2097671.0,
    "active_buys": 6,
    "active_sells": 4,
    "daily_pnl": 0.0,
    "daily_trades": 0,
    "halted": false
  },
  "open_orders": [...],
  "filled_trades": [...],
  "risk": {
    "halted": false,
    "daily_pnl": 0.0,
    "daily_trades": 0,
    "consecutive_losses": 0,
    "current_drawdown_pct": 0.0
  },
  "journal_stats": {
    "total_entries": 10,
    "open_entries": 10,
    "closed_entries": 0
  },
  "risk_events": []
}
```

---

## 🔌 WebSocket

Connect to: `ws://localhost:8081/ws?token=<your-token>`

### Message Types

**Market Data:**
```json
{
  "type": "market_data",
  "data": {
    "symbol": "BTCTHB",
    "price": 2283119.00,
    "volume": 150.25,
    "timestamp": "2026-04-13T08:00:00Z"
  }
}
```

**Bot Status:**
```json
{
  "type": "bot_status",
  "data": {
    "is_active": true,
    "total_trades": 156,
    "total_profit": 12543.20
  }
}
```

**Trade Notification:**
```json
{
  "type": "trade_notification",
  "data": {
    "symbol": "BTCTHB",
    "side": "BUY",
    "quantity": 0.0001,
    "price": 2280000.00,
    "total": 228.00,
    "type": "GRID_BUY",
    "timestamp": "2026-04-13T08:00:00Z",
    "message": "[REAL] Grid BUY 0.0001 @ 2280000.00"
  }
}
```

**Bot Activity:**
```json
{
  "type": "bot_activity",
  "data": {
    "timestamp": "2026-04-13T08:00:00Z",
    "activity": "SCANNING",
    "symbol": "BTCTHB",
    "message": "Scanning market: BTCTHB",
    "level": "info"
  }
}
```

### Ping/Pong

Send ping:
```json
{
  "type": "ping"
}
```

Receive pong:
```json
{
  "type": "pong"
}
```

---

## ⚠️ Error Responses

All errors follow this format:

```json
{
  "error": "Error message here"
}
```

Common HTTP status codes:
- `200` - Success
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (missing/invalid token)
- `404` - Not Found
- `405` - Method Not Allowed
- `500` - Internal Server Error

---

## 📝 Code Examples

### Python - Start Bot

```python
import requests

response = requests.post(
    'http://localhost:8080/api/bot/start',
    headers={'Authorization': 'Bearer YOUR_TOKEN'},
    json={
        'symbol': 'BTCTHB',
        'lowerPrice': 2000000,
        'upperPrice': 3000000,
        'gridLevels': 5,
        'investmentAmount': 500
    }
)

print(response.json())
```

### JavaScript - Get Balances

```javascript
const response = await fetch('http://localhost:8080/api/exchange/all-balances', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const balances = await response.json();
console.log(balances);
```

### curl - Check Bot Status

```bash
curl -X GET http://localhost:8080/api/bot/status \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

**For more examples, see the Postman collection or Swagger UI**
