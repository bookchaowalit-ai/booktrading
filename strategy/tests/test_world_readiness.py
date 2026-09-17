from __future__ import annotations

import httpx
import pytest

from app.world.client import WorldMarketsClient, WorldMarketsConfig
from app.world.landing import WorldLandingWriter
from app.world.readiness import check_world_readiness


def _payload() -> dict:
    return {
        "events": [
            {
                "ticker": "BTC15M",
                "markets": [
                    {
                        "ticker": "BTC15M-UP",
                        "question": "Will BTC be up at settlement?",
                        "status": "active",
                        "yes_bid": 0.42,
                        "yes_ask": 0.44,
                        "no_bid": 0.48,
                        "no_ask": 0.50,
                        "volume": 5_000,
                        "liquidity": 2_000,
                        "strikeDate": "2026-09-12T00:15:00Z",
                        "resolutionSource": "provider_rulebook",
                    }
                ],
            }
        ]
    }


@pytest.mark.asyncio
async def test_readiness_checks_api_parser_quality_and_lake(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_payload(), request=request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = WorldMarketsClient(
        WorldMarketsConfig(api_base="https://example.test/api/v1", ws_url="wss://example.test/ws"),
        http_client=http,
    )

    report = await check_world_readiness(
        client.config,
        client=client,
        landing_writer=WorldLandingWriter(tmp_path),
    )
    await http.aclose()

    assert report.api_status == "passed"
    assert report.parser_status == "passed"
    assert report.lake_status == "passed"
    assert report.market_count == 1
    assert report.quality_eligible_market_count == 1
    assert report.ready_for_paper is True
    assert any(key.startswith("control/manifests/") for key in report_path_keys(tmp_path))


@pytest.mark.asyncio
async def test_readiness_reports_access_block_without_exposing_key(tmp_path):
    secret = "readiness-secret"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {secret}"
        return httpx.Response(403, request=request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = WorldMarketsClient(
        WorldMarketsConfig(
            api_base="https://example.test/api/v1",
            ws_url="wss://example.test/ws",
            api_key=secret,
            max_retries=0,
        ),
        http_client=http,
    )

    report = await check_world_readiness(
        client.config,
        client=client,
        landing_writer=WorldLandingWriter(tmp_path),
    )
    await http.aclose()

    assert report.api_status == "blocked"
    assert report.api_status_code == 403
    assert report.ready_for_paper is False
    assert secret not in str(report.as_dict())


@pytest.mark.asyncio
async def test_readiness_stops_before_network_when_lake_is_required():
    config = WorldMarketsConfig(api_base="https://example.test/api/v1", ws_url="wss://example.test/ws")

    report = await check_world_readiness(config, landing_writer=None)

    assert report.lake_status == "blocked_missing_landing"
    assert report.api_status == "not_run"
    assert report.ready_for_paper is False


def report_path_keys(root) -> list[str]:
    return [path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()]
