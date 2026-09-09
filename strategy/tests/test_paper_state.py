"""Regression tests for the canonical persisted paper-bot state view."""

from app.polymarket.state import (
    is_resolved_position,
    overlay_paper_performance,
    overlay_paper_status,
    persisted_positions,
    persisted_trades,
    summarize_paper_state,
)


def test_resolved_position_supports_current_and_legacy_shapes():
    assert is_resolved_position({"resolved": True})
    assert is_resolved_position({"status": "closed"})
    assert not is_resolved_position({"resolved": False, "status": "open"})


def test_summary_matches_monitor_safety_fields():
    state = {
        "positions": {
            "active": {"resolved": False},
            "closed": {"status": "resolved"},
        },
        "kill_switch_active": True,
        "kill_reason": "max drawdown",
        "winning_trades": 0,
        "bankroll": 84.54,
        "peak_bankroll": 100.0,
        "total_pnl": -8.40,
        "total_trades": 20,
    }

    assert summarize_paper_state(state) == {
        "active_positions": 1,
        "resolved_positions": 1,
        "total_positions": 2,
        "kill_switch_active": True,
        "kill_reason": "max drawdown",
        "winning_trades": 0,
        "bankroll": 84.54,
        "peak_bankroll": 100.0,
        "total_pnl": -8.40,
        "total_trades": 20,
    }


def test_status_and_performance_overlay_use_persisted_values():
    state = {
        "positions": {
            "active": {"resolved": False, "entry_time": 2},
            "closed": {"resolved": True, "entry_time": 1, "pnl": -5.0},
        },
        "kill_switch_active": True,
        "kill_reason": "drawdown",
        "bankroll": 84.54,
        "peak_bankroll": 100.0,
        "total_pnl": -5.0,
        "total_trades": 1,
        "winning_trades": 0,
    }

    status = overlay_paper_status(
        {"positions": {}, "performance": {}, "alpha": {}},
        state,
    )
    performance = overlay_paper_performance({}, state)

    assert [p["entry_time"] for p in persisted_positions(state)] == [2, 1]
    assert status["positions"] == {"active": 1, "resolved": 1, "total": 2}
    assert status["performance"]["total_pnl"] == -5.0
    assert status["alpha"]["bankroll"]["current"] == 84.54
    assert status["kill_switch"]["active"] is True
    assert performance["active_positions"] == 1
    assert performance["realized_pnl"] == -5.0


def test_trade_fallback_is_explicitly_inferred_from_resolved_positions():
    state = {
        "positions": {
            "closed": {
                "position_id": "p-1",
                "resolved": True,
                "market_id": "m-1",
                "question": "Will X happen?",
                "side": "YES",
                "current_price": 0.4,
                "size_usdc": 5.0,
                "shares": 10.0,
                "pnl": -5.0,
                "last_update_time": 123.0,
            },
        },
        "trades": [],
    }

    trades = persisted_trades(state)

    assert len(trades) == 1
    assert trades[0]["action"] == "CLOSE"
    assert trades[0]["source"] == "position_fallback"
    assert trades[0]["inferred"] is True
