# Evidence Log

> Record state changes from daily monitor runs. Commit when positions change or signals become clear.
>
> **Rule:** Only log when something changed. No need to commit daily — commit on state transitions.

---

## Template

```
## YYYY-MM-DD
Active positions: X
Resolved trades: Y
Kill switch: ACTIVE/OFF
Decision: WAIT / REVIEW_SIGNALS / ENABLE_DRY_RUN
Bankroll: $XX.XX
Notes: [what changed, why, what to watch]
```

---

## Log

### 2026-06-20 (baseline)
- Active positions: 20
- Resolved trades: 0
- Kill switch: ACTIVE (max drawdown 15.8%)
- Decision: WAIT
- Bankroll: $84.54
- Notes: Baseline snapshot. All 20 positions are legacy exposure. Waiting for resolutions.

---

### 2026-06-23 — BTCTHB Paper Grid Supervised Trial (30 min)

**Config:**
- Symbol: BTCTHB (Binance TH)
- Grid: 2 levels × 2.0% spacing
- Order size: 0.00005 BTC (~฿106/order)
- Max exposure cap: ฿3,000
- Fee rate: 0.10% per side (0.20% round-trip)

**Baseline:**
- Time: 2026-06-22T17:42:34 UTC
- Price: ฿2,117,697
- Grid levels: BUY @ ฿2,032,989 / ฿2,075,343 | SELL @ ฿2,160,051 / ฿2,202,405
- Paper balance: ฿10,000

**Results (30.2 min, 30 ticks):**
- Ticks: 30 | Skipped: 0 | Errors: 0
- Price range: ฿2,117,242 – ฿2,126,460 (+0.364%)
- Orders placed: 4 | Fills: 0
- Final position: 0.000000 BTC
- Total fees: ฿0.00
- Realized PnL: ฿0.00
- Max exposure: ฿0.00
- Safety violations: 0

**Analysis:**
- Price stayed within ±0.4% of center — well inside the 2% grid spacing
- No fills expected at this volatility (avg hourly range ~0.45%)
- Grid correctly waits for meaningful moves before placing orders
- All systems nominal: price fetch, grid logic, safety guards, state tracking

**Verdict:** PASS — infrastructure works, safety guards hold, conservative config behaves as designed.
Next: longer trial (1 trading day) to capture fills during higher-volatility window.

---
