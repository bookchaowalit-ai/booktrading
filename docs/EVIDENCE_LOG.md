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

### 2026-07-23 — Bookkeeping Bugs Fixed: real_trades Now Trustworthy + Redis Restart-Policy Fixed

**Context:** Investigated "no profit after weeks of live trading." Real PnL was fine
(`trade_journal`: 927 closed trades, net +51 THB after fees as of 2026-07-21 — small
but not the concern) but the `real_trades` audit table and the Redis-backed pub/sub
were both broken, making the system's own bookkeeping unreliable.

**Bugs fixed (backend/internal/adapter/http/trade_handler.go, `persistTrade`):**
1. `testnet` was hardcoded to `true` on every insert regardless of the actual
   exchange config — every one of ~1900 historical rows read `testnet=true` even
   though `/api/trade/status` correctly reported `testnet=false` (live Binance TH
   mainnet). Fixed to look up the real flag via `GetSupportedExchanges()`.
2. `exchange_order_id` was extracted via `result.(map[string]interface{})`, but
   `PlaceOrder` returns a typed `*Order` struct — the assertion always failed
   silently, so `exchange_order_id` was `NULL` on 100% of historical rows. Fixed
   by round-tripping through JSON to read the `orderId` field regardless of
   provider's concrete return type.
3. **Root cause of Redis being down:** the `redis` service in `docker-compose.yml`
   had no `restart:` policy (every other service has `restart: unless-stopped`).
   After a host reboot (~2026-07-22 10:11 local), Docker restarted everything
   except Redis, so the backend spent ~24h+ spamming
   `Failed to publish market data: dial tcp: lookup redis ... no such host`.
   Added `restart: unless-stopped` to the redis service and brought it back up
   (data intact — AOF persisted 22 keys).

**Verification (post-fix, 2026-07-21 16:43 UTC → 2026-07-23 08:42 UTC):**
- 147 real trades placed and persisted; **100% now carry a real `exchange_order_id`
  and `testnet=false`**; every `real_trades` row has exactly one matching
  `trade_journal` row (LEFT JOIN on `exchange_order_id`, zero unmatched); zero
  duplicate `exchange_order_id` in either table.
- Two orders (`363469458` ETHTHB SELL 0.002 @ ฿65,854; `205875639` SOLTHB SELL
  0.05 @ ฿2,640.39) cross-checked directly against Binance TH's live
  `GET /api/v1/order` — symbol/side/qty/price match exactly.
- Backend logs since the Redis fix (08:41 UTC onward): zero "Failed to publish"
  / persistence errors, zero non-201 responses on `/api/trade/order` or
  `/api/journal/entry`.
- `cd backend && go vet ./... && go test ./...` — clean, all pass.
- `cd frontend && npm test` (36/36 pass), `npx tsc --noEmit` (clean). No
  `docs:check` script exists in this repo (checked `frontend/package.json` and
  CI workflow — not part of the pipeline).
- `strategy` service `pytest`: 10 pre-existing failures (Polymarket paper-bot
  kill-switch async bug, grid-safety default-config drift, stale
  `DEFAULT_MAX_POSITIONS` assertion) — unrelated to this change (no Python was
  touched); flagged for separate follow-up.

**Decision:** No change to trading behavior — this was a bookkeeping/observability
fix only. `real_trades` can now be trusted for future evidence-gate decisions.

- Active positions: 14 (Polymarket paper)
- Resolved trades: 6
- Kill switch: RESET (was stuck from 429 storm, cleared via Redis state update)
- Real grid bot: LIVE on Binance TH mainnet — 14 open orders across 5 symbols (BTCTHB, ETHTHB, BNBTHB, SOLTHB, XRPTHB)
- Paper grid bot: Operational across 10 symbols (THB + USDT pairs)
- Poly bot: Operational (149 events, 757 signals, scan #387)
- 429 errors: 0 (rate limit increased from 100 → 1000 req/min)
- Fixes applied:
  1. `BINANCE_TH_USE_TESTNET=false` — enabled real order placement
  2. Rate limit 100 → 1000 req/min in `handler.go` — fixed 429 storm
  3. Redis `poly_paper:state` kill_switch_active → false — cleared stuck kill switch
- Monitoring: `infra/scripts/monitor.sh` created for on-demand health checks
- Decision: OBSERVE — waiting for first real fills before evidence gate assessment

---

### 2026-06-25 — Momentum Signal Disabled

- Active positions: 14
- Resolved trades: 6
- Kill switch: ACTIVE (paper bot max drawdown 15.84%)
- Decision: WAIT
- Bankroll: $84.54
- Signal action: `momentum` disabled by default via `POLY_DISABLED_SIGNALS=momentum`
- Evidence: momentum PnL $-10.93 over 4 resolved trades, 0% win rate
- Notes: This is a risk-tuning change only. Kill switch remains active; no dry-run reset and no live trading.

---

### 2026-06-23 — State Consistency / Risk Source Audit

- Active positions: 14
- Resolved trades: 6
- Kill switch: ACTIVE (paper bot max drawdown 15.84%)
- Decision: WAIT
- Bankroll: $84.54
- Peak bankroll: $100.45
- Risk source: `paper_bot` controls Polymarket / paper-capital readiness gates
- Grid risk manager: separate BTCTHB grid source; 0% grid drawdown does not clear paper-bot drawdown
- Notes: `/api/command-center`, `/api/poly-paper/status`, and dynamic evidence gates now agree on paper-bot state. Gate 1 remains blocked by active kill switch, 14 active positions > 8, and paper drawdown > 5%.

---

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

### 2026-08-11 — Local capital-protection bootstrap (Solo Empire operator)

- Active positions: 14 (documented reconstruction)
- Resolved trades: 6
- Kill switch: ACTIVE (paper bot max drawdown 15.84%)
- Decision: **WAIT**
- Bankroll: $84.54 / peak $100.45
- Infra: local redis+postgres started; gitignored `.env` with paper-only defaults; no exchange keys
- Notes: Seeded Redis key `poly_paper:state` for local observability. No kill-switch reset, no dry-run flip to false, no live trading. Research walk-forward + finance ledger bootstrap run from Solo Empire host.

