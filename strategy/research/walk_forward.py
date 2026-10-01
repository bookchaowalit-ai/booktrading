#!/usr/bin/env python3
"""Phase 4 walk-forward strategy validator (read-only research tooling).

Proves — or disproves — whether an EMA/ADX futures strategy is consistent
out-of-sample (OOS) before leverage or real money is ever considered. This
tool places NO orders, uses NO credentials and gives NO investment advice.

Scheme: rolling [train][test] windows sliding by ``step`` over the bar
series. Two evaluation modes:

* ``fixed``  — every grid variant is evaluated on every test window.
* ``select`` — for each window the best variant is chosen ON THE TRAIN
  SLICE ONLY (by Sharpe; ties broken by lower max drawdown, then grid
  order) and the frozen variant is then evaluated on the test slice. The
  selection function receives only the train slice by construction, so the
  test slice cannot leak into parameter selection.

A spot buy-and-hold-after-costs baseline over the same test windows is
always included. The risk gate compares each variant against that baseline.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from futures_backtest import (  # noqa: E402
    MS_PER_YEAR,
    Bar,
    StrategyConfig,
    Trade,
    compute_metrics,
    median_interval_ms,
    profit_factor,
    run_backtest,
    sharpe_ratio,
)

DISCLAIMER = (
    "Research tooling only — not investment advice. Read-only: "
    "no exchange credentials, no order placement, no mainnet "
    "execution anywhere in this code."
)


@dataclass(frozen=True)
class WalkForwardConfig:
    train_bars: int = 2160  # ~90 days of 1h bars
    test_bars: int = 720  # ~30 days
    step_bars: int = 720
    initial_equity: float = 10000.0
    taker_fee_bps: float = 5.0
    slippage_bps: float = 2.0
    funding_rate_bps_per_8h: float = 1.0
    maintenance_margin_rate: float = 0.005


@dataclass(frozen=True)
class RiskGateConfig:
    max_drawdown_pct: float = 25.0
    min_sharpe: float = 0.0
    min_profitable_windows_pct: float = 40.0
    must_beat_spot: bool = True


@dataclass(frozen=True)
class Variant:
    name: str
    cfg: StrategyConfig


# ---------------------------------------------------------------------------
# Windows and grid
# ---------------------------------------------------------------------------


def make_windows(
    n_bars: int, cfg: WalkForwardConfig
) -> list[tuple[int, int, int, int]]:
    """Return (train_start, train_end, test_start, test_end) index tuples."""
    windows = []
    start = 0
    while start + cfg.train_bars + cfg.test_bars <= n_bars:
        windows.append(
            (
                start,
                start + cfg.train_bars,
                start + cfg.train_bars,
                start + cfg.train_bars + cfg.test_bars,
            )
        )
        start += cfg.step_bars
    return windows


def default_grid(wf: WalkForwardConfig) -> list[Variant]:
    """Full default grid: 3 EMA pairs x 3 ADX thresholds x 2 modes x
    (spot, futures @ 1/2/3/5) = 90 variants."""
    return build_grid(
        wf,
        ema_pairs=[(9, 21), (12, 26), (20, 50)],
        adx_thresholds=[20.0, 25.0, 30.0],
        modes=["long_only", "long_short"],
        instruments=[
            ("spot", 1),
            ("futures", 1),
            ("futures", 2),
            ("futures", 3),
            ("futures", 5),
        ],
    )


def build_grid(
    wf: WalkForwardConfig, ema_pairs, adx_thresholds, modes, instruments
) -> list[Variant]:
    variants = []
    for ef, es in ema_pairs:
        for thr in adx_thresholds:
            for mode in modes:
                for instrument, lev in instruments:
                    suffix = f"x{lev}" if instrument == "futures" else ""
                    name = f"ema{ef}/{es}-adx{thr:g}-{mode}-{instrument}{suffix}"
                    variants.append(
                        Variant(
                            name,
                            StrategyConfig(
                                ema_fast=ef,
                                ema_slow=es,
                                adx_threshold=thr,
                                mode=mode,
                                instrument=instrument,
                                leverage=lev,
                                taker_fee_bps=wf.taker_fee_bps,
                                slippage_bps=wf.slippage_bps,
                                funding_rate_bps_per_8h=wf.funding_rate_bps_per_8h,
                                maintenance_margin_rate=wf.maintenance_margin_rate,
                                initial_equity=wf.initial_equity,
                            ),
                        )
                    )
    return variants


# ---------------------------------------------------------------------------
# Spot buy-and-hold-after-costs baseline
# ---------------------------------------------------------------------------


def buy_and_hold(bars: Sequence[Bar], wf: WalkForwardConfig):
    """Buy at the first bar's open, sell at the last bar's close, paying
    taker fee and slippage on both sides. Returns (trades, equity_curve,
    metrics) matching the engine's shapes."""
    fee = wf.taker_fee_bps / 1e4
    slip = wf.slippage_bps / 1e4
    entry = bars[0].open * (1.0 + slip)
    qty = wf.initial_equity / entry
    entry_fee = wf.initial_equity * fee
    exit_fill = bars[-1].close * (1.0 - slip)
    exit_fee = qty * exit_fill * fee
    pnl = qty * (exit_fill - entry)
    equity_curve = [(b.open_time_ms, qty * b.close - entry_fee) for b in bars]
    trade = Trade(
        entry_time_ms=bars[0].open_time_ms,
        exit_time_ms=bars[-1].open_time_ms,
        side="long",
        entry_price=entry,
        exit_price=exit_fill,
        qty=qty,
        pnl=pnl,
        fees=entry_fee + exit_fee,
        funding_paid=0.0,
        reason="end_of_data",
    )
    interval = median_interval_ms(bars)
    metrics = compute_metrics(equity_curve, [trade], interval, wf.initial_equity)
    return [trade], equity_curve, metrics


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def _window_metrics(
    bars: Sequence[Bar], windows, variant: Variant, funding
) -> list[dict]:
    rows = []
    for _, _, ts, te in windows:
        result = run_backtest(bars[ts:te], variant.cfg, funding)
        rows.append({"metrics": result.metrics, "trades": result.trades})
    return rows


def aggregate_window_rows(
    rows: list[dict], test_bars: int, bar_interval_ms: float
) -> dict:
    """Summarize per-window OOS results into one report row."""
    rets = [r["metrics"]["total_return_pct"] for r in rows]
    all_pnls = [t.pnl for r in rows for t in r["trades"]]
    windows_per_year = (MS_PER_YEAR / bar_interval_ms) / test_bars
    stitched = sharpe_ratio([r / 100.0 for r in rets], windows_per_year)
    n = len(rows)
    profitable = sum(1 for r in rets if r > 0)
    return {
        "num_windows": n,
        "median_window_return_pct": statistics.median(rets) if rets else 0.0,
        "worst_window_return_pct": min(rets) if rets else 0.0,
        "max_drawdown_pct": max(
            (r["metrics"]["max_drawdown_pct"] for r in rows), default=0.0
        ),
        "sharpe": stitched,
        "profit_factor": profit_factor(all_pnls),
        "pct_profitable_windows": (profitable / n * 100.0) if n else 0.0,
    }


def select_variant(
    train_bars: Sequence[Bar], grid: Sequence[Variant], funding
) -> Variant:
    """Pick the best variant on the TRAIN SLICE ONLY.

    By Sharpe, tie-break by lower max drawdown, then grid order. The test
    slice is never passed to this function — train/test separation holds
    by construction.
    """
    best = None
    best_key = None
    for variant in grid:
        result = run_backtest(list(train_bars), variant.cfg, funding)
        key = (-result.metrics["sharpe"], result.metrics["max_drawdown_pct"])
        if best_key is None or key < best_key:
            best_key = key
            best = variant
    return best


def evaluate_gate(report_row: dict, baseline_row: dict, gate: RiskGateConfig) -> dict:
    """Return {"verdict": "PASS"|"FAIL", "reasons": [...]}."""
    reasons = []
    if gate.must_beat_spot and not (
        report_row["median_window_return_pct"]
        > baseline_row["median_window_return_pct"]
    ):
        reasons.append(
            f"median OOS return {report_row['median_window_return_pct']:.2f}%"
            " does not beat spot baseline "
            f"{baseline_row['median_window_return_pct']:.2f}%"
        )
    if report_row["max_drawdown_pct"] > gate.max_drawdown_pct:
        reasons.append(
            f"max drawdown {report_row['max_drawdown_pct']:.2f}% exceeds "
            f"limit {gate.max_drawdown_pct:.2f}%"
        )
    if report_row["sharpe"] < gate.min_sharpe:
        reasons.append(
            f"sharpe {report_row['sharpe']:.3f} below minimum {gate.min_sharpe:.3f}"
        )
    if report_row["pct_profitable_windows"] < gate.min_profitable_windows_pct:
        reasons.append(
            f"profitable windows {report_row['pct_profitable_windows']:.1f}%"
            f" below minimum {gate.min_profitable_windows_pct:.1f}%"
        )
    return {"verdict": "PASS" if not reasons else "FAIL", "reasons": reasons}


# ---------------------------------------------------------------------------
# Top-level runner
# ---------------------------------------------------------------------------


def run_walk_forward(
    bars: Sequence[Bar],
    wf: WalkForwardConfig,
    gate: RiskGateConfig,
    mode: str = "fixed",
    grid: Sequence[Variant] | None = None,
    funding=None,
) -> dict:
    if mode not in ("fixed", "select"):
        raise ValueError(f"bad mode: {mode}")
    if grid is None:
        grid = default_grid(wf)
    windows = make_windows(len(bars), wf)
    if not windows:
        raise ValueError(
            f"not enough bars ({len(bars)}) for train={wf.train_bars} "
            f"+ test={wf.test_bars}"
        )
    interval = median_interval_ms(bars)

    # Spot buy-and-hold-after-costs baseline over the same OOS windows.
    baseline_rows = []
    for _, _, ts, te in windows:
        trades, _, metrics = buy_and_hold(bars[ts:te], wf)
        baseline_rows.append({"metrics": metrics, "trades": trades})
    baseline = aggregate_window_rows(baseline_rows, wf.test_bars, interval)
    baseline["name"] = "spot-buy-and-hold-after-costs"

    variants_out = []
    if mode == "fixed":
        for variant in grid:
            rows = _window_metrics(bars, windows, variant, funding)
            row = aggregate_window_rows(rows, wf.test_bars, interval)
            row["name"] = variant.name
            row["gate"] = evaluate_gate(row, baseline, gate)
            variants_out.append(row)
    else:  # select
        rows = []
        selections = []
        for trs, tre, ts, te in windows:
            chosen = select_variant(bars[trs:tre], grid, funding)
            selections.append(chosen.name)
            result = run_backtest(bars[ts:te], chosen.cfg, funding)
            rows.append({"metrics": result.metrics, "trades": result.trades})
        row = aggregate_window_rows(rows, wf.test_bars, interval)
        row["name"] = "select-best-on-train"
        row["selections"] = selections
        row["gate"] = evaluate_gate(row, baseline, gate)
        variants_out.append(row)

    return {
        "disclaimer": DISCLAIMER,
        "mode": mode,
        "config": {
            "train_bars": wf.train_bars,
            "test_bars": wf.test_bars,
            "step_bars": wf.step_bars,
            "initial_equity": wf.initial_equity,
            "taker_fee_bps": wf.taker_fee_bps,
            "slippage_bps": wf.slippage_bps,
            "funding_rate_bps_per_8h": wf.funding_rate_bps_per_8h,
            "maintenance_margin_rate": wf.maintenance_margin_rate,
        },
        "gate": {
            "max_drawdown_pct": gate.max_drawdown_pct,
            "min_sharpe": gate.min_sharpe,
            "min_profitable_windows_pct": gate.min_profitable_windows_pct,
            "must_beat_spot": gate.must_beat_spot,
        },
        "num_windows": len(windows),
        "baseline": baseline,
        "variants": variants_out,
    }


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def _fmt_pct(x):
    return f"{x:.2f}%"


def _fmt_pf(x):
    return "inf" if math.isinf(x) else f"{x:.3f}"


def render_markdown(report: dict) -> str:
    lines = [
        "# Phase 4 Walk-Forward Validation Report",
        "",
        f"> {DISCLAIMER}",
        "",
        f"- Mode: `{report['mode']}`",
        (
            f"- Windows: {report['num_windows']} "
            f"(train={report['config']['train_bars']}, "
            f"test={report['config']['test_bars']}, "
            f"step={report['config']['step_bars']} bars)"
        ),
        (
            f"- Costs: taker {report['config']['taker_fee_bps']} bps, "
            f"slippage {report['config']['slippage_bps']} bps, "
            f"funding fallback {report['config']['funding_rate_bps_per_8h']} bps/8h"
        ),
        (
            f"- Risk gate: maxDD <= {report['gate']['max_drawdown_pct']}%, "
            f"sharpe >= {report['gate']['min_sharpe']}, "
            f"profitable windows >= {report['gate']['min_profitable_windows_pct']}%, "
            f"must beat spot: {report['gate']['must_beat_spot']}"
        ),
        "",
        "| Variant | Median OOS | Worst OOS | Max DD | Sharpe | PF | Win windows | Gate |",
        "|---|---|---|---|---|---|---|---|",
    ]
    b = report["baseline"]
    lines.append(
        f"| **{b['name']}** | {_fmt_pct(b['median_window_return_pct'])} "
        f"| {_fmt_pct(b['worst_window_return_pct'])} "
        f"| {_fmt_pct(b['max_drawdown_pct'])} | {b['sharpe']:.3f} "
        f"| {_fmt_pf(b['profit_factor'])} "
        f"| {_fmt_pct(b['pct_profitable_windows'])} | baseline |"
    )
    for v in report["variants"]:
        verdict = v["gate"]["verdict"]
        lines.append(
            f"| {v['name']} | {_fmt_pct(v['median_window_return_pct'])} "
            f"| {_fmt_pct(v['worst_window_return_pct'])} "
            f"| {_fmt_pct(v['max_drawdown_pct'])} | {v['sharpe']:.3f} "
            f"| {_fmt_pf(v['profit_factor'])} "
            f"| {_fmt_pct(v['pct_profitable_windows'])} | **{verdict}** |"
        )
    lines.append("")
    lines.append("## Gate failure reasons")
    lines.append("")
    any_reason = False
    for v in report["variants"]:
        if v["gate"]["verdict"] == "FAIL":
            any_reason = True
            lines.append(f"- `{v['name']}`: " + "; ".join(v["gate"]["reasons"]))
    if not any_reason:
        lines.append("- none — all variants passed the gate")
    if report["mode"] == "select":
        lines.append("")
        lines.append("## Selections per window (chosen on train slice only)")
        lines.append("")
        for i, name in enumerate(report["variants"][0].get("selections", [])):
            lines.append(f"- window {i}: `{name}`")
    lines += [
        "",
        "---",
        "",
        f"*{DISCLAIMER}*",
        "",
    ]
    return "\n".join(lines)


def _jsonable(obj):
    if isinstance(obj, float) and not math.isfinite(obj):
        return "Infinity" if obj > 0 else "-Infinity"
    raise TypeError(type(obj).__name__)


def write_reports(report: dict, md_path=None, json_path=None) -> None:
    if md_path:
        Path(md_path).parent.mkdir(parents=True, exist_ok=True)
        Path(md_path).write_text(render_markdown(report))
    if json_path:
        Path(json_path).parent.mkdir(parents=True, exist_ok=True)
        Path(json_path).write_text(json.dumps(report, indent=2, default=_jsonable))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_ema_pairs(text: str):
    return [tuple(int(x) for x in p.split("/")) for p in text.split(",")]


def _parse_floats(text: str):
    return [float(x) for x in text.split(",")]


def _parse_instruments(text: str):
    out = []
    for tok in text.split(","):
        name, _, lev = tok.partition(":")
        out.append((name, int(lev) if lev else 1))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Phase 4 walk-forward validator. " + DISCLAIMER
    )
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument("--csv", help="bar cache CSV")
    source.add_argument(
        "--lake-symbol",
        help="read closed bars from the Data Lakehouse Silver layer (e.g. BTCUSDT)",
    )
    ap.add_argument("--lake-interval", default="1h")
    ap.add_argument("--lake-venue", default="binance_futures")
    ap.add_argument("--data-lake-uri", default=None)
    ap.add_argument(
        "--funding-csv", default=None, help="optional funding series CSV (time_ms,rate)"
    )
    ap.add_argument("--out", help="markdown report path")
    ap.add_argument("--json", dest="json_out", help="JSON report path")
    ap.add_argument("--mode", choices=["fixed", "select"], default="fixed")
    ap.add_argument("--train", type=int, default=2160)
    ap.add_argument("--test", type=int, default=720)
    ap.add_argument("--step", type=int, default=720)
    ap.add_argument(
        "--ema-pairs",
        default=None,
        help="e.g. '9/21,12/26,20/50' (default grid if unset)",
    )
    ap.add_argument("--adx-thresholds", default=None, help="e.g. '20,25,30'")
    ap.add_argument("--modes", default=None, help="e.g. 'long_only,long_short'")
    ap.add_argument(
        "--instruments",
        default=None,
        help="e.g. 'spot:1,futures:1,futures:2,futures:3,futures:5'",
    )
    ap.add_argument("--taker-fee-bps", type=float, default=5.0)
    ap.add_argument("--slippage-bps", type=float, default=2.0)
    ap.add_argument("--funding-bps-per-8h", type=float, default=1.0)
    ap.add_argument("--initial-equity", type=float, default=10000.0)
    ap.add_argument("--gate-max-dd", type=float, default=25.0)
    ap.add_argument("--gate-min-sharpe", type=float, default=0.0)
    ap.add_argument("--gate-min-profitable-pct", type=float, default=40.0)
    ap.add_argument(
        "--gate-must-beat-spot", action=argparse.BooleanOptionalAction, default=True
    )
    args = ap.parse_args(argv)

    from data import load_csv, load_funding_csv

    if args.lake_symbol:
        import lake_source

        lake_uri = args.data_lake_uri or lake_source.DEFAULT_LAKE_URI
        bars, quality = lake_source.load_bars(
            args.lake_symbol,
            interval=args.lake_interval,
            venue=args.lake_venue,
            data_lake_uri=lake_uri,
        )
        if quality.gaps:
            print(
                f"WARNING: {quality.missing_bars} missing bars in {len(quality.gaps)} gaps",
                file=sys.stderr,
            )
        funding = (
            load_funding_csv(args.funding_csv)
            if args.funding_csv
            else lake_source.load_funding(
                args.lake_symbol, venue=args.lake_venue, data_lake_uri=lake_uri
            )
            or None
        )
    else:
        bars = load_csv(args.csv)
        funding = load_funding_csv(args.funding_csv) if args.funding_csv else None
    wf = WalkForwardConfig(
        train_bars=args.train,
        test_bars=args.test,
        step_bars=args.step,
        initial_equity=args.initial_equity,
        taker_fee_bps=args.taker_fee_bps,
        slippage_bps=args.slippage_bps,
        funding_rate_bps_per_8h=args.funding_bps_per_8h,
    )
    gate = RiskGateConfig(
        max_drawdown_pct=args.gate_max_dd,
        min_sharpe=args.gate_min_sharpe,
        min_profitable_windows_pct=args.gate_min_profitable_pct,
        must_beat_spot=args.gate_must_beat_spot,
    )
    grid = None
    if any([args.ema_pairs, args.adx_thresholds, args.modes, args.instruments]):
        grid = build_grid(
            wf,
            ema_pairs=_parse_ema_pairs(args.ema_pairs)
            if args.ema_pairs
            else [(9, 21), (12, 26), (20, 50)],
            adx_thresholds=_parse_floats(args.adx_thresholds)
            if args.adx_thresholds
            else [20.0, 25.0, 30.0],
            modes=args.modes.split(",") if args.modes else ["long_only", "long_short"],
            instruments=_parse_instruments(args.instruments)
            if args.instruments
            else [
                ("spot", 1),
                ("futures", 1),
                ("futures", 2),
                ("futures", 3),
                ("futures", 5),
            ],
        )
    report = run_walk_forward(
        bars, wf, gate, mode=args.mode, grid=grid, funding=funding
    )
    write_reports(report, md_path=args.out, json_path=args.json_out)
    print(render_markdown(report))
    return 0  # always 0: this is research tooling, gate lives in the report


if __name__ == "__main__":
    raise SystemExit(main())
