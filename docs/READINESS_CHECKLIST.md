# Readiness Checklists

> **Current gate: WAIT — Capital Protection Mode**
>
> Last updated: 2026-06-23

This document defines the versioned gate criteria for advancing through each stage of the RUNBOOK decision tree. Each checklist must be fully satisfied before proceeding to the next stage.

**Do not skip stages. Do not self-approve. Evidence required for each item.**

---

## Live Risk Source

Readiness decisions use `/api/command-center` and the **paper bot** risk source for Polymarket / paper-capital state.

| Source | Scope | Current state |
|--------|-------|---------------|
| `paper_bot` | Polymarket / paper-capital protection | Bankroll $84.54, peak $100.45, drawdown 15.84%, kill switch ACTIVE, 14 active positions |
| `risk_manager` / grid bot | BTCTHB grid risk only | Separate risk source; do not use its 0% drawdown to clear paper-bot gates |

---

## Gate 0: Signal Performance Baseline

**Decision tree state:** `WAIT` → (signal accuracy must support progression)

Signal performance is tracked automatically by the Signal Performance Tracker.
Signals are logged from 6 sources (Polymarket, DexScreener, curated, Yahoo Finance, Binance TH, macro)
evaluated against live prices after 24h and 7d horizons.

### Prerequisites

- [ ] At least 100 signals logged across 3+ sources
- [ ] 24h evaluation accuracy > 45% (better than random)
- [ ] 7d evaluation accuracy > 40% (directional signal has edge)
- [ ] At least 1 source shows > 50% accuracy (identifiable edge)
- [ ] Auto-evaluation cron running (every 5 min)

### Verification

```bash
# Check signal stats
curl -s http://localhost:8004/api/signal-tracker/stats | python -m json.tool

# Check auto-evaluation is running
docker compose logs strategy --tail 50 | grep "Signal evaluation"
```

### Evidence to log

- Total signals logged per source
- 24h accuracy % and 7d accuracy %
- Best-performing source and its accuracy

---

## Gate 1: Before Enabling Dry-Run (`POLY_DRY_RUN=true`)

**Decision tree state:** `WAIT` → `REVIEW_SIGNALS` → `ENABLE_DRY_RUN`

### Prerequisites

- [ ] Kill switch has been reset (confirm via `monitor.py` output: `Kill switch: OFF`)
- [ ] Active positions ≤ 8 (legacy positions resolved or closed)
- [ ] Per-signal PnL reviewed for all signal types
- [x] Losing signals (net PnL < -$5) disabled or documented with rationale — `momentum` disabled after -$10.93 over 4 trades, 0% WR
- [ ] Market blocklist confirmed: `politics,sports,entertainment,celebrities`
- [ ] Daily loss limit confirmed at $5 (see `.env`)
- [ ] Max positions confirmed at 8 (see `.env`)
- [ ] `POLY_DRY_RUN=true` set in `.env` (safe-by-default, see `.env.example`)

### Verification

```bash
# Run monitor — decision should be ENABLE_DRY_RUN or better
docker compose exec strategy python /app/scripts/monitor.py

# Check env
docker compose exec strategy env | grep POLY_DRY_RUN
```

### Evidence to log

- Date dry-run enabled
- Signal types disabled (if any)
- Initial bankroll at dry-run start

---

## Gate 2: Before Resetting Paper Kill Switch

**Decision tree state:** `WAIT` → `REVIEW_SIGNALS`

### Prerequisites

- [ ] Dry-run logs reviewed for at least 2 weeks
- [ ] No bad category leakage (blocklist working correctly)
- [ ] Max positions conservative (≤ 8)
- [ ] Daily loss limit confirmed ($5)
- [ ] No unexplained drawdown > 5% during dry-run
- [ ] Per-signal PnL shows at least 3 signal types profitable
- [ ] Win rate > 52% over 50+ would-trade entries (if available)

### Verification

```bash
# Check dry-run would-trade log
docker compose exec strategy cat /app/logs/dry_run.log

# Run monitor — decision should be ENABLE_DRY_RUN with stable metrics
docker compose exec strategy python /app/scripts/monitor.py
```

### Evidence to log

- Dry-run duration (start date → today)
- Would-trade entries count
- Win rate %
- Max drawdown during dry-run

---

## Gate 3: Before Micro-Live (Real Money)

**Decision tree state:** `ENABLE_DRY_RUN` → `RESET_PAPER` → `MICRO-LIVE`

**Real money trading is FORBIDDEN until ALL are satisfied.**

### Prerequisites

- [ ] Dry-run mode stable for **2-4 weeks** with positive expected value
- [ ] Per-signal PnL shows at least 3 signal types profitable
- [ ] Max drawdown in dry-run < 5%
- [ ] Win rate > 52% over 50+ would-trade entries
- [ ] Market blocklist filtering confirmed working
- [ ] Kill switch tested and confirmed responsive (triggered correctly in test)
- [ ] Starting capital is money you can 100% afford to lose
- [ ] Position size: $1-2 per trade (no exceptions)
- [ ] Max positions: 3-5 (conservative, no scaling up)
- [ ] Daily loss limit: $2-3 (tighter than paper)
- [ ] Manual approval required for each trade (no auto-execution)
- [ ] `POLY_DRY_RUN=false` only after all above checked

### Verification

```bash
# Final monitor check before going live
docker compose exec strategy python /app/scripts/monitor.py

# Verify env is correct for micro-live
docker compose exec strategy env | grep POLY_
```

### Evidence to log

- Date micro-live started
- Starting bankroll
- Position size limit
- Max positions limit
- Daily loss limit

---

## Gate 4: Production Deploy Readiness

**Deploy is manual-only. Requires explicit `workflow_dispatch` with `deploy_production=true`.**

### Prerequisites

- [ ] CI pipeline green (Frontend Tests + Backend Tests + Docker Images)
- [ ] All strategy, command-center contract, and frontend safety checks passing in CI
- [ ] `.env.example` reviewed and safe-by-default
- [ ] `PRODUCTION_HOST` secret configured in GitHub
- [ ] Domain name registered and DNS configured
- [ ] TLS/HTTPS certificates ready (Caddy auto-provisions)
- [ ] Database backup strategy confirmed
- [ ] Redis persistence enabled
- [ ] Monitoring/alerting configured (Prometheus + Grafana or equivalent)
- [ ] Emergency stop procedure documented and tested

### Verification

```bash
# Check CI status
gh run list --limit 1

# Verify secrets exist
gh secret list
```

---

## Current Status

| Gate | Status | Blocked By |
|------|--------|------------|
| 0. Signal Performance | 🟡 Collecting | Auto-evaluation active, accuracy data pending 24h maturation |
| 1. Enable Dry-Run | 🔴 Not ready | Paper kill switch active, 14 active positions > 8, paper drawdown 15.84% > 5% |
| 2. Reset Kill Switch | 🔴 Not ready | Need dry-run evidence first |
| 3. Micro-Live | 🔴 Not ready | Need Gate 1 and Gate 2 evidence first |
| 4. Production Deploy | 🔴 Not ready | Need domain/secrets/prod env |

---

## How to Update

When completing a checklist item:

1. Check the box in this file
2. Add evidence (date, metrics, screenshots)
3. Commit with message: `docs: mark [gate] item complete — [evidence summary]`

**Never check a box without evidence.** The checklist is a safety gate, not a todo list.
