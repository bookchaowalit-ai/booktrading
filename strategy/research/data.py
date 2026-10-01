#!/usr/bin/env python3
"""Market-data loading for the Phase 4 walk-forward validator.

This is the ONLY module in ``trading/`` that can touch the network, and it
does so exclusively via the public, unauthenticated Binance market-data
endpoints (klines and funding rates). There are NO credentials, NO auth
headers, NO env vars and NO private/trading endpoints anywhere in this file.
Nothing else in the package imports the network path implicitly — library
code consumes CSV caches or in-memory bars.

CSV cache format (deterministic, one bar per line)::

    open_time_ms,open,high,low,close,volume
    1704067200000,30000.0,30012.5,29990.1,30001.25,123.45

Floats are written with ``repr`` so a load/save round-trip is exact.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from futures_backtest import Bar

SPOT_KLINES_URL = "https://api.binance.com/api/v3/klines"
FUTURES_KLINES_URL = "https://fapi.binance.com/fapi/v1/klines"
FUTURES_FUNDING_URL = "https://fapi.binance.com/fapi/v1/fundingRate"

_BAR_HEADER = ["open_time_ms", "open", "high", "low", "close", "volume"]
_FUNDING_HEADER = ["time_ms", "rate"]


# ---------------------------------------------------------------------------
# CSV cache
# ---------------------------------------------------------------------------


def save_csv(path, bars: Sequence[Bar]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(_BAR_HEADER)
        for b in bars:
            writer.writerow(
                [
                    b.open_time_ms,
                    repr(b.open),
                    repr(b.high),
                    repr(b.low),
                    repr(b.close),
                    repr(b.volume),
                ]
            )


def load_csv(path) -> list[Bar]:
    bars: list[Bar] = []
    with Path(path).open(newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if header != _BAR_HEADER:
            raise ValueError(f"{path}: unexpected header {header!r}")
        for row in reader:
            if not row:
                continue
            bars.append(
                Bar(
                    int(row[0]),
                    float(row[1]),
                    float(row[2]),
                    float(row[3]),
                    float(row[4]),
                    float(row[5]),
                )
            )
    return bars


def save_funding_csv(path, funding: Sequence[tuple[int, float]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(_FUNDING_HEADER)
        for t, r in funding:
            writer.writerow([t, repr(r)])


def load_funding_csv(path) -> list[tuple[int, float]]:
    out: list[tuple[int, float]] = []
    with Path(path).open(newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if header != _FUNDING_HEADER:
            raise ValueError(f"{path}: unexpected header {header!r}")
        for row in reader:
            if not row:
                continue
            out.append((int(row[0]), float(row[1])))
    return out


# ---------------------------------------------------------------------------
# Public Binance API parsing (pure functions, unit-tested without HTTP)
# ---------------------------------------------------------------------------


def parse_klines(payload) -> list[Bar]:
    """Parse a Binance klines JSON payload into Bars (ascending time)."""
    bars = []
    for row in payload:
        bars.append(
            Bar(
                int(row[0]),
                float(row[1]),
                float(row[2]),
                float(row[3]),
                float(row[4]),
                float(row[5]),
            )
        )
    bars.sort(key=lambda b: b.open_time_ms)
    return bars


def parse_funding_rates(payload) -> list[tuple[int, float]]:
    """Parse a Binance futures fundingRate JSON payload."""
    out = [(int(row["fundingTime"]), float(row["fundingRate"])) for row in payload]
    out.sort()
    return out


# ---------------------------------------------------------------------------
# Network fetch (public endpoints only, no auth)
# ---------------------------------------------------------------------------


def _get_json(url: str, params: dict, timeout: float = 15.0):
    full = f"{url}?{urlencode(params)}"
    req = Request(full, headers={"User-Agent": "book-finance-research/1.0"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"network fetch failed for {url}: {exc}") from exc


def fetch_binance_klines(
    symbol: str, interval: str, start_ms: int, end_ms: int, market: str = "spot"
) -> list[Bar]:
    """Fetch public klines from Binance with limit=1000 pagination.

    ``market`` is "spot" or "futures". No authentication is used or needed.
    """
    if market not in ("spot", "futures"):
        raise ValueError(f"bad market: {market}")
    url = SPOT_KLINES_URL if market == "spot" else FUTURES_KLINES_URL
    bars: list[Bar] = []
    cursor = start_ms
    while cursor < end_ms:
        payload = _get_json(
            url,
            {
                "symbol": symbol,
                "interval": interval,
                "startTime": cursor,
                "endTime": end_ms - 1,
                "limit": 1000,
            },
        )
        if not payload:
            break
        batch = parse_klines(payload)
        if not batch:
            break
        bars.extend(b for b in batch if start_ms <= b.open_time_ms < end_ms)
        last = batch[-1].open_time_ms
        if last <= cursor or len(batch) < 1000:
            break
        cursor = last + 1
    # de-duplicate while preserving ascending order
    seen = {}
    for b in bars:
        seen[b.open_time_ms] = b
    return [seen[t] for t in sorted(seen)]


def fetch_binance_funding_rates(
    symbol: str, start_ms: int, end_ms: int
) -> list[tuple[int, float]]:
    """Fetch public futures funding-rate history (no auth)."""
    out: list[tuple[int, float]] = []
    cursor = start_ms
    while cursor < end_ms:
        payload = _get_json(
            FUTURES_FUNDING_URL,
            {
                "symbol": symbol,
                "startTime": cursor,
                "endTime": end_ms - 1,
                "limit": 1000,
            },
        )
        if not payload:
            break
        batch = parse_funding_rates(payload)
        if not batch:
            break
        out.extend(t for t in batch if start_ms <= t[0] < end_ms)
        last = batch[-1][0]
        if last <= cursor or len(batch) < 1000:
            break
        cursor = last + 1
    seen = {}
    for t, r in out:
        seen[t] = r
    return [(t, seen[t]) for t in sorted(seen)]


# ---------------------------------------------------------------------------
# CLI (--fetch is the only entry point that uses the network)
# ---------------------------------------------------------------------------


def _parse_date_ms(text: str) -> int:
    from datetime import datetime, timezone

    dt = datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Data loader. --fetch downloads PUBLIC Binance market "
        "data (no credentials) into a local CSV cache."
    )
    ap.add_argument(
        "--fetch", action="store_true", help="download public klines into a cache CSV"
    )
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--interval", default="1h")
    ap.add_argument("--market", choices=["spot", "futures"], default="futures")
    ap.add_argument("--start", help="YYYY-MM-DD (UTC, inclusive)")
    ap.add_argument("--end", help="YYYY-MM-DD (UTC, exclusive)")
    ap.add_argument("--out", help="output CSV path for bars")
    ap.add_argument(
        "--funding-out",
        default=None,
        help="optional output CSV path for the funding series",
    )
    args = ap.parse_args(argv)

    if not args.fetch:
        ap.print_help()
        return 0
    if not (args.start and args.end and args.out):
        ap.error("--fetch requires --start, --end and --out")

    start_ms = _parse_date_ms(args.start)
    end_ms = _parse_date_ms(args.end)
    try:
        bars = fetch_binance_klines(
            args.symbol, args.interval, start_ms, end_ms, market=args.market
        )
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    save_csv(args.out, bars)
    print(f"wrote {len(bars)} bars -> {args.out}")
    if args.funding_out:
        try:
            funding = fetch_binance_funding_rates(args.symbol, start_ms, end_ms)
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        save_funding_csv(args.funding_out, funding)
        print(f"wrote {len(funding)} funding events -> {args.funding_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
