"""Route access matrix for the strategy API (FastAPI).

Every route create_app() serves must be listed in EXPECTED with its
access level, so a new route fails CI until someone classifies it:

- PUBLIC: no credentials. Reads only; a public write fails this test.
- SERVICE: Authorization: Bearer  (@auth_required).
  Browsers never hold that token: they reach these routes through the Go
  backend /strategy-api proxy, which checks the session (writes need an
  admin) and forwards with the service token.
- STRICT: like SERVICE, and also refused when AUTH_TOKEN is unset
  (no dev-mode allow-all) because it clears a safety control or reads lake
  configuration.

Protected routes are exercised over ASGI with no token, a wrong token and a
non-Bearer token; each must answer 401. No network: outbound httpx is mocked.
"""

import httpx
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute

import infrastructure.api.app as api_module

PUBLIC = "public"
SERVICE = "service"
STRICT = "strict"
TOKEN = "matrix-service-token"
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
PATH_PARAMS = {"symbol": "BTCTHB", "task_id": "t1", "subtask_idx": "0", "token_id": "1"}

EXPECTED = {
    ("GET", "/api/health"): PUBLIC,
    ("GET", "/api/v1/world/status"): STRICT,
    ("POST", "/api/v1/world/import"): SERVICE,
    ("GET", "/api/indicators"): PUBLIC,
    ("GET", "/api/indicators/{symbol}"): PUBLIC,
    ("GET", "/api/strategy/config"): SERVICE,
    ("POST", "/api/strategy/config"): SERVICE,
    ("POST", "/api/strategy/reset"): SERVICE,
    ("GET", "/api/signals"): SERVICE,
    ("GET", "/api/strategies"): SERVICE,
    ("POST", "/api/backtest"): SERVICE,
    ("POST", "/api/ai/predict"): SERVICE,
    ("GET", "/api/ai/recommend"): SERVICE,
    ("POST", "/api/ai/anomalies"): SERVICE,
    ("POST", "/api/ai/optimize"): SERVICE,
    ("GET", "/api/ai/dashboard"): SERVICE,
    ("GET", "/api/grid/status"): PUBLIC,
    ("GET", "/api/real-grid/status"): PUBLIC,
    ("GET", "/api/real-grid/preflight"): PUBLIC,
    ("POST", "/api/real-grid/kill"): SERVICE,
    ("POST", "/api/real-grid/enable"): SERVICE,
    ("GET", "/api/real-grid/notifications"): PUBLIC,
    ("GET", "/api/real-grid/health"): PUBLIC,
    ("POST", "/api/real-grid/restart"): SERVICE,
    ("GET", "/api/real-grid/config/{symbol}"): PUBLIC,
    ("PUT", "/api/real-grid/config/{symbol}"): SERVICE,
    ("GET", "/api/real-grid/performance"): PUBLIC,
    ("GET", "/api/risk/status"): PUBLIC,
    ("POST", "/api/risk/reset"): SERVICE,
    ("GET", "/api/brain/status"): PUBLIC,
    ("GET", "/api/brain/directive/{symbol}"): PUBLIC,
    ("POST", "/api/brain/refresh"): SERVICE,
    ("POST", "/api/brain/reset-cb"): STRICT,
    ("GET", "/api/journal/entries"): PUBLIC,
    ("GET", "/api/journal/stats"): PUBLIC,
    ("GET", "/api/report/daily"): PUBLIC,
    ("POST", "/api/backtest/run"): SERVICE,
    ("POST", "/api/backtest/sweep"): SERVICE,
    ("POST", "/api/backtest/compare"): SERVICE,
    ("POST", "/api/backtest/walk-forward"): SERVICE,
    ("GET", "/api/polymarket/events"): PUBLIC,
    ("GET", "/api/polymarket/markets"): PUBLIC,
    ("GET", "/api/polymarket/search"): PUBLIC,
    ("GET", "/api/polymarket/opportunities"): PUBLIC,
    ("GET", "/api/poly-paper/status"): PUBLIC,
    ("GET", "/api/poly-paper/positions"): PUBLIC,
    ("GET", "/api/poly-paper/trades"): PUBLIC,
    ("GET", "/api/poly-paper/performance"): PUBLIC,
    ("GET", "/api/poly-paper/notifications"): PUBLIC,
    ("GET", "/api/poly-paper/signals"): PUBLIC,
    ("POST", "/api/poly-paper/reset-kill-switch"): STRICT,
    ("GET", "/api/arb-paper/status"): PUBLIC,
    ("POST", "/api/arb-paper/reset"): SERVICE,
    ("GET", "/api/dca/status"): PUBLIC,
    ("GET", "/api/trend/status"): PUBLIC,
    ("GET", "/api/futures/status"): SERVICE,
    ("GET", "/api/futures/preflight"): SERVICE,
    ("GET", "/api/polymarket/summary"): PUBLIC,
    ("GET", "/api/polymarket/tags"): PUBLIC,
    ("GET", "/api/polymarket/orderbook/{token_id}"): PUBLIC,
    ("GET", "/api/polymarket/price-history/{token_id}"): PUBLIC,
    ("GET", "/api/market-intel/scan"): PUBLIC,
    ("GET", "/api/market-intel/quotes"): PUBLIC,
    ("GET", "/api/market-intel/overview"): PUBLIC,
    ("GET", "/api/market-intel/sources"): PUBLIC,
    ("GET", "/api/market-intel/alerts"): PUBLIC,
    ("GET", "/api/market-intel/last-scan"): PUBLIC,
    ("GET", "/api/market-intel/onchain/status"): PUBLIC,
    ("GET", "/api/market-intel/portfolio"): PUBLIC,
    ("GET", "/api/airdrop-tracker/tasks"): PUBLIC,
    ("POST", "/api/airdrop-tracker/tasks"): SERVICE,
    ("PATCH", "/api/airdrop-tracker/tasks/{task_id}"): SERVICE,
    ("PATCH", "/api/airdrop-tracker/tasks/{task_id}/subtasks/{subtask_idx}"): SERVICE,
    ("DELETE", "/api/airdrop-tracker/tasks/{task_id}"): SERVICE,
    ("GET", "/api/airdrop-tracker/stats"): PUBLIC,
    ("GET", "/api/signal-tracker/signals"): PUBLIC,
    ("GET", "/api/signal-tracker/stats"): PUBLIC,
    ("POST", "/api/signal-tracker/evaluate"): SERVICE,
    ("GET", "/api/evidence"): PUBLIC,
    ("GET", "/api/research"): PUBLIC,
    ("GET", "/api/command-center"): PUBLIC,
}


def _served_routes(app: FastAPI) -> set[tuple[str, str]]:
    served = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            served.add((method, route.path))
    return served


class _NoRateLimit:
    def allow(self, key):
        return True


@pytest.fixture(autouse=True)
def no_rate_limit(monkeypatch):
    monkeypatch.setattr(api_module, "rate_limiter", _NoRateLimit())


@pytest.fixture
def app(monkeypatch):
    # create_app() reads AUTH_TOKEN into api_module.API_TOKEN.
    monkeypatch.setenv("AUTH_TOKEN", TOKEN)
    monkeypatch.setattr(api_module, "API_TOKEN", None)
    return api_module.create_app({})


@pytest.fixture
def no_network(monkeypatch):
    real_client = httpx.AsyncClient

    def offline_client(*args, **kwargs):
        if "transport" not in kwargs:
            kwargs["transport"] = httpx.MockTransport(lambda request: httpx.Response(503))
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", offline_client)


def test_every_served_route_is_classified(app):
    served = _served_routes(app)
    assert len(served) >= 70, "route enumeration broke"
    unclassified = sorted(served - EXPECTED.keys())
    stale = sorted(EXPECTED.keys() - served)
    assert not unclassified, f"classify these routes in EXPECTED: {unclassified}"
    assert not stale, f"EXPECTED lists routes the app no longer serves: {stale}"


def test_no_write_route_is_public():
    public_writes = sorted(k for k, level in EXPECTED.items() if k[0] in WRITE_METHODS and level == PUBLIC)
    assert not public_writes, f"state-changing routes must require the service token: {public_writes}"


def _concrete(path: str) -> str:
    for name, value in PATH_PARAMS.items():
        path = path.replace("{" + name + "}", value)
    assert "{" not in path, f"add a sample value for {path} to PATH_PARAMS"
    return path


async def _call(app, method, path, headers=None):
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        body = {} if method in WRITE_METHODS else None
        return await client.request(method, _concrete(path), json=body, headers=headers or {})


PROTECTED = sorted(k for k, level in EXPECTED.items() if level != PUBLIC)
STRICT_ROUTES = sorted(k for k, level in EXPECTED.items() if level == STRICT)


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "path"), PROTECTED)
@pytest.mark.parametrize(
    "headers",
    [None, {"Authorization": "Bearer wrong"}, {"Authorization": TOKEN}],
    ids=["anonymous", "wrong-token", "not-bearer"],
)
async def test_protected_routes_reject_missing_or_wrong_token(app, no_network, method, path, headers):
    response = await _call(app, method, path, headers)
    assert response.status_code == 401, f"{method} {path}: {response.status_code} {response.text[:200]}"


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "path"), STRICT_ROUTES)
async def test_strict_routes_fail_closed_without_configured_token(monkeypatch, no_network, method, path):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("AUTH_TOKEN", raising=False)
    monkeypatch.setattr(api_module, "API_TOKEN", None)
    app = api_module.create_app({})
    assert api_module.API_TOKEN is None
    response = await _call(app, method, path)
    assert response.status_code == 401, f"{method} {path}: {response.status_code}"


@pytest.mark.asyncio
async def test_real_grid_config_put_reads_json_body(app, monkeypatch):
    """The body used to be named ``request``, so every call failed with 500."""
    import app.real_grid_bot as real_grid_bot

    seen = {}

    class _Bot:
        def update_config(self, symbol, **kwargs):
            seen.update(symbol=symbol, **kwargs)
            return True

    monkeypatch.setattr(real_grid_bot, "get_real_grid_bot", lambda: _Bot())
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            "/api/real-grid/config/btcthb",
            json={"grid_levels": 3},
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
    assert response.status_code == 200, response.text
    assert seen == {"symbol": "BTCTHB", "grid_levels": 3}
