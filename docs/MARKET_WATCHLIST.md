# Market Watchlist

> Read-only research output from `scripts/market_research.py`.
> **This is NOT trading signals.** Bot must NOT trade from this list until all gates pass.

**Last scan:** 2026-06-22 17:13 UTC
**Candidates:** 0 (all 200 scanned markets correctly blocked)

## Filters

- Min liquidity: $500
- Min volume: $1,000
- Max spread: 5%
- Price range: 5%–95%
- Blocked categories: celebrities, entertainment, gaming, movies, music, politics, pop-culture, sports, tv

## Manual Review — Previous Candidates (2026-06-22)

All 6 candidates from the initial scan were reviewed and **REJECTED**:

| # | Market | Resolution | Category Leak? | Data Source | Signal | Decision |
|---|--------|-----------|----------------|-------------|--------|----------|
| 1 | Netanyahu out by end of 2026? | Clear date | **POLITICS** — head of state (keyword gap: `netanyahu`) | Speculative | No edge | REJECT |
| 2 | Xi Jinping out before 2027? | Clear date | **POLITICS** — head of state (keyword gap: `xi jinping`) | Speculative | No edge | REJECT |
| 3 | China invade Taiwan by end of 2026? | Clear event | Geopolitical — borderline politics (keyword gap: `invade`) | Speculative | No edge | REJECT |
| 4 | Erdoğan out by December 31, 2026? | Clear date | **POLITICS** — head of state (Unicode: `ğ` → `g`) | Speculative | No edge | REJECT |
| 5 | Weinstein no prison time? | Court record | **CELEBRITY/LEGAL** (keyword gap: `sentenced`) | Official court docs | Watch only | REJECT |
| 6 | Weinstein 20–30 years? | Court record | **CELEBRITY/LEGAL** (keyword gap: `sentenced`) | Official court docs | Watch only | REJECT |

### Fixes applied after review

- Added head-of-state names: `netanyahu`, `xi jinping`, `putin`, `zelensky`, `erdogan`, etc.
- Added geopolitical terms: `invade`, `invasion`, `annex`, `sanctions`, `nato`, `military strike`, `coup`, `regime`
- Added legal/celebrity terms: `sentenced`, `prison time`, `verdict`, `indictment`, `acquitted`, `parole`
- Added Unicode normalization (NFKD) to catch diacritics: `Erdoğan` → `erdogan`

### Post-fix scan result

- 200 markets scanned → **197 blocked + 3 extreme price = 0 candidates**
- Blocklist now catches indirect politics, Unicode variants, and celebrity legal cases

## Alpha Criteria

Before any market moves from watchlist to actual trading:

1. **Objective resolution** — resolved by official data, not opinion
2. **Good liquidity** — can enter/exit without significant slippage
3. **Tight spread** — not eating your edge before you start
4. **No information asymmetry** — no insider knowledge, politics, or sports
5. **Verifiable data source** — external source anyone can check
6. **Multi-signal agreement** — several signals point the same way

## Blocked Categories

- Politics (elections, legislation, appointments, heads of state, geopolitics)
- Sports (game outcomes, scores, championships)
- Entertainment (awards, box office, celebrity events)
- Celebrities (personal events, legal cases, sentencing)

## Scanner CLI Options

```bash
# Default scan
python scripts/market_research.py

# Custom limit and liquidity threshold
python scripts/market_research.py --limit 10 --min-liquidity 1000

# Docker
docker run --rm -v "$(pwd)/strategy:/app" -v "$(pwd):/workspace" -w /app \
  -e WATCHLIST_OUTPUT=/workspace/docs/MARKET_WATCHLIST.md \
  python:3.11-slim-bookworm bash -c \
  "pip install -r requirements.txt -q 2>/dev/null && python /app/scripts/market_research.py"
```

## Status

**This watchlist is for RESEARCH ONLY.**
Bot will NOT trade from this list until:
- [ ] Kill switch reset (Gate 1)
- [ ] Dry-run validated (Gate 2)
- [ ] Micro-live approved (Gate 3)

See `docs/READINESS_CHECKLIST.md` for full gate requirements.
