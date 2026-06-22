# Market Watchlist

> Read-only research output from `scripts/market_research.py`.
> **This is NOT trading signals.** Bot must NOT trade from this list until all gates pass.

**Last scan:** 2026-06-22 17:06 UTC
**Candidates:** 6

## Filters

- Min liquidity: $500
- Min volume: $1,000
- Max spread: 5%
- Price range: 5%–95%
- Blocked categories: celebrities, entertainment, gaming, movies, music, politics, pop-culture, sports, tv

## Candidates

| # | Score | Question | Yes | Liquidity | Volume | Resolution |
|---|-------|----------|-----|-----------|--------|------------|
| 1 | 7.9 | Netanyahu out by end of 2026? | 0.53 | $58,201 | $1,605,732 | good |
| 2 | 6.5 | Xi Jinping out before 2027? | 0.06 | $224,096 | $10,454,310 | good |
| 3 | 6.5 | Will China invade Taiwan by end of 2026? | 0.06 | $613,206 | $36,362,436 | good |
| 4 | 6.5 | Erdoğan out by December 31, 2026? | 0.07 | $41,413 | $520,603 | good |
| 5 | 6.0 | Will Harvey Weinstein be sentenced to no prison time? | 0.86 | $3,178 | $377,423 | good |
| 6 | 5.3 | Will Harvey Weinstein be sentenced to between 20 and 30 | 0.06 | $2,654 | $215,239 | good |

## Alpha Criteria

Before any market moves from watchlist to actual trading:

1. **Objective resolution** — resolved by official data, not opinion
2. **Good liquidity** — can enter/exit without significant slippage
3. **Tight spread** — not eating your edge before you start
4. **No information asymmetry** — no insider knowledge, politics, or sports
5. **Verifiable data source** — external source anyone can check
6. **Multi-signal agreement** — several signals point the same way

## Blocked Categories

- Politics (elections, legislation, appointments)
- Sports (game outcomes, scores, championships)
- Entertainment (awards, box office, celebrity events)
- Celebrities (personal events, legal cases)

## Status

**This watchlist is for RESEARCH ONLY.**
Bot will NOT trade from this list until:
- [ ] Kill switch reset (Gate 1)
- [ ] Dry-run validated (Gate 2)
- [ ] Micro-live approved (Gate 3)

See `docs/READINESS_CHECKLIST.md` for full gate requirements.
