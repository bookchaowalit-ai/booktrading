"""Helpers for interpreting the persisted Polymarket paper-bot state."""

from typing import Any, Dict, List


PAPER_STATE_KEY = "poly_paper:state"


def is_resolved_position(position: Dict[str, Any]) -> bool:
    """Return whether a persisted position is closed/resolved."""
    return bool(
        position.get("resolved", False)
        or position.get("status") in ("resolved", "closed")
    )


def summarize_paper_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Return the safety-relevant values shared by API and monitor views."""
    raw_positions = state.get("positions", {})
    positions = [
        position
        for position in raw_positions.values()
        if isinstance(position, dict)
    ] if isinstance(raw_positions, dict) else []

    active = [position for position in positions if not is_resolved_position(position)]
    resolved = [position for position in positions if is_resolved_position(position)]
    derived_pnl = sum((position.get("pnl", 0) or 0) for position in positions)
    derived_wins = sum(1 for position in resolved if (position.get("pnl", 0) or 0) > 0)
    total_pnl = state.get("total_pnl")
    total_trades = state.get("total_trades")
    winning_trades = state.get("winning_trades")

    return {
        "active_positions": len(active),
        "resolved_positions": len(resolved),
        "total_positions": len(positions),
        "kill_switch_active": bool(state.get("kill_switch_active", False)),
        "kill_reason": str(state.get("kill_reason", "") or ""),
        "winning_trades": derived_wins if winning_trades is None else winning_trades,
        "bankroll": state.get("bankroll") if state.get("bankroll") is not None else 100.0,
        "peak_bankroll": state.get("peak_bankroll") if state.get("peak_bankroll") is not None else 100.0,
        "total_pnl": derived_pnl if total_pnl is None else total_pnl,
        "total_trades": len(resolved) if total_trades is None else total_trades,
    }


def persisted_positions(state: Dict[str, Any], active_only: bool = False) -> List[Dict[str, Any]]:
    """Return persisted positions using the paper bot's API ordering."""
    raw_positions = state.get("positions", {})
    positions = [
        position
        for position in raw_positions.values()
        if isinstance(position, dict)
    ] if isinstance(raw_positions, dict) else []
    if active_only:
        positions = [position for position in positions if not is_resolved_position(position)]
    return sorted(
        positions,
        key=lambda position: position.get("entry_time", 0) or 0,
        reverse=True,
    )


def persisted_trades(state: Dict[str, Any], limit: int = 50) -> List[Dict[str, Any]]:
    """Return persisted trades, or explicit inferred closes when history is absent."""
    raw_trades = state.get("trades")
    if isinstance(raw_trades, list) and raw_trades:
        return list(reversed(raw_trades[-limit:]))

    inferred = []
    for position in persisted_positions(state):
        if not is_resolved_position(position):
            continue
        position_id = position.get("position_id", "unknown")
        inferred.append({
            "trade_id": f"position-fallback:{position_id}:close",
            "position_id": position_id,
            "market_id": position.get("market_id", ""),
            "question": position.get("question", ""),
            "side": position.get("side", ""),
            "action": "CLOSE",
            "price": position.get("current_price", 0.0),
            "size_usdc": position.get("size_usdc", 0.0),
            "shares": position.get("shares", 0.0),
            "pnl": position.get("pnl", 0.0),
            "timestamp": position.get("last_update_time", position.get("entry_time", 0.0)),
            "signals": position.get("signals", []),
            "source": "position_fallback",
            "inferred": True,
        })
    return inferred[:limit]


def overlay_paper_status(base_status: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """Overlay persisted safety and portfolio fields on a bot status payload."""
    summary = summarize_paper_state(state)
    status = dict(base_status)
    status["positions"] = {
        "active": summary["active_positions"],
        "resolved": summary["resolved_positions"],
        "total": summary["total_positions"],
    }

    performance = dict(status.get("performance") or {})
    resolved = persisted_positions(state)
    resolved = [position for position in resolved if is_resolved_position(position)]
    winning_trades = summary["winning_trades"]
    performance.update({
        "total_pnl": summary["total_pnl"],
        "total_trades": summary["total_trades"],
        "winning_trades": winning_trades,
        "win_rate_pct": round((winning_trades / len(resolved) * 100), 1) if resolved else 0,
        "active_positions": summary["active_positions"],
        "opportunities_found": state.get("opportunities_found", 0),
    })
    status["performance"] = performance

    alpha = dict(status.get("alpha") or {})
    bankroll = dict(alpha.get("bankroll") or {})
    bankroll.update({
        "current": summary["bankroll"],
        "peak": summary["peak_bankroll"],
    })
    alpha["bankroll"] = bankroll
    status["alpha"] = alpha
    status["kill_switch"] = {
        "active": summary["kill_switch_active"],
        "reason": summary["kill_reason"],
        "daily_pnl": state.get("daily_pnl", 0.0),
        "consecutive_losses": state.get("consecutive_losses", 0),
        "api_failures": state.get("api_failure_count", 0),
    }
    status["state_source"] = "redis"
    return status


def overlay_paper_performance(base_performance: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """Overlay persisted portfolio values on a paper-performance payload."""
    positions = persisted_positions(state)
    active = [position for position in positions if not is_resolved_position(position)]
    resolved = [position for position in positions if is_resolved_position(position)]
    realized_pnl = sum((position.get("pnl", 0) or 0) for position in resolved)
    unrealized_pnl = sum((position.get("pnl", 0) or 0) for position in active)
    summary = summarize_paper_state(state)
    winning_trades = summary["winning_trades"]
    performance = dict(base_performance)
    performance.update({
        "total_pnl": summary["total_pnl"],
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "total_trades": summary["total_trades"],
        "winning_trades": winning_trades,
        "losing_trades": len(resolved) - winning_trades,
        "active_positions": len(active),
        "bankroll": {
            "current": summary["bankroll"],
            "peak": summary["peak_bankroll"],
            "drawdown_pct": round(
                (1 - summary["bankroll"] / summary["peak_bankroll"]) * 100,
                1,
            ) if summary["peak_bankroll"] else 0,
        },
        "kill_switch": {
            "active": state.get("kill_switch_active", False),
            "reason": state.get("kill_reason", ""),
            "daily_pnl": state.get("daily_pnl", 0.0),
            "consecutive_losses": state.get("consecutive_losses", 0),
            "api_failures": state.get("api_failure_count", 0),
        },
        "state_source": "redis",
    })
    return performance
