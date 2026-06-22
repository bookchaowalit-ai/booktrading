# Polymarket Paper Bot — Operations Runbook

> **Current mode: CAPITAL PROTECTION / EVIDENCE COLLECTION**
>
> Last updated: 2026-06-20

---

## System State Snapshot

| Metric                | Value         |
|-----------------------|---------------|
| Kill switch           | **ACTIVE**    |
| Kill reason           | Max drawdown 15.8% (limit 5%) |
| Bankroll              | ~$84.54       |
| Active positions      | 20 (legacy)   |
| Resolved positions    | 0             |
| Max positions allowed | 8             |
| Daily loss limit      | $5            |
| Consecutive loss limit| 3             |

---

## Daily Monitor Command

```bash
cd domains/book-dev/book-products/booktrading
docker compose exec strategy python scripts/monitor.py
```

Expected output includes:
- Active / resolved position counts
- Bankroll, PnL, drawdown %
- Kill switch status + reason
- Consecutive losses, daily PnL
- Per-signal PnL breakdown
- Decision recommendation

---

## Decision Tree

```
START
  │
  ├─ Kill switch ACTIVE? ──────────► WAIT
  │                                   └─ Do nothing. Log the state.
  │
  ├─ Active positions > 8? ────────► WAIT
  │                                   └─ Legacy positions need to resolve.
  │                                      Check back daily.
  │
  ├─ Resolved trades < 50%? ───────► WAIT
  │                                   └─ Not enough data to evaluate signals.
  │
  ├─ Per-signal PnL available? ────► REVIEW_SIGNALS
  │                                   └─ Identify worst performers.
  │                                      Disable signals with consistent losses.
  │
  ├─ Signal PnL reviewed,          ► ENABLE_DRY_RUN
  │  positions ≤ 8?
  │                                   └─ Set POLY_DRY_RUN=true
  │                                      Run for 2-4 weeks. Log would-trade entries.
  │
  ├─ Dry-run stable 2-4 weeks? ───► RESET_PAPER
  │                                   └─ Reset paper state. Start fresh paper cycle.
  │
  └─ Paper stable 2-4 weeks        ► MICRO-LIVE (see prerequisites below)
     + all prerequisites met?
```

---

## When NOT to Reset Kill Switch

**Do NOT reset the kill switch if ANY of these are true:**

1. Active positions still > 8 (legacy positions unresolved)
2. You haven't reviewed per-signal PnL for all signal types
3. Dry-run mode hasn't been run for at least 2 weeks
4. Bankroll drawdown cause hasn't been identified
5. You're doing it "just to see what happens"

**The kill switch is working correctly.** It stopped trading at 15.8% drawdown — that's the system doing its job. Resetting without evidence is how money is lost.

---

## When to Enable POLY_DRY_RUN=true

Only after ALL of these are met:

- [ ] Kill switch has been reset
- [ ] Active positions ≤ 8
- [ ] Per-signal PnL reviewed — worst signals disabled
- [ ] Market blocklist confirmed: `politics,sports,entertainment,celebrities`
- [ ] You're ready to log would-trade entries daily for 2-4 weeks

Enable with:
```bash
# In .env
POLY_DRY_RUN=true
```

---

## When to Disable Losing Signals

After kill switch is reset and resolved trades have PnL data:

1. Run monitor — check per-signal PnL breakdown
2. Any signal type with **net negative PnL over 10+ resolved trades** → disable
3. Edit signal weights or remove signal from the alpha engine
4. Re-run dry-run mode to validate improvement

---

## Micro-Live Prerequisites

**Real money trading is FORBIDDEN until ALL are satisfied:**

- [ ] Dry-run mode stable for **2-4 weeks** with positive expected value
- [ ] Per-signal PnL shows at least 3 signal types profitable
- [ ] Max drawdown in dry-run < 5%
- [ ] Win rate > 52% over 50+ would-trade entries
- [ ] Market blocklist filtering confirmed working
- [ ] Kill switch tested and confirmed responsive
- [ ] Starting capital is money you can 100% afford to lose

Even then: start with **minimum position sizes** ($1-2 per trade).

---

## Emergency Stop & Reset Procedure

### Emergency Stop (halt everything NOW)

```bash
# Stop the bot container
docker compose stop strategy

# Or set kill switch manually via Redis
docker compose exec redis redis-cli SET poly_paper:kill_override 1
```

### Reset Kill Switch (ONLY when decision tree says GO)

```bash
# 1. Verify conditions are met (run monitor first)
docker compose exec strategy python scripts/monitor.py

# 2. If monitor says REVIEW_SIGNALS or better, reset via Python
docker compose exec strategy python -c "
from app.polymarket.paper_bot import PolymarketPaperBot
bot = PolymarketPaperBot()
bot.reset_kill_switch()
print('Kill switch reset. Monitor closely.')
"
```

### Full Paper Reset (nuclear option — clears all positions)

```bash
# ONLY after dry-run validation is complete
docker compose exec redis redis-cli DEL poly_paper:state
```

**WARNING:** This deletes all position history. Only do this when you're starting a completely fresh paper cycle after dry-run validation.

---

## Safety Commits

| Commit    | Description                          |
|-----------|--------------------------------------|
| `1aa12d8` | Readiness safeguards: kill switch, dry-run, blocklist/allowlist |
| `b3e0907` | Monitor tooling: daily monitoring script |
| `fcd4cf5` | Safety filter tests: 20 tests + dry-run AlphaSignal bug fix |

Full test suite: **80/80 passing** (33 kill-switch + 20 safety filters + 27 monitor decision)

---

## Key Files

| File | Purpose |
|------|---------|
| `strategy/app/polymarket/paper_bot.py` | Core bot logic |
| `strategy/scripts/monitor.py` | Daily monitoring script |
| `strategy/tests/test_kill_switch.py` | 13 kill switch tests |
| `strategy/tests/test_monitor_decision.py` | 27 monitor decision tree tests |
| `strategy/tests/test_safety_filters.py` | 20 safety filter tests |
| `strategy/RUNBOOK.md` | This file |
| `docs/READINESS_CHECKLIST.md` | Versioned gate criteria for each stage |

---

## Rules

1. **No real money** until micro-live prerequisites are all checked
2. **No kill switch reset** without evidence from per-signal PnL
3. **No architecture changes** while in capital protection mode
4. **Monitor daily** — even if nothing changed, log the state
5. **Small changes only** — tests, docs, config. No big refactors.
6. **Never set `POLY_DRY_RUN=false`** for real money until RUNBOOK micro-live prerequisites are met. See `.env.example` for safe-by-default config.
