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
