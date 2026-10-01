#!/usr/bin/env python3
"""Daily PAPER signal report built on Data Lakehouse bars.

For each symbol this tool:

1. loads closed bars + funding from the lake Silver layer (``lake_source``);
2. blocks the decision when data is stale or has gaps;
3. re-runs the walk-forward validator in ``select`` mode (train-only
   selection) and applies the risk gate;
4. selects the current variant on the most recent train window only and reads
   its signal at the last CLOSED bar;
5. writes a Markdown + JSON report and appends one idempotent entry per
   (symbol, bar) to a local paper journal, then scores the journal as a paper
   track record.

Decisions are PAPER_LONG / PAPER_SHORT / PAPER_FLAT only when the gate
passes, otherwise NO_TRADE with explicit reasons. Nothing here places orders,
reads credentials, or touches an exchange account.

Research tooling only — not investment advice.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from futures_backtest import Bar, compute_signals, max_drawdown_pct
from walk_forward import (
    DISCLAIMER,
    RiskGateConfig,
    Variant,
    WalkForwardConfig,
    build_grid,
    default_grid,
    run_walk_forward,
    select_variant,
)

from lake_source import ROOT

DEFAULT_OUT_DIR = ROOT / "data" / "generated" / "reports" / "trading"
INTERVAL_MS = {"15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
SIDE_DECISION = {1: "PAPER_LONG", -1: "PAPER_SHORT", 0: "PAPER_FLAT"}
TRACK_RECORD_MIN_DAYS = 90
MAX_MISSING_BAR_RATIO = 0.005


def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def fast_grid(wf: WalkForwardConfig) -> list[Variant]:
    """Small grid for quick runs: 3 EMA pairs x 2 ADX x 2 modes x spot/futures x1."""
    return build_grid(
        wf,
        ema_pairs=[(9, 21), (12, 26), (20, 50)],
        adx_thresholds=[20.0, 25.0],
        modes=["long_only", "long_short"],
        instruments=[("spot", 1), ("futures", 1)],
    )


def data_blockers(bars: Sequence[Bar], quality: dict, *, interval: str, now_ms: int, train_bars: int) -> list[str]:
    step = INTERVAL_MS[interval]
    blockers = []
    if not bars:
        return ["no bars"]
    close_of_last = bars[-1].open_time_ms + step
    stale_bars = (now_ms - close_of_last) // step
    if stale_bars > 2:
        blockers.append(f"data stale: last closed bar {iso(close_of_last)} is {stale_bars} bars old")
    recent_start = bars[-min(train_bars, len(bars))].open_time_ms
    recent_gaps = [g for g in quality.get("gaps", []) if g[0] >= recent_start]
    if recent_gaps:
        blockers.append(f"{len(recent_gaps)} gap(s) inside the most recent train window")
    missing = quality.get("missing_bars", 0)
    if bars and missing / (len(bars) + missing) > MAX_MISSING_BAR_RATIO:
        blockers.append(f"{missing} missing bars exceed {MAX_MISSING_BAR_RATIO:.1%} of history")
    return blockers


def evaluate_symbol(
    symbol: str,
    bars: Sequence[Bar],
    funding,
    quality: dict,
    *,
    interval: str,
    now_ms: int,
    wf: WalkForwardConfig,
    gate: RiskGateConfig,
    grid: Sequence[Variant],
) -> dict[str, Any]:
    step = INTERVAL_MS[interval]
    blockers = data_blockers(bars, quality, interval=interval, now_ms=now_ms, train_bars=wf.train_bars)
    base = {
        "symbol": symbol,
        "interval": interval,
        "bars": len(bars),
        "quality": {k: v for k, v in quality.items() if k != "gaps"},
        "as_of_open_ms": bars[-1].open_time_ms if bars else None,
        "as_of_close": iso(bars[-1].open_time_ms + step) if bars else None,
        "last_close": bars[-1].close if bars else None,
    }
    if len(bars) < wf.train_bars + wf.test_bars:
        blockers.append(
            f"only {len(bars)} bars; walk-forward needs {wf.train_bars + wf.test_bars}"
        )
    if blockers and len(bars) < wf.train_bars + wf.test_bars:
        return {**base, "decision": "NO_TRADE", "reasons": blockers}

    report = run_walk_forward(bars, wf, gate, mode="select", grid=grid, funding=funding)
    oos = report["variants"][0]
    current = select_variant(bars[-wf.train_bars:], grid, funding)
    side = compute_signals(bars[-wf.train_bars:], current.cfg)[-1]
    reasons = list(blockers)
    if oos["gate"]["verdict"] != "PASS":
        reasons.extend(oos["gate"]["reasons"])
    decision = "NO_TRADE" if reasons else SIDE_DECISION[side]
    return {
        **base,
        "decision": decision,
        "reasons": reasons,
        "would_be_side": SIDE_DECISION[side],
        "variant": current.name,
        "variant_config": asdict(current.cfg),
        "gate": oos["gate"],
        "oos": {
            k: oos.get(k)
            for k in (
                "median_window_return_pct",
                "sharpe",
                "max_drawdown_pct",
                "pct_profitable_windows",
                "worst_window_return_pct",
            )
        },
        "baseline_median_window_return_pct": report["baseline"].get("median_window_return_pct"),
        "num_windows": report["num_windows"],
    }


# ---------------------------------------------------------------------------
# Paper journal
# ---------------------------------------------------------------------------


def load_journal(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def append_journal(path: Path, results: Sequence[dict[str, Any]], *, recorded_at: str) -> int:
    journal = load_journal(path)
    seen = {(e["symbol"], e["as_of_open_ms"]) for e in journal}
    added = 0
    for r in results:
        if r.get("as_of_open_ms") is None or (r["symbol"], r["as_of_open_ms"]) in seen:
            continue
        journal.append(
            {
                "symbol": r["symbol"],
                "as_of_open_ms": r["as_of_open_ms"],
                "as_of_close": r["as_of_close"],
                "close": r["last_close"],
                "decision": r["decision"],
                "variant": r.get("variant"),
                "recorded_at": recorded_at,
            }
        )
        added += 1
    journal.sort(key=lambda e: (e["symbol"], e["as_of_open_ms"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(journal, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return added


def paper_track_record(journal: Sequence[dict[str, Any]], symbol: str, *, cost_bps: float = 7.0) -> dict[str, Any]:
    """Score consecutive journal entries as a 1x-notional paper position."""
    entries = [e for e in journal if e["symbol"] == symbol]
    position = {"PAPER_LONG": 1, "PAPER_SHORT": -1}
    equity, curve, prev_pos = 1.0, [], 0
    for cur, nxt in zip(entries, entries[1:]):
        pos = position.get(cur["decision"], 0)
        cost = abs(pos - prev_pos) * cost_bps / 10_000
        equity *= (1 + pos * (nxt["close"] / cur["close"] - 1)) * (1 - cost)
        curve.append((nxt["as_of_open_ms"], equity))
        prev_pos = pos
    days = (
        (entries[-1]["as_of_open_ms"] - entries[0]["as_of_open_ms"]) / 86_400_000
        if len(entries) > 1
        else 0.0
    )
    hold = entries[-1]["close"] / entries[0]["close"] - 1 if len(entries) > 1 else 0.0
    total = equity - 1
    return {
        "symbol": symbol,
        "entries": len(entries),
        "days_tracked": round(days, 1),
        "paper_return_pct": round(total * 100, 2),
        "buy_and_hold_pct": round(hold * 100, 2),
        "max_drawdown_pct": round(max_drawdown_pct(curve), 2) if curve else 0.0,
        "track_record_met": days >= TRACK_RECORD_MIN_DAYS and total > 0 and total > hold,
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _num(x):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.2f}"


def _pct(x):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.2f}%"


def render(results: Sequence[dict], records: Sequence[dict], *, generated_at: str) -> str:
    lines = [
        "# Paper Trading Signal Report",
        "",
        f"Generated: {generated_at} · Source: Data Lakehouse Silver `crypto_ohlcv` / `crypto_funding`",
        "",
        f"> {DISCLAIMER} PAPER decisions only — no orders are placed.",
        "",
        "| Symbol | As of (bar close) | Close | Decision | Would-be side | Gate | OOS Sharpe | OOS max DD | Median window vs spot |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        oos = r.get("oos", {})
        lines.append(
            f"| {r['symbol']} | {r.get('as_of_close') or 'n/a'} | {r.get('last_close') or 'n/a'} "
            f"| **{r['decision']}** | {r.get('would_be_side', 'n/a')} "
            f"| {r.get('gate', {}).get('verdict', 'n/a')} | {_num(oos.get('sharpe')) if oos else 'n/a'} "
            f"| {_pct(oos.get('max_drawdown_pct')) if oos else 'n/a'} "
            f"| {_pct(oos.get('median_window_return_pct')) if oos else 'n/a'} vs {_pct(r.get('baseline_median_window_return_pct'))} |"
        )
    lines += ["", "## Reasons", ""]
    for r in results:
        reasons = r.get("reasons") or ["gate passed; no blockers"]
        lines.append(f"- **{r['symbol']}**: " + "; ".join(reasons))
        if r.get("variant"):
            lines.append(f"  - current variant (train-selected): `{r['variant']}`")
    lines += [
        "",
        f"## Paper track record (1x notional, costs included; needs ≥{TRACK_RECORD_MIN_DAYS} days)",
        "",
        "| Symbol | Entries | Days | Paper return | Buy & hold | Max DD | Requirement met |",
        "|---|---|---|---|---|---|---|",
    ]
    for t in records:
        lines.append(
            f"| {t['symbol']} | {t['entries']} | {t['days_tracked']} | {_pct(t['paper_return_pct'])} "
            f"| {_pct(t['buy_and_hold_pct'])} | {_pct(t['max_drawdown_pct'])} | {'yes' if t['track_record_met'] else 'no'} |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT")
    ap.add_argument("--interval", default="1h", choices=sorted(INTERVAL_MS))
    ap.add_argument("--venue", default="binance_futures")
    ap.add_argument("--data-lake-uri", default=None)
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    ap.add_argument("--journal", default=None, help="paper journal JSON (default: <out-dir>/paper-journal.json)")
    ap.add_argument("--grid", choices=["fast", "full"], default="fast")
    ap.add_argument("--no-journal", action="store_true")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)

    import lake_source

    lake_uri = args.data_lake_uri or lake_source.DEFAULT_LAKE_URI
    now_ms = int(time.time() * 1000)
    generated_at = iso(now_ms)
    wf, gate = WalkForwardConfig(), RiskGateConfig()
    grid = fast_grid(wf) if args.grid == "fast" else default_grid(wf)

    results = []
    for symbol in [s.strip().upper() for s in args.symbols.split(",") if s.strip()]:
        try:
            bars, quality = lake_source.load_bars(
                symbol, interval=args.interval, venue=args.venue, data_lake_uri=lake_uri
            )
        except lake_source.LakeDataError as exc:
            results.append({"symbol": symbol, "decision": "NO_TRADE", "reasons": [str(exc)], "as_of_open_ms": None})
            continue
        funding = lake_source.load_funding(symbol, venue=args.venue, data_lake_uri=lake_uri) or None
        q = {**quality.as_dict(), "gaps": quality.gaps}
        results.append(
            evaluate_symbol(
                symbol, bars, funding, q, interval=args.interval, now_ms=now_ms,
                wf=wf, gate=gate, grid=grid,
            )
        )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    journal_path = Path(args.journal) if args.journal else out_dir / "paper-journal.json"
    added = 0 if args.no_journal else append_journal(journal_path, results, recorded_at=generated_at)
    journal = load_journal(journal_path)
    records = [paper_track_record(journal, r["symbol"]) for r in results]

    stamp = generated_at[:10]
    payload = {
        "schema_version": "trading.paper-signal.v1",
        "generated_at": generated_at,
        "disclaimer": DISCLAIMER,
        "orders_placed": False,
        "data_source": {"layer": "silver", "datasets": ["crypto_ohlcv", "crypto_funding"], "venue": args.venue},
        "results": results,
        "journal": {"path": str(journal_path), "entries_added": added},
        "track_record": records,
    }
    (out_dir / f"signal-{stamp}.json").write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    markdown = render(results, records, generated_at=generated_at)
    (out_dir / f"signal-{stamp}.md").write_text(markdown, encoding="utf-8")
    print(json.dumps(payload, indent=2, default=str) if args.as_json else markdown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
