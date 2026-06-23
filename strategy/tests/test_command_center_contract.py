"""
Contract tests for /api/command-center endpoint.

These tests hit the live running strategy API inside the container.
Run with: docker compose exec strategy python -m pytest tests/test_command_center_contract.py -v

Validates:
1. Response shape — all required top-level keys present
2. Kill switch invariant — if active, decision must NOT allow trading
3. Gate invariant — if gates incomplete, next_trigger must reference evidence/gates
4. Decision is one of the valid enum values
5. Nested structures have expected fields
"""
import os

import httpx
import pytest

STRATEGY_API_URL = os.environ.get('STRATEGY_API_URL', 'http://strategy:8000')


@pytest.fixture
def command_center():
    resp = httpx.get(f'{STRATEGY_API_URL}/api/command-center', timeout=10.0)
    assert resp.status_code == 200, f'Expected 200, got {resp.status_code}: {resp.text}'
    return resp.json()


# ── Shape contract ─────────────────────────────────────────────────────────────

class TestCommandCenterShape:
    """Response must always contain these top-level keys with correct types."""

    def test_has_current_decision(self, command_center):
        assert 'current_decision' in command_center
        assert isinstance(command_center['current_decision'], str)

    def test_has_next_trigger(self, command_center):
        assert 'next_trigger' in command_center
        assert isinstance(command_center['next_trigger'], str)

    def test_has_kill_switch(self, command_center):
        assert 'kill_switch' in command_center
        ks = command_center['kill_switch']
        assert 'active' in ks
        assert isinstance(ks['active'], bool)

    def test_has_positions(self, command_center):
        assert 'positions' in command_center
        pos = command_center['positions']
        assert 'active' in pos
        assert isinstance(pos['active'], int)

    def test_has_evidence_gates(self, command_center):
        assert 'evidence' in command_center
        ev = command_center['evidence']
        assert 'gates_ready' in ev
        assert 'gates_total' in ev
        assert isinstance(ev['gates_ready'], int)
        assert isinstance(ev['gates_total'], int)
        assert ev['gates_total'] >= ev['gates_ready']

    def test_has_system_health(self, command_center):
        assert 'system_health' in command_center
        sh = command_center['system_health']
        assert 'strategy_api' in sh
        assert 'redis_connected' in sh
        assert isinstance(sh['redis_connected'], bool)

    def test_has_timestamp(self, command_center):
        assert 'timestamp' in command_center
        assert isinstance(command_center['timestamp'], str)


# ── Decision validity ──────────────────────────────────────────────────────────

VALID_DECISIONS = {'WAIT', 'REVIEW_SIGNALS', 'ENABLE_DRY_RUN', 'MONITOR'}


class TestDecisionContract:
    """Decision must be a valid enum value and respect safety invariants."""

    def test_decision_is_valid_enum(self, command_center):
        assert command_center['current_decision'] in VALID_DECISIONS

    def test_kill_switch_active_means_wait(self, command_center):
        """If kill switch is active, decision MUST be WAIT — never trade."""
        if command_center['kill_switch']['active']:
            assert command_center['current_decision'] == 'WAIT', (
                f"Kill switch ACTIVE but decision is {command_center['current_decision']}. "
                "Must be WAIT."
            )

    def test_incomplete_gates_no_trade_signal(self, command_center):
        """If gates not all ready, next_trigger must reference gates/evidence, not trading."""
        ev = command_center['evidence']
        if ev['gates_ready'] < ev['gates_total']:
            trigger = command_center['next_trigger'].lower()
            trade_words = {'start trading', 'enable live', 'go live', 'begin trading'}
            assert not any(w in trigger for w in trade_words), (
                f"Gates incomplete ({ev['gates_ready']}/{ev['gates_total']}) "
                f"but next_trigger says '{command_center['next_trigger']}'. "
                "Should reference gates/evidence."
            )

    def test_wait_decision_no_trade_signal(self, command_center):
        """If decision is WAIT, next_trigger must not suggest trading."""
        if command_center['current_decision'] == 'WAIT':
            trigger = command_center['next_trigger'].lower()
            assert 'start trading' not in trigger
            assert 'enable live' not in trigger

    def test_next_trigger_non_empty(self, command_center):
        assert len(command_center['next_trigger'].strip()) > 0


# ── Nested structure contracts ─────────────────────────────────────────────────

class TestNestedContracts:
    """Sub-objects must have consistent structure."""

    def test_grid_structure(self, command_center):
        grid = command_center['grid']
        assert 'running' in grid
        assert isinstance(grid['running'], bool)

    def test_research_structure(self, command_center):
        research = command_center['research']
        assert 'crypto_pairs' in research
        assert isinstance(research['crypto_pairs'], int)
        assert research['crypto_pairs'] >= 0

    def test_positions_non_negative(self, command_center):
        pos = command_center['positions']
        assert pos['active'] >= 0
        assert pos['resolved'] >= 0

    def test_evidence_gates_non_negative(self, command_center):
        ev = command_center['evidence']
        assert ev['gates_ready'] >= 0
        assert ev['gates_total'] >= 0
