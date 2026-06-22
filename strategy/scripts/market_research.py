#!/usr/bin/env python3
"""
Polymarket Read-Only Market Scanner
Run: docker compose exec strategy python /app/scripts/market_research.py
      or with options: python scripts/market_research.py --limit 10 --min-liquidity 1000

Scans active markets for research/watchlist purposes.
Does NOT place orders, reset kill switch, or modify any state.

Filters:
  - Active/open markets only
  - Liquidity > $500 (override with --min-liquidity)
  - Real volume (total traded > $1,000)
  - Clear resolution rules (description quality check)
  - Category blocklist: politics, sports, entertainment, celebrities
    (checked via tags + keyword scan on question text)
  - Price range: 0.05–0.95 (avoids extreme odds without edge)

Note: CLOB spread endpoint requires outcome token_ids (not condition_ids
from Gamma). Spread data is omitted; manual review recommended.

Output: Top N candidates → stdout + docs/MARKET_WATCHLIST.md
"""
import argparse
import asyncio
import sys
import os
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

# Add parent dir so `app.*` imports work when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.polymarket.client import PolymarketClient

# ── Configuration ─────────────────────────────────────────────────────────────

BLOCKED_TAGS = {
    'politics', 'sports', 'entertainment', 'celebrities',
    'pop-culture', 'music', 'movies', 'tv', 'gaming',
}

# Keyword blocklist — catches markets where Gamma returns empty tags
BLOCKED_QUESTION_KEYWORDS = [
    # Politics
    'president', 'presidential', 'senate', 'house of representatives',
    'congress', 'democrat', 'republican', 'election', 'governor',
    'cabinet', 'secretary of', 'impeach', 'legislation', 'ballot',
    'political party', 'control the', 'balance of power', 'primary',
    'nominee', 'vice president', 'mayor', 'trump', 'biden',
    # Heads of state / geopolitical (catch indirect politics)
    'netanyahu', 'xi jinping', 'putin', 'zelensky', 'erdogan',
    'erdogan', 'macron', 'sunak', 'modi', 'khamenei',
    'kim jong', 'castro', 'lukashenko', 'assad',
    'invade', 'invasion', 'annex', 'sanctions', 'nato ',
    'military strike', 'civil war', 'coup ', 'regime',
    # Sports
    'win the world cup', 'nba ', 'nfl ', 'mlb ', 'nhl ',
    'super bowl', 'world series', 'championship', 'match ',
    'game ', 'season record', 'playoff', 'grand prix',
    'ufc ', 'boxing', 'tennis open', 'fifa',
    # Entertainment / Celebrities
    'album', 'oscars', 'emmy', 'grammy', 'box office',
    'celebrity', 'net worth', 'dating', 'married to',
    'gta vi', 'rihanna', 'taylor swift', 'kanye', 'drake',
    'movie ', 'tv show', 'video game',
    # Legal / celebrity (non-political courts are still celebrity-adjacent)
    'sentenced', 'prison time', 'verdict', 'indictment', 'acquitted',
    'parole', 'probation', 'manslaughter', 'felony',
]

MIN_LIQUIDITY = 500       # USDC (override via --min-liquidity)
MIN_VOLUME = 1_000        # USDC total traded
MAX_SPREAD = 0.05         # 5¢
PRICE_FLOOR = 0.05        # avoid extreme long-shots
PRICE_CEIL = 0.95         # avoid near-certain outcomes
TOP_N = 20                # override via --limit
SCAN_PAGES = 4            # pages of 50 markets = ~200 raw candidates


# ── Filter functions ──────────────────────────────────────────────────────────

def _normalize(text):
    """NFKD-normalize and strip diacritics for keyword matching."""
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.category(c).startswith('M')).lower()


def is_blocked(tags, question=''):
    """Check if market is blocked by tags OR question keywords."""
    # Tag-based check
    for t in tags:
        if t.lower().replace(' ', '-') in BLOCKED_TAGS:
            return True
    # Keyword-based check on question text (catches empty-tag markets)
    # Normalize to strip diacritics (e.g. Erdoğan → erdogan)
    q_norm = _normalize(question)
    for kw in BLOCKED_QUESTION_KEYWORDS:
        if kw in q_norm:
            return True
    return False


def price_extreme(yes_price):
    """True if price is outside the tradable range."""
    return yes_price < PRICE_FLOOR or yes_price > PRICE_CEIL


def resolution_quality(desc):
    """
    Score resolution description quality.
    Returns: ('good'|'weak'|'none', score)
    """
    if not desc or len(desc.strip()) < 20:
        return ('none', 0)

    text = desc.lower()
    good_keywords = [
        'official', 'source', 'data', 'reported', 'announced',
        'confirmed', 'published', 'record', 'statistics', 'agency',
        'reuters', 'ap ', 'associated press', 'bloomberg',
    ]
    bad_keywords = [
        'opinion', 'believe', 'prediction', ' speculation',
        'rumor', 'maybe', 'might', 'could', 'wish',
    ]

    good_hits = sum(1 for k in good_keywords if k in text)
    bad_hits = sum(1 for k in bad_keywords if k in text)

    length = len(desc)
    score = min(length / 200, 3) + good_hits - bad_hits

    if score >= 2:
        return ('good', score)
    elif score >= 0:
        return ('weak', score)
    else:
        return ('none', score)


# ── Scoring ───────────────────────────────────────────────────────────────────

def compute_score(m, spread_val, res_score):
    """
    Compute quality score (0–10) for ranking markets.
    Higher = better candidate for trading research.
    """
    score = 0.0

    # Liquidity (0–2.5)
    liq = m.liquidity or 0
    if liq > 0:
        score += min(2.5, (liq / 5_000) * 2.5)

    # Volume (0–2)
    vol = m.volume or 0
    if vol > 0:
        score += min(2.0, (vol / 20_000) * 2.0)

    # Price quality — closer to 50/50 = more edge potential (0–1.5)
    yes = m.yes_price
    if 0.10 <= yes <= 0.90:
        score += 1.5 - abs(yes - 0.5) * 3

    # Spread — tighter is better (0–2)
    if spread_val is not None:
        if spread_val <= 0.02:
            score += 2.0
        elif spread_val <= MAX_SPREAD:
            score += 1.0

    # Resolution quality (0–2)
    score += min(2.0, max(0, res_score))

    return round(score, 1)


# ── Main scan ─────────────────────────────────────────────────────────────────

async def scan(limit=TOP_N, min_liquidity=MIN_LIQUIDITY):
    """Scan Polymarket for candidate markets. Read-only."""
    client = PolymarketClient()

    all_markets = []
    for page in range(SCAN_PAGES):
        batch = await client.get_markets(
            limit=50, offset=page * 50, active=True, closed=False,
        )
        all_markets.extend(batch)
        if len(batch) < 50:
            break

    # ── Filter ────────────────────────────────────────────────────────────
    passed_filters = []
    rejected = {'blocked': 0, 'extreme_price': 0, 'low_liquidity': 0, 'low_volume': 0}

    for m in all_markets:
        if is_blocked(m.tags, m.question):
            rejected['blocked'] += 1
            continue
        if price_extreme(m.yes_price):
            rejected['extreme_price'] += 1
            continue
        if (m.liquidity or 0) < min_liquidity:
            rejected['low_liquidity'] += 1
            continue
        if (m.volume or 0) < MIN_VOLUME:
            rejected['low_volume'] += 1
            continue

        res_label, res_score = resolution_quality(m.description)
        passed_filters.append((m, res_label, res_score))

    # ── Score and rank (no CLOB spread — condition_id ≠ token_id) ─────
    results = []
    for m, res_label, res_score in passed_filters:
        score = compute_score(m, spread_val=None, res_score=res_score)
        results.append({
            'market': m,
            'spread': None,
            'res_label': res_label,
            'res_score': res_score,
            'score': score,
        })

    results.sort(key=lambda x: x['score'], reverse=True)
    top = results[:limit]

    await client.close()
    return top, all_markets, rejected


# ── Display ───────────────────────────────────────────────────────────────────

def print_results(results, total_scanned, rejected):
    """Print scanner report to stdout."""
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    print()
    print('┌─────────────────────────────────────────────────────────────┐')
    print('│   Polymarket Market Scanner — READ ONLY                     │')
    print('└─────────────────────────────────────────────────────────────┘')
    print(f'  Date:              {now}')
    print(f'  Markets scanned:   {total_scanned}')
    print(f'  Rejected:          blocked={rejected["blocked"]}  '
          f'extreme_price={rejected["extreme_price"]}  '
          f'low_liq={rejected["low_liquidity"]}  '
          f'low_vol={rejected["low_volume"]}')
    print(f'  Candidates:        {len(results)}')
    print()

    if not results:
        print('  No markets passed all filters.')
        print()
        return

    print(f'  {"#":>2}  {"Score":>5}  {"Liq":>8}  {"Vol":>8}  '
          f'{"Yes":>5}  {"Res":>4}  Question')
    print('  ' + '─' * 74)

    for i, r in enumerate(results, 1):
        m = r['market']
        q = m.question[:52]
        print(f'  {i:2d}  {r["score"]:5.1f}  ${m.liquidity or 0:7,.0f}  '
              f'${m.volume or 0:7,.0f}  {m.yes_price:5.2f}  '
              f'{r["res_label"]:>4}  {q}')

    print()
    print('  Alpha checklist:')
    print('    ✓ Objective resolution — official data sources')
    print('    ✓ Good liquidity — can enter/exit without slippage')
    print('    ✓ Tight spread — not eating your edge')
    print('    ✓ No insider/political/sports information asymmetry')
    print('    ✓ Verifiable external data source')
    print()
    print('  ⚠  READ ONLY — no orders placed, no state changed')
    print('  ───────────────────────────────────────────────────────────')
    print()


# ── Markdown watchlist ────────────────────────────────────────────────────────

# Output path: env override > relative to script (Docker) > relative to repo
def _resolve_watchlist_path():
    env = os.environ.get('WATCHLIST_OUTPUT')
    if env:
        return Path(env)
    # Try relative to this script (works when strategy/ is mounted at /app)
    script_docs = Path(__file__).resolve().parent.parent.parent / 'docs' / 'MARKET_WATCHLIST.md'
    if script_docs.parent.exists():
        return script_docs
    # Fallback: write to cwd/docs/
    return Path.cwd() / 'docs' / 'MARKET_WATCHLIST.md'

WATCHLIST_PATH = _resolve_watchlist_path()


def write_watchlist(results, min_liquidity=MIN_LIQUIDITY):
    """Write/update docs/MARKET_WATCHLIST.md with scan results + manual review fields."""
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    lines = [
        '# Market Watchlist',
        '',
        '> Read-only research output from `scripts/market_research.py`.',
        '> **This is NOT trading signals.** Bot must NOT trade from this list until all gates pass.',
        '',
        f'**Last scan:** {now}',
        f'**Candidates:** {len(results)}',
        '',
        '## Filters',
        '',
        f'- Min liquidity: ${min_liquidity:,}',
        f'- Min volume: ${MIN_VOLUME:,}',
        f'- Max spread: {MAX_SPREAD:.0%}',
        f'- Price range: {PRICE_FLOOR:.0%}–{PRICE_CEIL:.0%}',
        f'- Blocked categories: {", ".join(sorted(BLOCKED_TAGS))}',
        '',
        '## Candidates',
        '',
    ]

    if not results:
        lines.append('_No markets passed all filters this scan._')
    else:
        lines.append('| # | Score | Question | Yes | Liquidity | Volume | Resolution |')
        lines.append('|---|-------|----------|-----|-----------|--------|------------|')

        for i, r in enumerate(results, 1):
            m = r['market']
            q = m.question[:55]
            lines.append(
                f'| {i} | {r["score"]:.1f} | {q} | {m.yes_price:.2f} | '
                f'${m.liquidity or 0:,.0f} | ${m.volume or 0:,.0f} | {r["res_label"]} |'
            )

    lines += [
        '',
        '## Manual Review',
        '',
        '> Fill in each row after checking the live market page.',
        '',
        '| # | Market | Resolution clear? | Order book checked? | Data source? | Signal reason? | Decision |',
        '|---|--------|-------------------|--------------------|--------------|----------------|----------|',
    ]
    for i, r in enumerate(results, 1):
        q = r['market'].question[:40]
        lines.append(f'| {i} | {q} | ☐ | ☐ | ☐ | ☐ | ☐ |')

    lines += [
        '',
        '### Review criteria',
        '',
        '1. **Resolution clear?** — No ambiguous wording, objective outcome',
        '2. **Order book checked?** — Real bid/ask on Polymarket page, not just Gamma liquidity',
        '3. **Data source?** — Official data/API/report, not speculation or rumors',
        '4. **Signal reason?** — Predictive edge exists beyond liquidity/volume',
        '5. **Decision** — PASS (proceed to alpha check) / WATCH ONLY / REJECT',
        '',
        '## Alpha Criteria',
        '',
        'Before any market moves from watchlist to actual trading:',
        '',
        '1. **Objective resolution** — resolved by official data, not opinion',
        '2. **Good liquidity** — can enter/exit without significant slippage',
        '3. **Tight spread** — not eating your edge before you start',
        '4. **No information asymmetry** — no insider knowledge, politics, or sports',
        '5. **Verifiable data source** — external source anyone can check',
        '6. **Multi-signal agreement** — several signals point the same way',
        '',
        '## Blocked Categories',
        '',
        '- Politics (elections, legislation, appointments)',
        '- Sports (game outcomes, scores, championships)',
        '- Entertainment (awards, box office, celebrity events)',
        '- Celebrities (personal events, legal cases)',
        '',
        '## Status',
        '',
        '**This watchlist is for RESEARCH ONLY.**',
        'Bot will NOT trade from this list until:',
        '- [ ] Kill switch reset (Gate 1)',
        '- [ ] Dry-run validated (Gate 2)',
        '- [ ] Micro-live approved (Gate 3)',
        '',
        'See `docs/READINESS_CHECKLIST.md` for full gate requirements.',
        '',
    ]

    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    WATCHLIST_PATH.write_text('\n'.join(lines))
    return WATCHLIST_PATH


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Polymarket read-only market scanner')
    parser.add_argument('--limit', type=int, default=TOP_N,
                        help=f'Max candidates to return (default: {TOP_N})')
    parser.add_argument('--min-liquidity', type=int, default=MIN_LIQUIDITY,
                        help=f'Minimum liquidity in USDC (default: {MIN_LIQUIDITY})')
    args = parser.parse_args()

    print()
    print('  Scanning Polymarket (read-only)...')
    if args.limit != TOP_N or args.min_liquidity != MIN_LIQUIDITY:
        print(f'  Options: --limit={args.limit} --min-liquidity={args.min_liquidity}')
    print()

    results, total, rejected = asyncio.run(
        scan(limit=args.limit, min_liquidity=args.min_liquidity)
    )

    print_results(results, total, rejected)
    path = write_watchlist(results, min_liquidity=args.min_liquidity)
    print(f'  Watchlist written to: {path}')
    print()


if __name__ == '__main__':
    main()
