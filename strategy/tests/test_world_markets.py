from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import httpx
import pyarrow.parquet as parquet
import pytest

from app.market_intel.scanner import MarketScanner
from app.market_intel.sources.world import WorldSource
from app.world.client import WorldApiError, WorldMarketsClient, WorldMarketsConfig, parse_price_tick
from app.world.landing import WorldLandingWriter
from app.world.models import WorldMarket
from app.world.scanner import WorldPaperScanner, WorldScannerConfig


def _event_payload(cursor: str | None = None) -> dict:
    payload = {
        "events": [
            {
                "ticker": "BTC15M",
                "title": "BTC direction in 15 minutes",
                "category": "crypto",
                "tags": ["crypto"],
                "markets": [
                    {
                        "ticker": "BTC15M-UP",
                        "question": "Will BTC be up at settlement?",
                        "status": "active",
                        "yes_bid": "0.42",
                        "yes_ask": "0.44",
                        "no_bid": "0.48",
                        "no_ask": "0.50",
                        "yes_ask_size": "2",
                        "no_ask_size": "3",
                        "volume": "5000",
                        "liquidity": "2000",
                        "strikeDate": "2026-09-12T12:00:00Z",
                        "resolutionSource": "provider_rulebook",
                    }
                ],
            }
        ]
    }
    if cursor is not None:
        payload["cursor"] = cursor
    return payload


@pytest.mark.asyncio
async def test_client_parses_events_and_uses_bounded_query_shape():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_event_payload(), request=request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    config = WorldMarketsConfig(api_base="https://example.test/api/v1", ws_url="wss://example.test/ws")
    client = WorldMarketsClient(config, http_client=http)
    page = await client.list_events(category="crypto", tags=["Crypto"], limit=20)
    await http.aclose()

    assert len(page.events) == 1
    assert page.events[0]["markets"][0]["ticker"] == "BTC15M-UP"
    assert page.request_params == {
        "withNestedMarkets": "true",
        "limit": "20",
        "category": "crypto",
        "tags": "crypto",
        "status": "active",
    }
    assert str(seen[0].url).endswith("withNestedMarkets=true&limit=20&category=crypto&tags=crypto&status=active")


@pytest.mark.asyncio
async def test_client_flattens_nested_markets_and_paginates():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.params.get("cursor", "first"))
        body = _event_payload("next") if len(calls) == 1 else _event_payload()
        if len(calls) == 2:
            body["events"][0]["markets"][0]["ticker"] = "ETH15M-UP"
        return httpx.Response(200, json=body, request=request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = WorldMarketsClient(
        WorldMarketsConfig(api_base="https://example.test/api/v1", ws_url="wss://example.test/ws"),
        http_client=http,
    )
    markets = await client.list_markets(limit=10, max_pages=2)
    await http.aclose()

    assert [market.ticker for market in markets] == ["BTC15M-UP", "ETH15M-UP"]
    assert calls == ["first", "next"]
    assert markets[0].yes_ask == pytest.approx(0.44)
    assert markets[0].yes_ask_size == pytest.approx(2.0)
    assert markets[0].no_ask_size == pytest.approx(3.0)
    assert markets[0].buy_both_total == pytest.approx(0.94)


@pytest.mark.asyncio
async def test_api_error_does_not_expose_api_key():
    secret = "do-not-print-this"

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
    with pytest.raises(WorldApiError) as error:
        await client.list_events()
    await http.aclose()

    assert error.value.status_code == 403
    assert secret not in str(error.value)


def test_price_tick_parser_ignores_ack_and_normalizes_ticker():
    assert parse_price_tick({"type": "subscribed", "channel": "world_prices"}) is None
    tick = parse_price_tick(
        {
            "type": "ticker",
            "data": {
                "market_ticker": "BTC15M-UP",
                "yes_bid": "0.41",
                "yes_ask": "0.43",
                "no_bid": "0.49",
                "no_ask": "0.51",
                "timestamp": 1_757_674_800_000,
            },
        }
    )
    assert tick is not None
    assert tick.ticker == "BTC15M-UP"
    assert tick.yes_mid == pytest.approx(0.42)
    assert tick.no_mid == pytest.approx(0.50)


def test_landing_preserves_exact_bytes_and_is_idempotent(tmp_path):
    raw = b'{"events":[{"ticker":"BTC15M-UP"}]}\n'
    writer = WorldLandingWriter(tmp_path)
    first = writer.write_snapshot(
        raw,
        endpoint="/events",
        request_params={"status": "active", "api_key": "must-not-land"},
    )
    second = writer.write_snapshot(
        raw,
        endpoint="/events",
        request_params={"status": "active", "api_key": "different"},
    )

    assert first["status"] == "written"
    assert second["status"] == "existing"
    assert (tmp_path / first["raw_key"]).read_bytes() == raw
    manifest = json.loads((tmp_path / first["manifest_key"]).read_text())
    assert manifest["source"] == "world_xyz"
    assert manifest["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert manifest["metadata"]["request_params"]["api_key"] == "[REDACTED]"
    table = parquet.read_table(tmp_path / first["bronze_key"])
    assert table.num_rows == 1
    assert table.column("payload_json")[0].as_py() == raw.decode()
    assert table.column_names == manifest["bronze"]["columns"]


def test_landing_reuses_immutable_keys_when_retrying_on_a_later_day(tmp_path):
    raw = b'{"events":[{"ticker":"BTC15M-UP"}]}\n'
    first = WorldLandingWriter(tmp_path).write_snapshot(
        raw,
        endpoint="/events",
        received_at=datetime(2026, 9, 12, 0, 0, tzinfo=UTC),
    )
    second = WorldLandingWriter(tmp_path).write_snapshot(
        raw,
        endpoint="/events",
        received_at=datetime(2026, 9, 13, 0, 0, tzinfo=UTC),
    )

    assert second["status"] == "existing"
    assert second["raw_key"] == first["raw_key"]
    assert second["bronze_key"] == first["bronze_key"]


def test_paper_scanner_flags_gross_gap_without_calling_it_profit():
    market = WorldMarket(
        ticker="BTC15M-UP",
        title="BTC direction",
        question="Will BTC be up?",
        status="active",
        yes_bid=0.42,
        yes_ask=0.44,
        no_bid=0.48,
        no_ask=0.50,
        volume=5_000,
        liquidity=2_000,
        strike_date="2026-09-12T12:00:00Z",
        resolution_source="provider_rulebook",
    )
    signals = WorldPaperScanner(WorldScannerConfig(min_complement_gap=0.03)).scan([market])

    assert len(signals) == 1
    assert signals[0].signal_type == "gross_complement_underpricing"
    assert signals[0].side == "BUY_BOTH_REVIEW"
    assert signals[0].metadata["paper_only"] is True
    assert "fees" in signals[0].reason


def test_paper_scanner_rejects_invalid_quotes_and_preserves_zero_price():
    invalid = WorldMarket(
        ticker="BAD",
        question="Invalid quote?",
        status="active",
        yes_bid=0.7,
        yes_ask=0.6,
        no_bid=0.4,
        no_ask=1.2,
        volume=1_000,
        liquidity=500,
        strike_date="2026-09-12T12:00:00Z",
        resolution_source="provider_rulebook",
    )
    zero = WorldMarket(ticker="ZERO", yes_price=0.0, last_price=0.5)

    assert "yes_bid_above_ask" in invalid.validation_errors
    assert "no_ask_outside_binary_price_range" in invalid.validation_errors
    assert WorldPaperScanner().scan([invalid]) == []
    assert zero.yes_mid == 0.0


@pytest.mark.asyncio
async def test_world_source_lands_and_exposes_unified_quote():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_event_payload(), request=request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    config = WorldMarketsConfig(api_base="https://example.test/api/v1", ws_url="wss://example.test/ws")
    client = WorldMarketsClient(config, http_client=http)
    source = WorldSource(client=client, landing_writer=None, require_landing=False)
    quotes = await source.fetch_quotes()
    opportunities = await source.scan_opportunities(quotes)
    await http.aclose()

    assert quotes[0].source == "world_xyz"
    assert quotes[0].metadata["paper_only"] is True
    assert opportunities[0].metadata["confidence_kind"] == "data_quality_not_probability"


def test_world_source_is_opt_in_in_unified_scanner():
    scanner = MarketScanner(enabled_sources=["world"])
    assert set(scanner.sources) == {"world"}


@pytest.mark.asyncio
async def test_world_source_fails_closed_without_landing():
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(500, request=request)))
    client = WorldMarketsClient(
        WorldMarketsConfig(api_base="https://example.test/api/v1", ws_url="wss://example.test/ws"),
        http_client=http,
    )
    source = WorldSource(client=client, landing_writer=None)

    with pytest.raises(WorldApiError, match="landing is not configured"):
        await source.fetch_markets()
    await http.aclose()
