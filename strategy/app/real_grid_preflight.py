"""Read-only Binance TH readiness checks for the real-grid symbol set.

This module deliberately uses only public exchange metadata and 24-hour ticker
data.  It never reads account balances and never places, cancels, or modifies
orders.
"""

from __future__ import annotations

import asyncio
import math
import os
from collections.abc import Iterable
from typing import Any

import httpx

from app.real_grid_bot import (
    BINANCE_PUBLIC_REST,
    GRID_CAPITAL_BASE_THB,
    GRID_MAX_PORTFOLIO_NOTIONAL_THB,
    SYMBOL_DEFAULTS,
)
from app.risk_manager import RiskConfig

DEFAULT_MAX_ORDER_SIZE_THB = 200.0
DEFAULT_MAX_OPEN_ORDERS = RiskConfig().max_open_orders
LIQUIDITY_WARNING_QUOTE_VOLUME_THB = 100_000.0
VOLATILITY_WARNING_PCT = 10.0
DEFAULT_PREFLIGHT_SYMBOLS = tuple(SYMBOL_DEFAULTS)


def parse_symbols(raw: str | None = None) -> list[str]:
    """Return normalized, de-duplicated symbols for a preflight run."""
    value = raw if raw is not None else os.getenv("REAL_PREFLIGHT_SYMBOLS")
    if not value:
        value = ",".join(DEFAULT_PREFLIGHT_SYMBOLS)

    symbols: list[str] = []
    for item in value.split(","):
        symbol = item.strip().upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_step_multiple(quantity: float, step_size: float) -> bool:
    if step_size <= 0:
        return True
    units = round(quantity / step_size)
    return math.isclose(
        quantity,
        units * step_size,
        rel_tol=0.0,
        abs_tol=max(step_size * 1e-6, 1e-12),
    )


def _is_tick_compatible(configured_tick: float, exchange_tick: float) -> bool:
    if configured_tick <= 0 or exchange_tick <= 0:
        return False
    return _is_step_multiple(configured_tick, exchange_tick)


def _exchange_rules(exchange_symbol: dict[str, Any] | None) -> dict[str, float]:
    if not exchange_symbol:
        return {
            "min_notional": 0.0,
            "step_size": 0.0,
            "tick_size": 0.0,
            "min_qty": 0.0,
        }

    filters = {
        item.get("filterType"): item
        for item in exchange_symbol.get("filters", [])
        if isinstance(item, dict) and item.get("filterType")
    }
    lot_size = filters.get("LOT_SIZE", {})
    price_filter = filters.get("PRICE_FILTER", {})
    notional_filter = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL", {})
    return {
        "min_notional": _as_float(notional_filter.get("minNotional")),
        "step_size": _as_float(lot_size.get("stepSize")),
        "tick_size": _as_float(price_filter.get("tickSize")),
        "min_qty": _as_float(lot_size.get("minQty")),
    }


def validate_symbol_snapshot(
    symbol: str,
    exchange_symbol: dict[str, Any] | None,
    ticker: dict[str, Any] | None,
    config: dict[str, Any] | None = None,
    *,
    max_order_size_thb: float = DEFAULT_MAX_ORDER_SIZE_THB,
) -> dict[str, Any]:
    """Validate one symbol using already-fetched public exchange data."""
    config = config or SYMBOL_DEFAULTS.get(symbol, {})
    rules = _exchange_rules(exchange_symbol)
    price = _as_float((ticker or {}).get("lastPrice"))
    quote_volume = _as_float((ticker or {}).get("quoteVolume"))
    change_pct = _as_float((ticker or {}).get("priceChangePercent"))
    order_size = _as_float(config.get("order_size"))
    order_notional = order_size * price
    status = (exchange_symbol or {}).get("status")
    configured_tick = _as_float(config.get("tick_size"), rules["tick_size"])

    checks = {
        "symbol_exists": exchange_symbol is not None,
        "symbol_trading": status == "TRADING",
        "ticker_available": price > 0,
        "order_size_step_ok": _is_step_multiple(order_size, rules["step_size"]),
        "min_notional_ok": order_notional >= rules["min_notional"] if rules["min_notional"] else False,
        "max_order_size_ok": order_notional <= max_order_size_thb if order_notional > 0 else False,
        "tick_size_compatible": _is_tick_compatible(configured_tick, rules["tick_size"]),
    }

    blockers: list[str] = []
    if not checks["symbol_exists"]:
        blockers.append("symbol_not_found")
    elif not checks["symbol_trading"]:
        blockers.append(f"symbol_status_{status or 'unknown'}")
    if not checks["ticker_available"]:
        blockers.append("ticker_unavailable")
    if not checks["order_size_step_ok"]:
        blockers.append("order_size_not_on_exchange_step")
    if not checks["min_notional_ok"]:
        blockers.append("order_below_min_notional")
    if not checks["max_order_size_ok"]:
        blockers.append("order_above_risk_max_order_size")
    if not checks["tick_size_compatible"]:
        blockers.append("configured_tick_size_incompatible")

    warnings: list[str] = []
    if quote_volume < LIQUIDITY_WARNING_QUOTE_VOLUME_THB:
        warnings.append("low_24h_quote_volume")
    if abs(change_pct) >= VOLATILITY_WARNING_PCT:
        warnings.append("high_24h_price_move")

    return {
        "ready": not blockers,
        "symbol": symbol,
        "status": status,
        "price": price,
        "quote_volume_24h_thb": quote_volume,
        "price_change_24h_pct": change_pct,
        "configured": {
            "order_size": order_size,
            "order_notional_thb": round(order_notional, 4),
            "grid_levels": int(config.get("grid_levels", 0) or 0),
            "max_position": _as_float(config.get("max_position")),
            "configured_tick_size": configured_tick,
        },
        "exchange_rules": rules,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
    }


async def _get_json(
    client: httpx.AsyncClient,
    path: str,
    params: dict[str, str] | None = None,
) -> Any:
    response = await client.get(path, params=params)
    response.raise_for_status()
    return response.json()


async def run_preflight(
    symbols: Iterable[str] | str | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Run a read-only multi-symbol preflight and return a JSON-safe report."""
    if isinstance(symbols, str):
        symbol_list = parse_symbols(symbols)
    elif symbols is None:
        symbol_list = parse_symbols()
    else:
        symbol_list = parse_symbols(",".join(symbols))

    if not symbol_list:
        return {"ready": False, "symbols": {}, "error": "No symbols supplied"}

    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=15.0)
    try:
        exchange_info = await _get_json(http, f"{BINANCE_PUBLIC_REST}/api/v1/exchangeInfo")
        exchange_symbols = {
            item.get("symbol"): item
            for item in exchange_info.get("symbols", [])
            if isinstance(item, dict) and item.get("symbol")
        }

        async def fetch_ticker(symbol: str) -> tuple[str, dict[str, Any] | None, str | None]:
            try:
                return symbol, await _get_json(
                    http,
                    f"{BINANCE_PUBLIC_REST}/api/v1/ticker/24hr",
                    {"symbol": symbol},
                ), None
            except Exception as exc:
                return symbol, None, str(exc)

        ticker_results = await asyncio.gather(*(fetch_ticker(symbol) for symbol in symbol_list))
        reports: dict[str, dict[str, Any]] = {}
        for symbol, ticker, ticker_error in ticker_results:
            report = validate_symbol_snapshot(
                symbol,
                exchange_symbols.get(symbol),
                ticker,
            )
            if ticker_error:
                report["ready"] = False
                report["blockers"].append("ticker_request_failed")
                report["ticker_error"] = ticker_error
            reports[symbol] = report

        configured_order_notionals = [
            item["configured"]["order_notional_thb"]
            for item in reports.values()
            if item["ready"]
        ]
        total_ready_notional = round(sum(configured_order_notionals), 4)
        return {
            "ready": all(item["ready"] for item in reports.values()),
            "symbols": reports,
            "portfolio": {
                "base_capital_thb": GRID_CAPITAL_BASE_THB,
                "max_portfolio_notional_thb": GRID_MAX_PORTFOLIO_NOTIONAL_THB,
                "max_open_orders": DEFAULT_MAX_OPEN_ORDERS,
                "ready_symbol_count": len(configured_order_notionals),
                "configured_one_order_notional_thb": total_ready_notional,
                "headroom_after_one_order_each_thb": round(
                    GRID_MAX_PORTFOLIO_NOTIONAL_THB - total_ready_notional,
                    4,
                ),
            },
            "read_only": True,
            "order_actions": [],
        }
    except Exception as exc:
        return {
            "ready": False,
            "symbols": {},
            "error": f"Public exchange preflight failed: {exc}",
            "read_only": True,
            "order_actions": [],
        }
    finally:
        if owns_client:
            await http.aclose()
