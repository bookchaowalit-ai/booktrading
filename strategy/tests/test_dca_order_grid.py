"""DCA sell orders must respect the exchange step/tick grid (no network)."""

import asyncio

import app.dca_bot as dca
from app.dca_bot import DCABot, DCAConfig, DCAState, _floor_to_step


class _Resp:
    status_code = 201

    def json(self):
        return {"order": {}}


class _FakeHTTP:
    def __init__(self):
        self.posts = []

    async def post(self, url, json=None):
        self.posts.append(json)
        return _Resp()


def _bot(balances):
    bot = DCABot()
    bot._http = _FakeHTTP()

    async def fetch_balances():
        return balances

    bot._fetch_balances = fetch_balances
    return bot


def test_floor_to_step_is_exact():
    assert _floor_to_step(0.0012345678, 0.00001) == 0.00123
    assert _floor_to_step(0.3, 0.1) == 0.3  # float 0.3/0.1 = 2.9999999999999996
    assert _floor_to_step(1234567.89, 1.0) == 1234567.0
    assert _floor_to_step(5.0, 0) == 5.0


def test_sell_quantity_and_price_are_on_the_grid(monkeypatch):
    monkeypatch.setattr(dca, "BINANCE_TH_MAINNET", True)
    cfg = DCAConfig(symbol="BTCTHB", step_size=0.00001, tick_size=0.01)
    bot = _bot({"BTC": 1.0})
    asyncio.run(bot._execute_sell(cfg, DCAState(symbol="BTCTHB"), 2_000_000.123456, 0.0012345678, "T"))
    [order] = bot._http.posts
    assert order["quantity"] == 0.00123
    assert order["price"] == 2_000_000.12


def test_short_balance_sell_never_exceeds_holdings(monkeypatch):
    monkeypatch.setattr(dca, "BINANCE_TH_MAINNET", True)
    cfg = DCAConfig(symbol="ETHTHB", step_size=0.0001, tick_size=1.0)
    bot = _bot({"ETH": 0.123456789})
    asyncio.run(bot._execute_sell(cfg, DCAState(symbol="ETHTHB"), 100_000.0, 1.0, "T"))
    [order] = bot._http.posts
    assert order["quantity"] == 0.1172  # floor(0.95 * 0.123456789, 0.0001)
    assert order["quantity"] <= 0.123456789


def test_sell_below_min_notional_after_rounding_is_skipped(monkeypatch):
    monkeypatch.setattr(dca, "BINANCE_TH_MAINNET", True)
    cfg = DCAConfig(symbol="BTCTHB", step_size=0.00001, tick_size=0.01, min_notional_thb=100.0)
    bot = _bot({"BTC": 1.0})
    # 0.0000999 BTC * 1,050,000 = 104.9 THB raw, but it floors to 0.00009 BTC
    # = 94.5 THB, which the exchange would reject as below min notional.
    asyncio.run(bot._execute_sell(cfg, DCAState(symbol="BTCTHB"), 1_050_000.0, 0.0000999, "T"))
    assert bot._http.posts == []
