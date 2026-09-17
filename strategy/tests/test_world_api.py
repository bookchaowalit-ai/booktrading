import json

import httpx
import pytest
from fastapi import FastAPI

import infrastructure.api.app as api_module


def _world_response() -> bytes:
    return json.dumps(
        {
            "events": [
                {
                    "ticker": "BTC15M",
                    "title": "BTC direction in 15 minutes",
                    "markets": [
                        {
                            "ticker": "BTC15M-UP",
                            "question": "Will BTC be up at settlement?",
                            "status": "active",
                            "yes_bid": 0.42,
                            "yes_ask": 0.44,
                            "no_bid": 0.48,
                            "no_ask": 0.50,
                            "yes_ask_size": 2,
                            "no_ask_size": 3,
                            "volume": 5_000,
                            "liquidity": 2_000,
                            "strikeDate": "2026-09-12T12:00:00Z",
                            "resolutionSource": "provider_rulebook",
                        }
                    ],
                }
            ]
        },
        separators=(",", ":"),
    ).encode()


def _api(tmp_path, monkeypatch) -> FastAPI:
    app = FastAPI()
    app.state.config = {"world_markets_landing_uri": str(tmp_path / "lake")}
    monkeypatch.setattr(api_module, "API_TOKEN", "world-api-test-token")
    api_module.register_routes(app)
    return app


@pytest.mark.asyncio
async def test_world_import_api_lands_raw_body_and_returns_paper_contract(tmp_path, monkeypatch):
    app = _api(tmp_path, monkeypatch)
    raw = _world_response()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/world/import?received_at=2026-09-12T10:00:00Z",
            content=raw,
            headers={"Authorization": "Bearer world-api-test-token", "Content-Type": "application/json"},
        )

    assert response.status_code == 200, response.text
    report = response.json()
    assert report["mode"] == "api_json_paper_import"
    assert report["execution_enabled"] is False
    assert report["markets_scanned"] == 1
    assert report["signals"][0]["ticker"] == "BTC15M-UP"
    assert report["landing"]["status"] == "written"
    assert (tmp_path / "lake" / report["landing"]["raw_key"]).read_bytes() == raw


@pytest.mark.asyncio
async def test_world_import_api_requires_auth_before_writing(tmp_path, monkeypatch):
    app = _api(tmp_path, monkeypatch)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/world/import", content=_world_response())

    assert response.status_code == 401
    assert not (tmp_path / "lake").exists()


@pytest.mark.asyncio
async def test_world_status_api_exposes_paper_contract(tmp_path, monkeypatch):
    app = _api(tmp_path, monkeypatch)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/world/status",
            headers={"Authorization": "Bearer world-api-test-token"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "source": "world_xyz",
        "mode": "read_only_paper",
        "execution_enabled": False,
        "lake_configured": True,
        "import_endpoint": "/api/v1/world/import",
    }


@pytest.mark.asyncio
async def test_world_import_api_rejects_invalid_json_before_landing(tmp_path, monkeypatch):
    app = _api(tmp_path, monkeypatch)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/world/import",
            content=b"{not-json",
            headers={"Authorization": "Bearer world-api-test-token", "Content-Type": "application/json"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "World JSON payload is invalid JSON"
    assert not (tmp_path / "lake").exists()


@pytest.mark.asyncio
async def test_world_api_requires_configured_backend_token(tmp_path, monkeypatch):
    app = FastAPI()
    app.state.config = {"world_markets_landing_uri": str(tmp_path / "lake")}
    monkeypatch.setattr(api_module, "API_TOKEN", None)
    api_module.register_routes(app)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/world/status",
            headers={"Authorization": "Bearer any-token"},
        )

    assert response.status_code == 401
