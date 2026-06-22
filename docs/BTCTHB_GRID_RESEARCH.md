# BTCTHB Grid Research

> Read-only research for paper/grid validation on Binance Thailand.
> **This is NOT trading advice.** Bot must NOT trade until all gates pass.

**Last updated:** 2026-06-22 17:25 UTC
**Pair:** BTCTHB (Binance Thailand)
**Status:** PAPER/RESEARCH ONLY

---

## Market Snapshot (Live)

| Metric | Value |
|--------|-------|
| Last price | ฿2,120,337 |
| 24h high | ฿2,152,000 |
| 24h low | ฿2,080,116 |
| 24h range | 3.456% |
| 24h volume | ฿37.17M (17.58 BTC) |
| 24h trades | 4,343 |
| Avg hourly range | 0.453% |
| Max hourly range | 1.287% |

### Order Book (Top 20 levels)

| Metric | Value |
|--------|-------|
| Best bid | ฿2,120,000.00 |
| Best ask | ฿2,120,001.00 |
| **Spread** | **฿1.00 (0.0000%)** |
| Bid depth (top 20) | ฿9.26M |
| Ask depth (top 20) | ฿12.53M |
| **Total depth** | **฿21.79M** |

**Key observation:** Spread is essentially zero (฿1 on ฿2.1M). This is excellent for grid trading — no edge lost to spread on fills.

---

## Fee Structure (Binance TH)

| Fee type | Rate |
|----------|------|
| Maker fee | 0.10% |
| Taker fee | 0.10% |
| **Round-trip (buy+sell)** | **0.20%** |

### Minimum grid spacing for profitability

```
Min spacing > round-trip fee + spread
Min spacing > 0.20% + 0.00%
Min spacing > 0.20%

Conservative: 1.0% – 2.0%
```

---

## Grid Parameters (from `real_grid_bot.py`)

Current config for BTCTHB:

| Parameter | Value | Notes |
|-----------|-------|-------|
| `grid_spacing_pct` | 2.0% | ~฿42,407 between levels |
| `grid_levels` | 2 | 2 above + 2 below = 4 active levels |
| `order_size` | 0.00005 BTC | ~฿106 per order |
| `max_position` | 0.001 BTC | ~฿2,120 max exposure |
| `max_daily_loss_usd` | $50 | Stop trading if exceeded |
| `volatility_mode` | ATR | Dynamic spacing based on ATR(14) |
| `poll_interval_sec` | 60 | Check every 60s |

### Grid layout at current price (฿2,120,337)

```
Level    Price (฿)        Distance from mid
─────────────────────────────────────────────
SELL +2  2,205,144        +฿84,807 (+4.0%)
SELL +1  2,162,741        +฿42,404 (+2.0%)
───────── MID ─────────── 2,120,337 ─────────
BUY  -1  2,077,934        -฿42,403 (-2.0%)
BUY  -2  2,035,527        -฿84,810 (-4.0%)
```

Grid width: ฿169,617 (8.0% of price)

---

## Profitability Analysis

### Per grid cycle (one buy + one sell fill)

```
Order size:         0.00005 BTC = ฿106
Gross profit:       2.0% × ฿106 = ฿2.12
Round-trip fee:     0.2% × ฿106 = ฿0.21
Net profit/cycle:   ฿1.91 (1.8% after fees)
```

### Expected orders/day

Based on 24h range (3.456%) and grid spacing (2.0%):

```
Conservative estimate: 1–2 grid cycles/day
Optimistic estimate:   3–4 cycles/day (if price oscillates within grid)

Expected daily profit: ฿1.91 × 2 = ฿3.82/day (conservative)
                       ฿1.91 × 4 = ฿7.64/day (optimistic)
```

### Monthly projection (paper)

```
Conservative: ฿3.82 × 30 = ฿114.60/month
Optimistic:   ฿7.64 × 30 = ฿229.20/month
```

**Note:** These are paper numbers with tiny position sizes. Real trading would scale up but also scale risk.

---

## Risk Analysis

### Worst-case scenario

If price drops below entire grid and stays there:

```
Max position:     0.001 BTC = ฿2,120
Grid bottom:      -4.0% from entry
Unrealized loss:  4.0% × ฿2,120 = ฿84.80

If all 4 buy orders fill at -2%, -4%:
Total exposure:   0.0002 BTC = ฿424
Average loss:     ~3% × ฿424 = ฿12.72
```

### Daily loss limit

```
max_daily_loss_usd = $50 ≈ ฿1,770
This is 83% of max position (0.001 BTC)
```

### Comparison: grid_bot.py defaults (more aggressive)

| Parameter | real_grid_bot | grid_bot (paper) |
|-----------|---------------|------------------|
| spacing | 2.0% | 1.5% |
| levels | 2 | 5 |
| order_size | 0.00005 BTC | 0.001 BTC |
| max_position | 0.001 BTC | 0.05 BTC |
| Max exposure | ฿2,120 | ฿106,017 |
| Worst-case DD | ฿84.80 (4%) | ฿4,240 (4%) |

**Recommendation:** Use `real_grid_bot.py` config for paper validation. The `grid_bot.py` defaults are 50x larger exposure — not suitable for initial testing.

---

## Validation Checklist

Before moving from paper to dry-run:

- [ ] Paper grid runs for 7+ days without hitting daily loss limit
- [ ] Actual fill rate matches expected (1–4 cycles/day)
- [ ] Net profit per cycle matches theoretical (฿1.91 ± 0.05)
- [ ] No unexpected slippage on paper fills
- [ ] ATR-based spacing adapts correctly to volatility changes
- [ ] Grid re-centers properly after large price moves

---

## Next Steps

1. **Run paper grid** — Use `real_grid_bot.py` with BTCTHB config on testnet
2. **Monitor 7 days** — Collect fill rate, profit, drawdown data
3. **Compare to theory** — Does actual match the ฿1.91/cycle projection?
4. **Scale decision** — If paper validates, consider dry-run with 10x size (0.0005 BTC)

---

## Status

**This research is for PAPER VALIDATION ONLY.**
Bot will NOT trade from this research until:
- [ ] Kill switch reset (Gate 1)
- [ ] Paper validation complete (7+ days)
- [ ] Dry-run validated (Gate 2)
- [ ] Micro-live approved (Gate 3)

See `docs/READINESS_CHECKLIST.md` for full gate requirements.
