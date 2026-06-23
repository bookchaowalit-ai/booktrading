# Market Watchlist

> Read-only research output from `scripts/market_research.py`.
> **This is NOT trading signals.** Bot must NOT trade from this list until all gates pass.

**Last scan:** 2026-06-22 17:13 UTC
**Candidates:** 0

## Filters

- Min liquidity: $1,000
- Min volume: $1,000
- Max spread: 5%
- Price range: 5%–95%
- Blocked categories: celebrities, entertainment, gaming, movies, music, politics, pop-culture, sports, tv

## Candidates

_No markets passed all filters this scan._

## Manual Review

> Fill in each row after checking the live market page.

| # | Market | Resolution clear? | Order book checked? | Data source? | Signal reason? | Decision |
|---|--------|-------------------|--------------------|--------------|----------------|----------|

### Review criteria

1. **Resolution clear?** — No ambiguous wording, objective outcome
2. **Order book checked?** — Real bid/ask on Polymarket page, not just Gamma liquidity
3. **Data source?** — Official data/API/report, not speculation or rumors
4. **Signal reason?** — Predictive edge exists beyond liquidity/volume
5. **Decision** — PASS (proceed to alpha check) / WATCH ONLY / REJECT

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
