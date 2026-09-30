"""Mutating / expensive routes require the API bearer token.

Airdrop-tracker writes, backtest runs (run/sweep/compare/walk-forward) and
the manual signal evaluation used to be callable anonymously even with
``AUTH_TOKEN`` configured. They now use ``@auth_required`` like the
real-grid kill/enable routes. No network: every backend is faked.
"""

from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

import infrastructure.api.app as api_module

TOKEN = "secret-test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class _Calls(list):
    pass


class _FakeTracker:
    def __init__(self, calls):
        self.calls = calls

    async def add_task(self, **kwargs):
        self.calls.append("add")
        return {"id": "t1", **kwargs}

    async def update_task(self, task_id, updates):
        self.calls.append("update")
        return {"id": task_id, **updates}

    async def update_subtask(self, task_id, subtask_idx, completed):
        self.calls.append("subtask")
        return {"id": task_id}

    async def delete_task(self, task_id):
        self.calls.append("delete")
        return True


class _FakeSignalLogger:
    def __init__(self, calls):
        self.calls = calls

    async def evaluate_signals(self, prices):
        self.calls.append("evaluate")
        return {"evaluated": 0}

    def warning(self, *args, **kwargs):
        pass


@pytest.fixture
def calls(monkeypatch):
    import app.backtester as backtester
    import app.market_intel.airdrop_tracker as airdrop_tracker
    import app.market_intel.signal_logger as signal_logger

    recorded = _Calls()

    def stub(name):
        def _stub(*args, **kwargs):
            recorded.append(name)
            raise RuntimeError("backtest stub: no network in tests")

        return _stub

    monkeypatch.setattr(backtester, "GridBacktester", stub("GridBacktester"))
    monkeypatch.setattr(backtester, "run_parameter_sweep", stub("run_parameter_sweep"))
    monkeypatch.setattr(backtester, "run_walk_forward_tuning", stub("run_walk_forward_tuning"))
    monkeypatch.setattr(airdrop_tracker, "get_airdrop_tracker", lambda **kw: _FakeTracker(recorded))
    monkeypatch.setattr(signal_logger, "get_signal_logger", lambda **kw: _FakeSignalLogger(recorded))
    return recorded


def _api(monkeypatch, token=TOKEN):
    app = FastAPI()
    app.state.config = {}
    monkeypatch.setattr(api_module, "API_TOKEN", token)
    api_module.register_routes(app)
    return app


ROUTES = [
    ("POST", "/api/airdrop-tracker/tasks", {"name": "Drop"}),
    ("PATCH", "/api/airdrop-tracker/tasks/t1", {"status": "done"}),
    ("PATCH", "/api/airdrop-tracker/tasks/t1/subtasks/0", {"completed": True}),
    ("DELETE", "/api/airdrop-tracker/tasks/t1", None),
    ("POST", "/api/backtest/run", {"symbol": "BTCTHB"}),
    ("POST", "/api/backtest/sweep", {"symbol": "BTCTHB"}),
    ("POST", "/api/backtest/compare", {"symbol": "BTCTHB"}),
    ("POST", "/api/backtest/walk-forward", {"symbol": "BTCTHB"}),
    ("POST", "/api/signal-tracker/evaluate", None),
]


async def _call(app, method, path, body, headers=None):
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, json=body, headers=headers or {})


@pytest.fixture
def no_price_network(monkeypatch):
    """signal-tracker/evaluate fetches prices with httpx; answer locally."""
    real_client = httpx.AsyncClient

    def offline_client(*args, **kwargs):
        if "transport" not in kwargs:
            kwargs["transport"] = httpx.MockTransport(lambda request: httpx.Response(503))
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", offline_client)


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
@pytest.mark.parametrize("headers", [None, {"Authorization": "Bearer wrong"}, {"Authorization": TOKEN}])
async def test_anonymous_or_wrong_token_is_rejected(monkeypatch, calls, no_price_network, method, path, body, headers):
    app = _api(monkeypatch)
    response = await _call(app, method, path, body, headers)
    assert response.status_code == 401
    assert calls == []  # nothing ran


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
async def test_valid_token_reaches_the_handler(monkeypatch, calls, no_price_network, method, path, body):
    app = _api(monkeypatch)
    response = await _call(app, method, path, body, AUTH)
    assert response.status_code != 401, response.text
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_airdrop_add_with_token_succeeds(monkeypatch, calls):
    app = _api(monkeypatch)
    response = await _call(app, "POST", "/api/airdrop-tracker/tasks", {"name": "Drop"}, AUTH)
    assert response.status_code == 200, response.text
    assert response.json()["task"]["id"] == "t1"


@pytest.mark.asyncio
async def test_backtest_body_is_still_read_from_json(monkeypatch):
    import app.backtester as backtester

    seen = {}

    async def fake_sweep(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(
            symbol=kwargs["symbol"],
            days=kwargs["days"],
            interval=kwargs["interval"],
            volatility_mode=kwargs["volatility_mode"],
            results=[],
            best_config=None,
            worst_config=None,
        )

    monkeypatch.setattr(backtester, "run_parameter_sweep", fake_sweep)
    app = _api(monkeypatch)
    response = await _call(app, "POST", "/api/backtest/sweep", {"symbol": "ETHTHB", "days": 7}, AUTH)
    assert response.status_code == 200, response.text
    assert seen["symbol"] == "ETHTHB"
    assert seen["days"] == 7


@pytest.mark.asyncio
async def test_production_without_token_fails_closed(monkeypatch, calls):
    monkeypatch.setenv("ENVIRONMENT", "production")
    app = _api(monkeypatch, token=None)
    response = await _call(app, "DELETE", "/api/airdrop-tracker/tasks/t1", None)
    assert response.status_code == 401
    assert calls == []
