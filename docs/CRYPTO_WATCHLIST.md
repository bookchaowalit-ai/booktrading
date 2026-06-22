# Crypto Watchlist

> Read-only research output from `scripts/crypto_market_research.py`.
> **This is NOT trading signals.** Bot must NOT trade from this list until all gates pass.

**Last scan:** 2026-06-22 17:25 UTC
**Pairs scanned:** 6
**Min volume filter:** ฿1,000,000

## Exchanges

| Exchange | API | Pairs | Auth |
|----------|-----|-------|------|
| Binance Global | api.binance.com | BTCUSDT, ETHUSDT | Public |
| Binance TH | api.binance.th | BTCTHB, ETHTHB, SOLTHB, BNBTHB, XRPTHB | Public (market data) |
| Bitkub | api.bitkub.com | BTC_THB, ETH_THB, SOL_THB, BNB_THB, XRP_THB | Public (market data) |

## Ranked Pairs

| # | Score | Exchange | Symbol | Price | Vol (M ฿) | Vol% | Spread% | Depth (M ฿) |
|---|-------|----------|--------|-------|-----------|------|---------|-------------|
| 1 | 8.5 | Binance Global | BTCUSDT | 64,544.31 | 976.9M | 3.6% | 0.000 | 0.23M |
| 2 | 8.5 | Binance Global | ETHUSDT | 1,736.51 | 436.2M | 4.5% | 0.001 | 0.08M |
| 3 | 8.0 | Binance Th | BTCTHB | 2,121,733.00 | 36.8M | 3.4% | 0.000 | 2.36M |
| 4 | 6.9 | Binance Th | ETHTHB | 57,133.00 | 1.7M | 3.4% | 0.012 | 2.66M |
| 5 | 6.5 | Binance Th | XRPTHB | 37.52 | 1.1M | 3.1% | 0.027 | 0.58M |
| 6 | 6.1 | Binance Th | SOLTHB | 2,393.68 | 1.4M | 3.1% | 0.079 | 0.61M |

## Cross-Exchange Spread (THB)

_Insufficient data for cross-exchange comparison._

## Scoring Methodology

Score 0–10 based on:

| Component | Weight | Notes |
|-----------|--------|-------|
| Volume | 0–3 | Log scale, higher quote volume = more tradeable |
| Volatility | 0–2.5 | Sweet spot: 1–5% daily range (grid bot friendly) |
| Spread | 0–2.5 | Tighter = less cost per fill |
| Depth | 0–2 | Deeper book = less slippage |

## Manual Review

> Fill in each row after checking live order books.

| # | Pair | Exchange | Order book verified? | Fee structure? | Grid params fit? | Decision |
|---|------|----------|---------------------|----------------|-----------------|----------|
| 1 | BTCUSDT | binance_global | ☐ | ☐ | ☐ | ☐ |
| 2 | ETHUSDT | binance_global | ☐ | ☐ | ☐ | ☐ |
| 3 | BTCTHB | binance_th | ☐ | ☐ | ☐ | ☐ |
| 4 | ETHTHB | binance_th | ☐ | ☐ | ☐ | ☐ |
| 5 | XRPTHB | binance_th | ☐ | ☐ | ☐ | ☐ |
| 6 | SOLTHB | binance_th | ☐ | ☐ | ☐ | ☐ |

### Review criteria

1. **Order book verified?** — Live bids/asks on exchange, not just API data
2. **Fee structure?** — Maker/taker fees don't eat grid profits
3. **Grid params fit?** — Volatility matches grid spacing, depth supports order sizes
4. **Decision** — PAPER (proceed to paper trading) / WATCH ONLY / REJECT

## Recommended Next Steps

1. **Paper trade top pairs** — Use existing grid_bot.py with Binance TH testnet
2. **Validate spread stability** — Check if spread holds over 24h, not just snapshot
3. **Compare THB vs USDT** — FX risk assessment for THB-denominated pairs
4. **Fee impact analysis** — Grid profit must exceed maker+taker fees

## Status

**This watchlist is for RESEARCH ONLY.**
Bot will NOT trade from this list until:
- [ ] Kill switch reset (Gate 1)
- [ ] Dry-run validated (Gate 2)
- [ ] Micro-live approved (Gate 3)

See `docs/READINESS_CHECKLIST.md` for full gate requirements.
