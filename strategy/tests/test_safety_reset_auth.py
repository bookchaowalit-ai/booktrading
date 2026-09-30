"""Safety-control resets must not be callable anonymously.

The Polymarket kill switch and brain circuit breaker are capital-protection
controls, so their reset endpoints fail closed: they need a configured
AUTH_TOKEN and a matching bearer token, even in dev mode.
"""

import httpx
import pytest
from fastapi import FastAPI

import infrastructure.api.app as api_module


class _FakeBot:
    def __init__(self):
        self.resets = 0

    def reset_kill_switch(self):
        self.resets += 1

    def reset(self):
        self.resets += 1


def _api(monkeypatch, token):
    app = FastAPI()
    app.state.config = {}
    monkeypatch.setattr(api_module, "API_TOKEN", token)
    api_module.register_routes(app)
    return app


@pytest.fixture
def fake_poly_bot(monkeypatch):
    import app.polymarket.paper_bot as paper_bot

    bot = _FakeBot()
    monkeypatch.setattr(paper_bot, "get_poly_paper_bot", lambda: bot)
    return bot


async def _post(app, path, headers=None):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(path, headers=headers or {})


@pytest.mark.asyncio
async def test_kill_switch_reset_rejects_missing_token(monkeypatch, fake_poly_bot):
    app = _api(monkeypatch, "secret-test-token")
    response = await _post(app, "/api/poly-paper/reset-kill-switch")
    assert response.status_code == 401
    assert fake_poly_bot.resets == 0


@pytest.mark.asyncio
async def test_kill_switch_reset_rejects_wrong_token(monkeypatch, fake_poly_bot):
    app = _api(monkeypatch, "secret-test-token")
    response = await _post(app, "/api/poly-paper/reset-kill-switch", {"Authorization": "Bearer nope"})
    assert response.status_code == 401
    assert fake_poly_bot.resets == 0


@pytest.mark.asyncio
async def test_kill_switch_reset_fails_closed_without_configured_token(monkeypatch, fake_poly_bot):
    app = _api(monkeypatch, None)
    response = await _post(app, "/api/poly-paper/reset-kill-switch", {"Authorization": "Bearer anything"})
    assert response.status_code == 401
    assert fake_poly_bot.resets == 0


@pytest.mark.asyncio
async def test_kill_switch_reset_accepts_valid_token(monkeypatch, fake_poly_bot):
    app = _api(monkeypatch, "secret-test-token")
    response = await _post(
        app, "/api/poly-paper/reset-kill-switch", {"Authorization": "Bearer secret-test-token"}
    )
    assert response.status_code == 200, response.text
    assert fake_poly_bot.resets == 1


@pytest.mark.asyncio
async def test_circuit_breaker_reset_requires_token(monkeypatch):
    app = _api(monkeypatch, "secret-test-token")
    response = await _post(app, "/api/brain/reset-cb?symbol=btcusdt")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_arb_paper_reset_requires_token_when_configured(monkeypatch):
    import app.arbitrage_paper_bot as arb

    bot = _FakeBot()
    monkeypatch.setattr(arb, "get_arb_paper_bot", lambda: bot)
    app = _api(monkeypatch, "secret-test-token")

    denied = await _post(app, "/api/arb-paper/reset")
    assert denied.status_code == 401
    allowed = await _post(app, "/api/arb-paper/reset", {"Authorization": "Bearer secret-test-token"})
    assert allowed.status_code == 200, allowed.text
    assert bot.resets == 1


def test_require_auth_compares_tokens(monkeypatch):
    monkeypatch.setattr(api_module, "API_TOKEN", "abc")

    class _Req:
        def __init__(self, value):
            self.headers = {"Authorization": value}

    assert api_module.require_auth(_Req("Bearer abc")) is True
    assert api_module.require_auth(_Req("Bearer abd")) is False
    assert api_module.require_auth(_Req("abc")) is False
