"""The service token reaches the Go backend and nothing else."""

import httpx
import pytest

from app.backend_auth import backend_auth_headers, backend_event_hooks, is_backend_url


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("AUTH_TOKEN", "svc-token")
    monkeypatch.setenv("BACKEND_API_BASE", "http://backend:8080")
    monkeypatch.setenv("PAPER_API_BASE", "http://paper:8080/")


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://backend:8080/api/trade/order", True),
        ("http://backend:8080", True),
        ("http://paper:8080/api/paper/order", True),
        ("http://backend:8080.evil.test/api/trade/order", False),
        ("http://backend:80800/api", False),
        ("https://api.binance.th/api/v1/ticker/price", False),
        ("http://backend/api/trade/order", False),
    ],
)
def test_is_backend_url(url, expected):
    assert is_backend_url(url) is expected


def test_headers_only_for_backend(monkeypatch):
    assert backend_auth_headers("http://backend:8080/api/trade/balances") == {"Authorization": "Bearer svc-token"}
    assert backend_auth_headers("https://api.binance.th/api/v3/ticker") == {}
    monkeypatch.setenv("AUTH_TOKEN", "  ")
    assert backend_auth_headers("http://backend:8080/api/trade/balances") == {}


@pytest.mark.asyncio
async def test_event_hook_attaches_token_to_backend_requests_only():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen[request.url.host] = request.headers.get("Authorization")
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), event_hooks=backend_event_hooks()) as client:
        await client.get("http://backend:8080/api/trade/balances")
        await client.get("https://api.binance.th/api/v1/ticker/price")
        await client.get("http://paper:8080/api/paper/orders", headers={"Authorization": "Bearer caller"})

    assert seen == {"backend": "Bearer svc-token", "api.binance.th": None, "paper": "Bearer caller"}
