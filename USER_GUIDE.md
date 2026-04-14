# 📘 BookFinance User Guide

Welcome to BookFinance - Your complete crypto trading bot solution!

---

## 🚀 Quick Start

### 1. First Time Setup

```bash
# Clone the repository
git clone https://github.com/your-username/bookfinance.git
cd bookfinance

# Copy environment file
cp .env.example .env

# Edit with your settings
nano .env

# Start the application
docker compose up -d --build
```

### 2. Access the Application

Open your browser and go to: **http://localhost:3000**

### 3. Login

Use the admin credentials you set in `.env`:
- **Email:** `admin@your-domain.com` (or what you set in `FIRST_ADMIN_EMAIL`)
- **Password:** Your `FIRST_ADMIN_PASSWORD`

---

## 📊 Dashboard Overview

The dashboard is your command center. Here's what you'll see:

| Section | Description |
|---------|-------------|
| **Trading Controls** | Quick access to start/stop bot and configure strategy |
| **Stats Cards** | Total Value, Profit, Trades, Portfolio, Wallet balances |
| **Price Charts** | Real-time BTC and ETH price charts |
| **Technical Analysis** | RSI, MACD, and other indicators |
| **Recent Trades** | Latest trade history |

---

## 🤖 How to Start Trading

### Step 1: Go to Trading Page

Click **Trading** in the sidebar, or press `Ctrl+Alt+T`

### Step 2: Configure Your Bot

| Setting | Recommended Value | Description |
|---------|-------------------|-------------|
| **Symbol** | `BTCTHB` | Trading pair (Binance Thailand) |
| **Lower Price** | `2000000` | Bottom of your grid range |
| **Upper Price** | `3000000` | Top of your grid range |
| **Grid Levels** | `5` | Number of grid lines |
| **Investment** | `500` | Amount to invest (THB) |

### Step 3: Start the Bot

1. Click **Start Bot** button
2. Confirm the settings in the popup
3. Wait for the bot to initialize (should take 1-2 seconds)

### Step 4: Monitor Activity

Watch the **Activity Feed** in the right sidebar:
- 🟢 **Grid BUY** = Bot bought at low price
- 🔴 **Grid SELL** = Bot sold at high price
- ⏳ **WAITING** = Bot waiting for price to hit grid level

---

## 💰 Wallet Page

Access your wallet by clicking **Wallet** in the sidebar, or press `Ctrl+Alt+W`

### Features:

- **Total THB**: Sum of all THB across exchanges
- **Total USDT**: Sum of all USDT across exchanges
- **Per-Exchange Breakdown**: See balance on each exchange
- **Refresh Button**: Force refresh all balances

### Setup Exchange API Keys:

1. Go to **Settings** → **API Keys**
2. Click **Add API Key**
3. Select exchange (Binance TH, Bitkub, etc.)
4. Enter API Key and Secret
5. Click **Save**

---

## 📈 Analytics Dashboard

Access analytics by clicking **Analytics** in the sidebar

### Metrics Shown:

| Metric | What It Means |
|--------|---------------|
| **Total Trades** | Number of trades executed |
| **Win Rate** | Percentage of profitable trades |
| **Profit Factor** | Gross profit / Gross loss |
| **Sharpe Ratio** | Risk-adjusted return |
| **Max Drawdown** | Worst peak-to-trough decline |

### Performance Chart:

- Shows portfolio value over time
- Green line = profitable
- Red line = loss
- Dashed line = initial investment

### Time Ranges:

Click to switch between: **7d**, **30d**, **90d**, **1y**, **all**

---

## ⌨️ Keyboard Shortcuts

Press `?` anytime to see all shortcuts:

| Shortcut | Action |
|----------|--------|
| `Ctrl+K` | Open command palette |
| `Ctrl+B` | Toggle sidebar |
| `Ctrl+Alt+G` | Go to Dashboard |
| `Ctrl+Alt+T` | Go to Trading |
| `Ctrl+Alt+P` | Go to Portfolio |
| `Ctrl+Alt+W` | Go to Wallet |
| `Ctrl+Alt+F` | Go to Finance |
| `Ctrl+Alt+S` | Go to Settings |
| `Ctrl+Shift+S` | Start/Stop bot (Trading page) |
| `D` | Toggle dark/light theme |
| `L` | Logout |

---

## 🌗 Theme

Toggle between light and dark mode:

1. Click the ☀️/🌙 icon in the top bar
2. Or press `D` on keyboard
3. Theme is saved to localStorage

---

## 💾 Export/Import Configuration

### Export:

1. Go to **Settings** → **Advanced**
2. Click **Export Config**
3. Save the JSON file

### Import:

1. Go to **Settings** → **Advanced**
2. Click **Import Config**
3. Select your JSON file
4. Configuration will be applied

---

## 🔔 Notifications

### Toast Notifications

Appear in top-right corner for:
- Bot started/stopped
- Trade executed
- Error occurred
- Configuration saved

### Activity Feed

Located on Trading page (right sidebar):
- Real-time bot activities
- Trade notifications
- Error messages

---

## 📱 Mobile Usage

The app is mobile-responsive. Access on your phone at:
- `http://your-server-ip:3000`

Bottom navigation includes:
- Dashboard
- Trading
- Wallet
- Finance
- Settings

---

## 🛠️ Troubleshooting

### Bot Won't Start

**Problem**: Clicking Start Bot does nothing

**Solution**:
1. Check if you have API keys configured (Settings → API Keys)
2. Verify exchange connection (Wallet page should show balances)
3. Check browser console for errors (F12 → Console)
4. Try refreshing the page

### No Balances Showing

**Problem**: Wallet page shows "No balances found"

**Solution**:
1. Ensure API keys are set (Settings → API Keys)
2. Click Refresh button on Wallet page
3. Verify API keys are correct on exchange website
4. Check backend logs: `docker compose logs backend --tail=50`

### Price Chart Not Loading

**Problem**: Charts show blank

**Solution**:
1. Check internet connection (charts load external data)
2. Try hard refresh: `Ctrl+Shift+R`
3. Check if TradingView widget is blocked by ad blocker

### Can't Login

**Problem**: Login fails or redirects to homepage

**Solution**:
1. Verify credentials match what's in `.env`
2. Clear browser cache and cookies
3. Check if admin was created: `docker compose logs backend | grep "admin"`
4. Reset password if needed

---

## 📚 Glossary

| Term | Definition |
|------|------------|
| **Grid Trading** | Automated buying low, selling high within a price range |
| **Paper Trading** | Simulated trading without real money |
| **Bot Mode** | How the bot operates: GRID, SIGNAL, or AUTO |
| **Activity Feed** | Real-time log of bot activities |
| **Arbitrage** | Profiting from price differences across exchanges |
| **Win Rate** | Percentage of trades that are profitable |
| **Drawdown** | Decline from peak to trough in portfolio value |

---

## 🆘 Need Help?

1. **Check this guide first**
2. **View browser console** (F12) for errors
3. **Check backend logs**: `docker compose logs -f backend`
4. **Check frontend logs**: `docker compose logs -f frontend`
5. **Open an issue** on GitHub

---

**Happy Trading! 🚀**
