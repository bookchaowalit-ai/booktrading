#!/usr/bin/env python3
"""
Crypto Spot Market Scanner — Read-Only
Run: python scripts/crypto_market_research.py
     python scripts/crypto_market_research.py --limit 10 --min-volume 1000000

Scans Binance Global (USDT), Binance TH (THB), and Bitkub (THB) for
crypto spot pair quality. Rankings based on volume, volatility, spread,
and order book depth.

Note: Binance TH uses /api/v1/ endpoints (not v3).
      Bitkub API may be geo-restricted (requires TH IP).

Does NOT place orders, reset kill switch, or modify any state.

Output: Ranked pairs → stdout + docs/CRYPTO_WATCHLIST.md
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# ── Configuration ─────────────────────────────────────────────────────────────

# Binance Global (USDT pairs)
BINANCE_GLOBAL = "https://api.binance.com"
# Binance Thailand (THB pairs)
BINANCE_TH = "https://api.binance.th"
# Bitkub (THB pairs)
BITKUB = "https://api.bitkub.com"

# Pairs to scan
BINANCE_GLOBAL_PAIRS = ["BTCUSDT", "ETHUSDT"]
BINANCE_TH_PAIRS = ["BTCTHB", "ETHTHB", "SOLTHB", "BNBTHB", "XRPTHB"]
BITKUB_PAIRS = ["BTC_THB", "ETH_THB", "SOL_THB", "BNB_THB", "XRP_THB"]

# Mapping between exchanges for cross-exchange comparison
# base asset → {exchange: symbol}
PAIR_MAP = {
    "BTC": {"binance_global": "BTCUSDT", "binance_th": "BTCTHB", "bitkub": "BTC_THB"},
    "ETH": {"binance_global": "ETHUSDT", "binance_th": "ETHTHB", "bitkub": "ETH_THB"},
    "SOL": {"binance_th": "SOLTHB", "bitkub": "SOL_THB"},
    "BNB": {"binance_th": "BNBTHB", "bitkub": "BNB_THB"},
    "XRP": {"binance_th": "XRPTHB", "bitkub": "XRP_THB"},
}

DEFAULT_LIMIT = 10
MIN_VOLUME_THB = 1_000_000  # ~1M THB minimum daily volume (~$28k)
HTTP_TIMEOUT = 15.0
DEPTH_LIMIT = 5  # top 5 bids/asks


# ── Data fetching ─────────────────────────────────────────────────────────────

async def fetch_binance_24hr(client: httpx.AsyncClient, base_url: str, symbol: str) -> Optional[Dict]:
    """Fetch 24hr ticker from Binance-compatible endpoint.
    Binance TH uses /api/v1/, Binance Global uses /api/v3/.
    """
    # Determine API version based on base URL
    api_ver = "v1" if base_url == BINANCE_TH else "v3"
    try:
        resp = await client.get(f"{base_url}/api/{api_ver}/ticker/24hr", params={"symbol": symbol})
        if resp.status_code == 200:
            data = resp.json()
            return {
                "symbol": data.get("symbol", symbol),
                "last": float(data.get("lastPrice", 0)),
                "high": float(data.get("highPrice", 0)),
                "low": float(data.get("lowPrice", 0)),
                "volume": float(data.get("volume", 0)),         # base asset volume
                "quote_volume": float(data.get("quoteVolume", 0)),  # quote asset volume
                "price_change_pct": float(data.get("priceChangePercent", 0)),
                "weighted_avg": float(data.get("weightedAvgPrice", 0)),
            }
    except Exception as e:
        print(f"  ⚠ {base_url} {symbol} 24hr error: {e}")
    return None


async def fetch_binance_depth(client: httpx.AsyncClient, base_url: str, symbol: str) -> Optional[Dict]:
    """Fetch order book depth from Binance-compatible endpoint.
    Binance TH uses /api/v1/, Binance Global uses /api/v3/.
    """
    api_ver = "v1" if base_url == BINANCE_TH else "v3"
    try:
        resp = await client.get(f"{base_url}/api/{api_ver}/depth", params={"symbol": symbol, "limit": DEPTH_LIMIT})
        if resp.status_code == 200:
            data = resp.json()
            bids = [(float(p), float(q)) for p, q in data.get("bids", [])]
            asks = [(float(p), float(q)) for p, q in data.get("asks", [])]
            if bids and asks:
                best_bid = bids[0][0]
                best_ask = asks[0][0]
                spread = best_ask - best_bid
                spread_pct = (spread / best_ask * 100) if best_ask > 0 else 0
                # Depth: total quote value in top N levels
                bid_depth = sum(p * q for p, q in bids)
                ask_depth = sum(p * q for p, q in asks)
                return {
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "spread": spread,
                    "spread_pct": spread_pct,
                    "bid_depth": bid_depth,
                    "ask_depth": ask_depth,
                    "total_depth": bid_depth + ask_depth,
                }
    except Exception as e:
        print(f"  ⚠ {base_url} {symbol} depth error: {e}")
    return None


async def fetch_bitkub_ticker(client: httpx.AsyncClient, symbol: str) -> Optional[Dict]:
    """Fetch ticker from Bitkub public API."""
    try:
        resp = await client.get(f"{BITKUB}/api/v1/ticker", params={"sym": symbol})
        if resp.status_code == 200:
            data = resp.json()
            # Bitkub returns {symbol: {last, high24, low24, vol24, ...}}
            ticker = data.get(symbol)
            if ticker:
                last = float(ticker.get("last", 0))
                high = float(ticker.get("high24", 0))
                low = float(ticker.get("low24", 0))
                vol = float(ticker.get("vol24", 0))
                change_pct = float(ticker.get("changepct24", 0))
                return {
                    "symbol": symbol,
                    "last": last,
                    "high": high,
                    "low": low,
                    "volume": vol,           # base asset volume
                    "quote_volume": vol * last,  # approximate THB volume
                    "price_change_pct": change_pct,
                }
    except Exception as e:
        print(f"  ⚠ Bitkub {symbol} ticker error: {e}")
    return None


async def fetch_bitkub_depth(client: httpx.AsyncClient, symbol: str) -> Optional[Dict]:
    """Fetch order book from Bitkub public API."""
    try:
        resp = await client.get(f"{BITKUB}/api/v1/orderbook", params={"sym": symbol})
        if resp.status_code == 200:
            data = resp.json()
            # Bitkub orderbook: {bids: [[price, qty],...], asks: [[price, qty],...]}
            bids_raw = data.get("bids", [])
            asks_raw = data.get("asks", [])
            bids = [(float(p), float(q)) for p, q in bids_raw[:DEPTH_LIMIT]]
            asks = [(float(p), float(q)) for p, q in asks_raw[:DEPTH_LIMIT]]
            if bids and asks:
                best_bid = bids[0][0]
                best_ask = asks[0][0]
                spread = best_ask - best_bid
                spread_pct = (spread / best_ask * 100) if best_ask > 0 else 0
                bid_depth = sum(p * q for p, q in bids)
                ask_depth = sum(p * q for p, q in asks)
                return {
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "spread": spread,
                    "spread_pct": spread_pct,
                    "bid_depth": bid_depth,
                    "ask_depth": ask_depth,
                    "total_depth": bid_depth + ask_depth,
                }
    except Exception as e:
        print(f"  ⚠ Bitkub {symbol} depth error: {e}")
    return None


# ── Scanning ──────────────────────────────────────────────────────────────────

async def scan_exchange(client: httpx.AsyncClient, exchange: str, pairs: List[str]) -> List[Dict]:
    """Scan all pairs on one exchange. Returns list of pair metrics."""
    results = []

    for symbol in pairs:
        # Fetch ticker + depth in parallel
        if exchange == "bitkub":
            ticker, depth = await asyncio.gather(
                fetch_bitkub_ticker(client, symbol),
                fetch_bitkub_depth(client, symbol),
            )
        else:
            base_url = BINANCE_GLOBAL if exchange == "binance_global" else BINANCE_TH
            ticker, depth = await asyncio.gather(
                fetch_binance_24hr(client, base_url, symbol),
                fetch_binance_depth(client, base_url, symbol),
            )

        if not ticker:
            continue

        # Compute metrics
        high = ticker["high"]
        low = ticker["low"]
        last = ticker["last"]
        quote_vol = ticker.get("quote_volume", 0)

        # Volatility proxy: (high - low) / last * 100
        volatility_pct = ((high - low) / last * 100) if last > 0 else 0

        results.append({
            "exchange": exchange,
            "symbol": symbol,
            "last": last,
            "high": high,
            "low": low,
            "volume_base": ticker["volume"],
            "volume_quote": quote_vol,
            "change_pct": ticker["price_change_pct"],
            "volatility_pct": volatility_pct,
            "best_bid": depth["best_bid"] if depth else None,
            "best_ask": depth["best_ask"] if depth else None,
            "spread": depth["spread"] if depth else None,
            "spread_pct": depth["spread_pct"] if depth else None,
            "total_depth": depth["total_depth"] if depth else None,
        })

    return results


async def scan_all() -> List[Dict]:
    """Scan all exchanges and return combined results."""
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        tasks = [
            scan_exchange(client, "binance_global", BINANCE_GLOBAL_PAIRS),
            scan_exchange(client, "binance_th", BINANCE_TH_PAIRS),
            scan_exchange(client, "bitkub", BITKUB_PAIRS),
        ]
        results = await asyncio.gather(*tasks)

    combined = []
    for r in results:
        combined.extend(r)
    return combined


# ── Scoring ───────────────────────────────────────────────────────────────────

def score_pair(p: Dict) -> float:
    """
    Score a pair (0–10) for trading research quality.
    Higher = better candidate for paper/pilot trading.

    Components:
    - Volume (0–3): higher quote volume = more tradeable
    - Volatility (0–2.5): moderate vol = grid bot opportunity
    - Spread (0–2.5): tighter spread = less cost
    - Depth (0–2): deeper book = less slippage
    """
    score = 0.0

    # Volume score (0–3) — log scale, 1M THB = 1.0, 100M THB = 3.0
    vol = p.get("volume_quote", 0)
    if vol > 0:
        import math
        vol_m = vol / 1_000_000  # in millions THB
        score += min(3.0, 1.0 + math.log10(max(1, vol_m)) * 0.8)

    # Volatility score (0–2.5) — sweet spot 1–5% daily range
    vol_pct = p.get("volatility_pct", 0)
    if 1.0 <= vol_pct <= 5.0:
        score += 2.5
    elif 0.5 <= vol_pct < 1.0 or 5.0 < vol_pct <= 8.0:
        score += 1.5
    elif vol_pct > 0:
        score += 0.5

    # Spread score (0–2.5) — tighter is better
    spread = p.get("spread_pct")
    if spread is not None:
        if spread <= 0.05:
            score += 2.5
        elif spread <= 0.10:
            score += 2.0
        elif spread <= 0.30:
            score += 1.0
        elif spread <= 0.50:
            score += 0.5

    # Depth score (0–2) — deeper book
    depth = p.get("total_depth", 0)
    if depth:
        import math
        depth_m = depth / 1_000_000  # millions THB
        score += min(2.0, 0.5 + math.log10(max(1, depth_m)) * 0.6)

    return round(score, 1)


# ── Cross-exchange comparison ────────────────────────────────────────────────

def cross_exchange_analysis(all_pairs: List[Dict]) -> List[Dict]:
    """Compare same asset across exchanges for price discrepancy."""
    analyses = []
    for asset, exchanges in PAIR_MAP.items():
        prices = {}
        for exch, sym in exchanges.items():
            match = next((p for p in all_pairs if p["symbol"] == sym), None)
            if match and match["last"] > 0:
                prices[exch] = match

        if len(prices) < 2:
            continue

        # Find max spread between exchanges
        exch_list = list(prices.items())
        max_diff = 0
        max_pair = None
        for i in range(len(exch_list)):
            for j in range(i + 1, len(exch_list)):
                e1, p1 = exch_list[i]
                e2, p2 = exch_list[j]
                # Normalize: THB prices are comparable, USDT needs FX adjustment
                # For simplicity, just compare THB pairs directly
                if "th" in e1 and "th" in e2:
                    diff = abs(p1["last"] - p2["last"])
                    diff_pct = diff / max(p1["last"], p2["last"]) * 100
                    if diff_pct > max_diff:
                        max_diff = diff_pct
                        max_pair = (e1, p1["last"], e2, p2["last"])

        if max_pair:
            analyses.append({
                "asset": asset,
                "max_spread_pct": round(max_diff, 3),
                "from_exchange": max_pair[0],
                "from_price": max_pair[1],
                "to_exchange": max_pair[2],
                "to_price": max_pair[3],
            })

    return analyses


# ── Display ───────────────────────────────────────────────────────────────────

def print_results(all_pairs: List[Dict], cross: List[Dict]):
    """Print scanner report to stdout."""
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    # Score all pairs
    for p in all_pairs:
        p["score"] = score_pair(p)

    # Sort by score descending
    ranked = sorted(all_pairs, key=lambda x: x["score"], reverse=True)

    print()
    print('┌─────────────────────────────────────────────────────────────────┐')
    print('│   Crypto Spot Market Scanner — READ ONLY                        │')
    print('└─────────────────────────────────────────────────────────────────┘')
    print(f'  Date:           {now}')
    print(f'  Exchanges:      Binance Global, Binance TH, Bitkub')
    print(f'  Pairs scanned:  {len(all_pairs)}')
    print()

    # Summary table
    print(f'  {"#":>2}  {"Score":>5}  {"Exchange":>14}  {"Symbol":>10}  '
          f'{"Price":>12}  {"Vol(M)":>8}  {"Vol%":>6}  {"Spread":>7}  {"Depth(M)":>8}')
    print('  ' + '─' * 90)

    for i, p in enumerate(ranked, 1):
        exch = p["exchange"].replace("_", " ").title()
        vol_m = p["volume_quote"] / 1_000_000
        spread_str = f'{p["spread_pct"]:.3f}%' if p["spread_pct"] is not None else "N/A"
        depth_m = (p["total_depth"] or 0) / 1_000_000
        price_str = f'{p["last"]:,.2f}'
        print(f'  {i:2d}  {p["score"]:5.1f}  {exch:>14}  {p["symbol"]:>10}  '
              f'{price_str:>12}  {vol_m:7.1f}M  {p["volatility_pct"]:5.1f}%  '
              f'{spread_str:>7}  {depth_m:7.2f}M')

    # Cross-exchange analysis
    if cross:
        print()
        print('  Cross-Exchange Spread (THB pairs only):')
        print('  ' + '─' * 60)
        for c in sorted(cross, key=lambda x: x["max_spread_pct"], reverse=True):
            print(f'    {c["asset"]:>4}: {c["max_spread_pct"]:.3f}% spread')
            print(f'          {c["from_exchange"]} {c["from_price"]:,.2f} ↔ '
                  f'{c["to_exchange"]} {c["to_price"]:,.2f}')

    print()
    print('  Quality checklist:')
    print('    ✓ High volume — can enter/exit without moving the market')
    print('    ✓ Moderate volatility — grid bot sweet spot 1–5% daily range')
    print('    ✓ Tight spread — not eating grid profits')
    print('    ✓ Deep order book — less slippage on fills')
    print()
    print('  ⚠  READ ONLY — no orders placed, no state changed')
    print('  ───────────────────────────────────────────────────────────────')
    print()

    return ranked


# ── Markdown watchlist ────────────────────────────────────────────────────────

def _resolve_watchlist_path():
    env = os.environ.get('CRYPTO_WATCHLIST_OUTPUT')
    if env:
        return Path(env)
    script_docs = Path(__file__).resolve().parent.parent.parent / 'docs' / 'CRYPTO_WATCHLIST.md'
    if script_docs.parent.exists() and os.access(script_docs.parent, os.W_OK):
        return script_docs
    # Fall back to writable data dir (e.g. inside read-only container)
    data_dir = Path(__file__).resolve().parent.parent.parent / 'data'
    if data_dir.exists() and os.access(data_dir, os.W_OK):
        return data_dir / 'CRYPTO_WATCHLIST.md'
    return Path.cwd() / 'CRYPTO_WATCHLIST.md'


WATCHLIST_PATH = _resolve_watchlist_path()


def write_watchlist(ranked: List[Dict], cross: List[Dict], min_volume: float):
    """Write docs/CRYPTO_WATCHLIST.md with scan results."""
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    lines = [
        '# Crypto Watchlist',
        '',
        '> Read-only research output from `scripts/crypto_market_research.py`.',
        '> **This is NOT trading signals.** Bot must NOT trade from this list until all gates pass.',
        '',
        f'**Last scan:** {now}',
        f'**Pairs scanned:** {len(ranked)}',
        f'**Min volume filter:** ฿{min_volume:,.0f}',
        '',
        '## Exchanges',
        '',
        '| Exchange | API | Pairs | Auth |',
        '|----------|-----|-------|------|',
        '| Binance Global | api.binance.com | BTCUSDT, ETHUSDT | Public |',
        '| Binance TH | api.binance.th | BTCTHB, ETHTHB, SOLTHB, BNBTHB, XRPTHB | Public (market data) |',
        '| Bitkub | api.bitkub.com | BTC_THB, ETH_THB, SOL_THB, BNB_THB, XRP_THB | Public (market data) |',
        '',
        '## Ranked Pairs',
        '',
        '| # | Score | Exchange | Symbol | Price | Vol (M ฿) | Vol% | Spread% | Depth (M ฿) |',
        '|---|-------|----------|--------|-------|-----------|------|---------|-------------|',
    ]

    for i, p in enumerate(ranked, 1):
        exch = p["exchange"].replace("_", " ").title()
        vol_m = p["volume_quote"] / 1_000_000
        spread_str = f'{p["spread_pct"]:.3f}' if p["spread_pct"] is not None else "N/A"
        depth_m = (p["total_depth"] or 0) / 1_000_000
        lines.append(
            f'| {i} | {p["score"]:.1f} | {exch} | {p["symbol"]} | '
            f'{p["last"]:,.2f} | {vol_m:.1f}M | {p["volatility_pct"]:.1f}% | '
            f'{spread_str} | {depth_m:.2f}M |'
        )

    # Cross-exchange section
    lines += [
        '',
        '## Cross-Exchange Spread (THB)',
        '',
    ]

    if cross:
        lines.append('| Asset | Spread% | From | Price | To | Price |')
        lines.append('|-------|---------|------|-------|----|-------|')
        for c in sorted(cross, key=lambda x: x["max_spread_pct"], reverse=True):
            lines.append(
                f'| {c["asset"]} | {c["max_spread_pct"]:.3f}% | '
                f'{c["from_exchange"]} | {c["from_price"]:,.2f} | '
                f'{c["to_exchange"]} | {c["to_price"]:,.2f} |'
            )
    else:
        lines.append('_Insufficient data for cross-exchange comparison._')

    # Scoring methodology
    lines += [
        '',
        '## Scoring Methodology',
        '',
        'Score 0–10 based on:',
        '',
        '| Component | Weight | Notes |',
        '|-----------|--------|-------|',
        '| Volume | 0–3 | Log scale, higher quote volume = more tradeable |',
        '| Volatility | 0–2.5 | Sweet spot: 1–5% daily range (grid bot friendly) |',
        '| Spread | 0–2.5 | Tighter = less cost per fill |',
        '| Depth | 0–2 | Deeper book = less slippage |',
        '',
        '## Manual Review',
        '',
        '> Fill in each row after checking live order books.',
        '',
        '| # | Pair | Exchange | Order book verified? | Fee structure? | Grid params fit? | Decision |',
        '|---|------|----------|---------------------|----------------|-----------------|----------|',
    ]
    for i, p in enumerate(ranked, 1):
        lines.append(f'| {i} | {p["symbol"]} | {p["exchange"]} | ☐ | ☐ | ☐ | ☐ |')

    lines += [
        '',
        '### Review criteria',
        '',
        '1. **Order book verified?** — Live bids/asks on exchange, not just API data',
        '2. **Fee structure?** — Maker/taker fees don\'t eat grid profits',
        '3. **Grid params fit?** — Volatility matches grid spacing, depth supports order sizes',
        '4. **Decision** — PAPER (proceed to paper trading) / WATCH ONLY / REJECT',
        '',
        '## Recommended Next Steps',
        '',
        '1. **Paper trade top pairs** — Use existing grid_bot.py with Binance TH testnet',
        '2. **Validate spread stability** — Check if spread holds over 24h, not just snapshot',
        '3. **Compare THB vs USDT** — FX risk assessment for THB-denominated pairs',
        '4. **Fee impact analysis** — Grid profit must exceed maker+taker fees',
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
    parser = argparse.ArgumentParser(description='Crypto spot market read-only scanner')
    parser.add_argument('--limit', type=int, default=DEFAULT_LIMIT,
                        help=f'Max pairs to show (default: {DEFAULT_LIMIT})')
    parser.add_argument('--min-volume', type=int, default=MIN_VOLUME_THB,
                        help=f'Min quote volume in THB (default: {MIN_VOLUME_THB})')
    args = parser.parse_args()

    print()
    print('  Scanning crypto spot markets (read-only)...')
    if args.limit != DEFAULT_LIMIT or args.min_volume != MIN_VOLUME_THB:
        print(f'  Options: --limit={args.limit} --min-volume={args.min_volume}')
    print()

    all_pairs = asyncio.run(scan_all())

    # Filter by minimum volume
    filtered = [p for p in all_pairs if p.get("volume_quote", 0) >= args.min_volume]
    low_vol = len(all_pairs) - len(filtered)

    if low_vol > 0:
        print(f'  Filtered out {low_vol} pairs below ฿{args.min_volume:,} volume')
        print()

    # Cross-exchange analysis (on filtered)
    cross = cross_exchange_analysis(filtered)

    # Score and display
    ranked = print_results(filtered, cross)

    # Write watchlist
    path = write_watchlist(ranked, cross, args.min_volume)
    print(f'  Watchlist written to: {path}')
    print()


if __name__ == '__main__':
    main()
