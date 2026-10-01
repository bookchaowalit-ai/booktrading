#!/usr/bin/env python3
"""Load closed OHLCV bars and funding rates from the Data Lakehouse Silver layer.

This is the lake-first replacement for ``data.py --fetch``: the trading tools
read the Silver ``crypto_ohlcv`` / ``crypto_funding`` datasets produced by
``book-crypto-data`` (Binance public market data -> Bronze -> Silver) instead
of calling an exchange directly. Reading is local-only; no network, no
credentials.

Requires the Solo Empire ``infra/scripts/data_lake`` runtime (DuckDB + PyArrow).
Set ``SOLO_EMPIRE_ROOT`` when this checkout is not nested inside Solo Empire.
The rest of ``trading/`` stays stdlib-only; import this module lazily.

Research tooling only — not investment advice.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from futures_backtest import Bar


def solo_empire_root() -> Path:
    """Locate the Solo Empire checkout that owns the shared lake runtime and outputs.

    ``SOLO_EMPIRE_ROOT`` wins. Otherwise walk up from this file, because the
    booktrading checkout normally lives inside the Solo Empire tree. Without
    either, fall back to this folder so the stdlib-only tools still run.
    """
    configured = os.environ.get("SOLO_EMPIRE_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "infra" / "scripts" / "data_lake" / "silver.py").is_file():
            return parent
    return here.parent


ROOT = solo_empire_root()
DEFAULT_LAKE_URI = str(ROOT / "data" / "lake-local" / "scraping-captures-v2")
DEFAULT_VENUE = "binance_futures"
INTERVAL_MS = {"15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}


class LakeDataError(RuntimeError):
    """Raised when the lake cannot supply a usable series."""


@dataclass
class SeriesQuality:
    symbol: str
    interval: str
    bars: int = 0
    first_open_ms: int | None = None
    last_open_ms: int | None = None
    gaps: list[tuple[int, int]] = field(default_factory=list)  # (after_open_ms, missing_bars)

    @property
    def missing_bars(self) -> int:
        return sum(n for _, n in self.gaps)

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "interval": self.interval,
            "bars": self.bars,
            "first_open_ms": self.first_open_ms,
            "last_open_ms": self.last_open_ms,
            "gap_count": len(self.gaps),
            "missing_bars": self.missing_bars,
        }


def _read_silver(dataset: str, sql: str, data_lake_uri: str) -> list[dict[str, Any]]:
    scripts = ROOT / "infra" / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    try:
        from data_lake.silver import read_silver_rows  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on local runtime
        raise LakeDataError(f"data_lake runtime unavailable: {exc}") from exc
    return read_silver_rows(
        data_lake_uri=data_lake_uri, domain="market", dataset=dataset, sql=sql
    )


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def bars_from_rows(rows: Sequence[dict[str, Any]]) -> list[Bar]:
    """Deduplicate Silver rows by record_id (parts may overlap) and sort."""
    by_open: dict[int, Bar] = {}
    for row in rows:
        if row.get("quality_status") not in (None, "valid"):
            continue
        open_ms = int(row["open_time_ms"])
        by_open[open_ms] = Bar(
            open_ms,
            float(row["open"]),
            float(row["high"]),
            float(row["low"]),
            float(row["close"]),
            float(row["volume"]),
        )
    return [by_open[k] for k in sorted(by_open)]


def assess(bars: Sequence[Bar], symbol: str, interval: str) -> SeriesQuality:
    step = INTERVAL_MS[interval]
    quality = SeriesQuality(symbol=symbol, interval=interval, bars=len(bars))
    if bars:
        quality.first_open_ms = bars[0].open_time_ms
        quality.last_open_ms = bars[-1].open_time_ms
    for prev, cur in zip(bars, bars[1:]):
        delta = cur.open_time_ms - prev.open_time_ms
        if delta != step:
            quality.gaps.append((prev.open_time_ms, max(delta // step - 1, 0)))
    return quality


def load_bars(
    symbol: str,
    *,
    interval: str = "1h",
    venue: str = DEFAULT_VENUE,
    data_lake_uri: str = DEFAULT_LAKE_URI,
) -> tuple[list[Bar], SeriesQuality]:
    if interval not in INTERVAL_MS:
        raise LakeDataError(f"unsupported interval {interval!r}")
    sql = (
        "SELECT open_time_ms, open, high, low, close, volume, quality_status "
        "FROM lake_table "
        f"WHERE symbol = {_quote(symbol.upper())} AND interval = {_quote(interval)} "
        f"AND venue = {_quote(venue)}"
    )
    rows = _read_silver("crypto_ohlcv", sql, data_lake_uri)
    bars = bars_from_rows(rows)
    if not bars:
        raise LakeDataError(
            f"no Silver crypto_ohlcv bars for {venue}:{symbol}:{interval}; "
            "run `task trading:lake:capture` then `task trading:lake:silver`"
        )
    return bars, assess(bars, symbol.upper(), interval)


def load_funding(
    symbol: str,
    *,
    venue: str = DEFAULT_VENUE,
    data_lake_uri: str = DEFAULT_LAKE_URI,
) -> list[tuple[int, float]]:
    sql = (
        "SELECT funding_time_ms, funding_rate, quality_status FROM lake_table "
        f"WHERE symbol = {_quote(symbol.upper())} AND venue = {_quote(venue)}"
    )
    try:
        rows = _read_silver("crypto_funding", sql, data_lake_uri)
    except LakeDataError:
        raise
    except Exception:  # noqa: BLE001 - funding is optional; fall back to constant
        return []
    series = {
        int(r["funding_time_ms"]): float(r["funding_rate"])
        for r in rows
        if r.get("quality_status") in (None, "valid")
    }
    return sorted(series.items())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Inspect lake OHLCV coverage. " + __doc__.splitlines()[0])
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT")
    ap.add_argument("--interval", default="1h", choices=sorted(INTERVAL_MS))
    ap.add_argument("--venue", default=DEFAULT_VENUE)
    ap.add_argument("--data-lake-uri", default=DEFAULT_LAKE_URI)
    ap.add_argument("--export-csv-dir", help="optionally write data.py-compatible CSV caches")
    args = ap.parse_args(argv)
    out = []
    for symbol in [s.strip() for s in args.symbols.split(",") if s.strip()]:
        try:
            bars, quality = load_bars(
                symbol, interval=args.interval, venue=args.venue, data_lake_uri=args.data_lake_uri
            )
        except LakeDataError as exc:
            out.append({"symbol": symbol, "status": "missing", "error": str(exc)})
            continue
        funding = load_funding(symbol, venue=args.venue, data_lake_uri=args.data_lake_uri)
        item = {"status": "ok", **quality.as_dict(), "funding_points": len(funding)}
        if args.export_csv_dir:
            from data import save_csv, save_funding_csv

            base = Path(args.export_csv_dir)
            save_csv(base / f"{symbol}_{args.interval}.csv", bars)
            if funding:
                save_funding_csv(base / f"{symbol}_funding.csv", funding)
            item["exported_to"] = str(base)
        out.append(item)
    print(json.dumps(out, indent=2))
    return 0 if all(item["status"] == "ok" for item in out) else 1


if __name__ == "__main__":
    raise SystemExit(main())
