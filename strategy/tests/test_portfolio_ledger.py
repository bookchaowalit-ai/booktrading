from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.portfolio.ledger import LedgerConflictError, PaperPortfolioLedger
from app.portfolio.models import PaperCapitalAccount, PaperTrade, RewardEntry

AS_OF = datetime(2026, 9, 12, 1, 0, tzinfo=UTC)


def test_ledger_separates_realized_and_unrealized_paper_pnl_from_rewards():
    ledger = PaperPortfolioLedger()
    closed = PaperTrade(
        trade_id="closed-1",
        platform_id="world_xyz",
        symbol="WORLD-YES",
        side="buy",
        quantity=10,
        entry_price=0.4,
        exit_price=0.5,
        fee=0.02,
        slippage=0.01,
        status="closed",
        opened_at=datetime(2026, 9, 12, 0, 0, tzinfo=UTC),
        closed_at=datetime(2026, 9, 12, 0, 15, tzinfo=UTC),
    )
    open_trade = PaperTrade(
        trade_id="open-1",
        platform_id="binance_global",
        symbol="BTC-USDT",
        side="buy",
        quantity=2,
        entry_price=100,
        fee=0.5,
        slippage=0.1,
        opened_at=datetime(2026, 9, 12, 0, 5, tzinfo=UTC),
    )
    pending = RewardEntry(
        reward_id="pending-1",
        platform_id="airdrop_rewards",
        program="Points",
        kind="points",
        status="eligible",
        estimated_value=25,
        cost=1,
        created_at=datetime(2026, 9, 12, 0, 6, tzinfo=UTC),
        updated_at=datetime(2026, 9, 12, 0, 7, tzinfo=UTC),
    )
    claimed = RewardEntry(
        reward_id="claimed-1",
        platform_id="airdrop_rewards",
        program="Rebate",
        kind="rebate",
        status="claimed",
        estimated_value=12.5,
        realized_value=12.5,
        cost=0.5,
        created_at=datetime(2026, 9, 12, 0, 8, tzinfo=UTC),
        updated_at=datetime(2026, 9, 12, 0, 10, tzinfo=UTC),
    )

    ledger.record_trade(closed)
    ledger.record_trade(open_trade)
    ledger.record_reward(pending)
    ledger.record_reward(claimed)
    snapshot = ledger.snapshot(as_of=AS_OF, marks={"binance_global:BTC-USDT": 102})

    assert closed.account_scope == "paper-world_xyz"
    assert open_trade.account_scope == "paper-binance_global"
    assert pending.account_scope == "rewards-airdrop_rewards"
    assert snapshot.paper_realized_pnl == pytest.approx(0.97)
    assert snapshot.paper_unrealized_pnl == pytest.approx(3.4)
    assert snapshot.rewards_realized_net == pytest.approx(12.0)
    assert snapshot.rewards_pending_estimate == pytest.approx(25.0)
    assert snapshot.total_costs == pytest.approx(2.13)
    assert snapshot.open_trade_count == 1
    assert snapshot.closed_trade_count == 1
    assert snapshot.reward_count == 2
    assert snapshot.reporting_currency == "USD"
    assert snapshot.by_currency["USD"]["paper_realized_pnl"] == pytest.approx(0.97)
    assert snapshot.by_platform["airdrop_rewards"]["USD"]["reward_count"] == 2
    assert snapshot.as_dict()["execution_enabled"] is False
    assert snapshot.as_dict()["rewards"]["pending_estimate"] == 25.0


def test_ledger_is_idempotent_for_identical_ids_and_rejects_conflicts():
    ledger = PaperPortfolioLedger()
    trade = PaperTrade(
        trade_id="same-id",
        platform_id="world_xyz",
        symbol="MARKET",
        side="buy",
        quantity=1,
        entry_price=0.4,
        opened_at=datetime(2026, 9, 12, tzinfo=UTC),
    )

    assert ledger.record_trade(trade) is trade
    assert ledger.record_trade(trade) is trade
    with pytest.raises(LedgerConflictError, match="different data"):
        ledger.record_trade(
            PaperTrade(
                trade_id="same-id",
                platform_id="world_xyz",
                symbol="MARKET",
                side="buy",
                quantity=2,
                entry_price=0.4,
                opened_at=datetime(2026, 9, 12, tzinfo=UTC),
            )
        )


def test_export_events_are_json_compatible_and_sorted_by_event_id():
    ledger = PaperPortfolioLedger()
    ledger.record_reward(
        RewardEntry(
            reward_id="reward-z",
            platform_id="airdrop_rewards",
            program="Z",
            kind="quest",
            status="candidate",
            created_at=datetime(2026, 9, 12, tzinfo=UTC),
            updated_at=datetime(2026, 9, 12, tzinfo=UTC),
        )
    )
    ledger.record_trade(
        PaperTrade(
            trade_id="trade-a",
            platform_id="world_xyz",
            symbol="MARKET",
            side="buy",
            quantity=1,
            entry_price=0.4,
            opened_at=datetime(2026, 9, 12, tzinfo=UTC),
        )
    )

    events = ledger.export_events()

    assert [event["event_id"] for event in events] == ["trade-a", "reward-z"]
    assert events[0]["event_version"] == 1
    assert "execution_enabled" not in events[0]["trade"]


def test_event_models_reject_common_secret_fields_and_wallet_addresses():
    with pytest.raises(ValueError, match="credential or secret fields"):
        PaperTrade(
            trade_id="secret-metadata",
            platform_id="world_xyz",
            symbol="MARKET",
            side="buy",
            quantity=1,
            entry_price=0.4,
            metadata={"api_key": "must-not-be-stored"},
        )

    with pytest.raises(ValueError, match="credential-like assignments"):
        RewardEntry(
            reward_id="secret-notes",
            platform_id="airdrop_rewards",
            program="Program",
            kind="airdrop",
            status="candidate",
            notes="private_key=must-not-be-stored",
        )

    with pytest.raises(ValueError, match="non-address alias"):
        RewardEntry(
            reward_id="address-scope",
            platform_id="airdrop_rewards",
            program="Program",
            kind="airdrop",
            status="candidate",
            wallet_scope="0x1234567890abcdef",
        )


def test_binary_positions_allow_zero_settlement_and_zero_mark_prices():
    trade = PaperTrade(
        trade_id="zero-settlement",
        platform_id="world_xyz",
        symbol="BINARY-YES",
        side="buy",
        quantity=1,
        entry_price=0.4,
        exit_price=0.0,
        status="closed",
        opened_at=datetime(2026, 9, 12, tzinfo=UTC),
        closed_at=datetime(2026, 9, 12, 0, 1, tzinfo=UTC),
    )

    assert trade.gross_pnl == pytest.approx(-0.4)
    assert trade.mark_pnl(0.0) == pytest.approx(-0.4)


def test_snapshot_does_not_mix_currencies_or_project_future_records_backwards():
    ledger = PaperPortfolioLedger()
    future_close = PaperTrade(
        trade_id="future-close",
        platform_id="world_xyz",
        symbol="MARKET",
        side="buy",
        quantity=1,
        entry_price=0.4,
        exit_price=0.8,
        status="closed",
        opened_at=datetime(2026, 9, 12, tzinfo=UTC),
        closed_at=datetime(2026, 9, 12, 2, tzinfo=UTC),
        quote_currency="USD",
    )
    wld_reward = RewardEntry(
        reward_id="wld-reward",
        platform_id="airdrop_rewards",
        program="WLD points",
        kind="points",
        status="eligible",
        estimated_value=10,
        currency="WLD",
        created_at=datetime(2026, 9, 12, 0, 30, tzinfo=UTC),
        updated_at=datetime(2026, 9, 12, 1, 30, tzinfo=UTC),
    )
    ledger.record_trade(future_close)
    ledger.record_reward(wld_reward)

    historical = ledger.snapshot(
        as_of=datetime(2026, 9, 12, 1, tzinfo=UTC),
        marks={"world_xyz:MARKET": 0.5},
    )
    multi_currency = ledger.snapshot()
    usd_view = ledger.snapshot(
        as_of=datetime(2026, 9, 12, 1, tzinfo=UTC),
        reporting_currency="USD",
    )
    usd_full_view = ledger.snapshot(reporting_currency="USD")

    assert historical.closed_trade_count == 0
    assert historical.open_trade_count == 1
    assert historical.paper_realized_pnl == pytest.approx(0.0)
    assert historical.paper_unrealized_pnl == pytest.approx(0.1)
    assert historical.reward_count == 0
    assert set(multi_currency.by_currency) == {"USD", "WLD"}
    assert multi_currency.paper_realized_pnl is None
    assert multi_currency.rewards_pending_estimate is None
    assert multi_currency.total_costs is None
    assert usd_view.reporting_currency == "USD"
    assert usd_view.paper_realized_pnl == pytest.approx(0.0)
    assert usd_view.rewards_pending_estimate == pytest.approx(0.0)
    assert usd_full_view.paper_realized_pnl == pytest.approx(0.4)
    assert usd_full_view.rewards_pending_estimate == pytest.approx(0.0)
    assert usd_full_view.by_currency["WLD"]["rewards_pending_estimate"] == pytest.approx(10.0)


def test_account_scope_updates_paper_capital_and_exports_non_cash_finance_projection():
    ledger = PaperPortfolioLedger()
    ledger.register_account(
        PaperCapitalAccount(
            account_scope="world-paper-usd",
            platform_id="world_xyz",
            currency="USD",
            starting_capital=10.0,
        )
    )
    trade = PaperTrade(
        trade_id="world-loss",
        platform_id="world_xyz",
        symbol="MARKET-YES",
        side="buy",
        quantity=1.0,
        entry_price=0.5,
        exit_price=0.0,
        fee=0.01,
        status="closed",
        opened_at=datetime(2026, 9, 12, tzinfo=UTC),
        closed_at=datetime(2026, 9, 12, 0, 5, tzinfo=UTC),
        account_scope="world-paper-usd",
        source_ref="alpha-journal:request-1",
    )
    ledger.record_trade(trade)

    snapshot = ledger.snapshot()
    capital = snapshot.capital_by_account["world-paper-usd"]
    assert snapshot.by_account["world-paper-usd"]["USD"]["paper_realized_pnl"] == pytest.approx(-0.51)
    assert capital["starting_capital"] == pytest.approx(10.0)
    assert capital["realized_pnl"] == pytest.approx(-0.51)
    assert capital["reserved_risk"] == pytest.approx(0.0)
    assert capital["available_capital"] == pytest.approx(9.49)

    projections = ledger.export_finance_projections()
    assert len(projections) == 1
    assert projections[0]["event_type"] == "paper_finance_projection"
    assert projections[0]["source"] == "booktrading"
    assert projections[0]["projection_id"] == "paper-pnl:world-loss"
    assert projections[0]["signed_amount"] == pytest.approx(-0.51)
    assert projections[0]["cash_effect"] is False
    assert projections[0]["posting_status"] == "separate_paper_lane"


def test_registered_account_cannot_receive_another_platform_or_live_mode():
    ledger = PaperPortfolioLedger()
    ledger.register_account(PaperCapitalAccount("world-paper-usd", "world_xyz", "USD", 10.0))
    with pytest.raises(ValueError, match="activity_mode"):
        PaperTrade(
            trade_id="live-record",
            platform_id="world_xyz",
            symbol="MARKET",
            side="buy",
            quantity=1,
            entry_price=0.4,
            account_scope="world-paper-usd",
            activity_mode="live",
        )
    with pytest.raises(LedgerConflictError, match="does not match"):
        ledger.record_trade(
            PaperTrade(
                trade_id="wrong-platform",
                platform_id="fomo",
                symbol="MARKET",
                side="buy",
                quantity=1,
                entry_price=0.4,
                account_scope="world-paper-usd",
            )
        )
