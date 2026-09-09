from __future__ import annotations

import httpx
import pytest

from app.market_intel.evm_provider import EVMRetryPolicy
from app.market_intel.risk_gate import RiskState
from app.market_intel.scanner import MarketScanner
from app.market_intel.sources.evm_onchain import EVM_ONCHAIN_VERSION, EVMOnchainSource

TOPIC = "0x" + "11" * 32
FACTORY = "0x" + "aa" * 20
TOKEN0 = "0x" + "01" * 20
TOKEN1 = "0x" + "02" * 20
PAIR = "0x" + "03" * 20


def _word(address: str) -> str:
    return "0x" + "0" * 24 + address[2:]


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _RpcClient:
    def __init__(self, logs):
        self.logs = logs
        self.calls: list[dict] = []

    async def post(self, url, json):
        self.calls.append({"url": url, **json})
        if json["method"] == "eth_blockNumber":
            return _Response({"result": "0x64"})
        if json["method"] == "eth_getLogs":
            return _Response({"result": self.logs})
        raise AssertionError(json["method"])


class _FlakyRpcClient(_RpcClient):
    def __init__(self, logs):
        super().__init__(logs)
        self.block_attempts = 0

    async def post(self, url, json):
        if json["method"] == "eth_blockNumber":
            self.block_attempts += 1
            if self.block_attempts == 1:
                raise httpx.ConnectError("fixture transport failure", request=httpx.Request("POST", url))
        return await super().post(url, json)


class _MalformedRpcClient(_RpcClient):
    def __init__(self, result):
        super().__init__([])
        self.result = result

    async def post(self, url, json):
        self.calls.append({"url": url, **json})
        return _Response({"result": self.result})


@pytest.mark.asyncio
async def test_evm_onchain_source_decodes_pair_events_and_fails_closed():
    client = _RpcClient(
        [
            {
                "address": FACTORY,
                "topics": [TOPIC, _word(TOKEN0), _word(TOKEN1)],
                "data": _word(PAIR) + "0x"[2:] + "0" * 64,
                "blockNumber": "0x63",
                "transactionHash": "0x" + "ab" * 32,
                "logIndex": "0x1",
            }
        ]
    )
    source = EVMOnchainSource(
        rpc_urls={"ethereum": "https://rpc.example"},
        factory_addresses={"ethereum": [FACTORY]},
        event_topics={"ethereum": TOPIC},
        block_lookback=4,
        http_client=client,
    )

    quotes = await source.fetch_quotes()

    assert len(quotes) == 2
    assert {quote.metadata["token_address"] for quote in quotes} == {TOKEN0, TOKEN1}
    assert all(quote.metadata["decoder_status"] == "verified" for quote in quotes)
    assert all(quote.metadata["risk_state"] == RiskState.DETECTED.value for quote in quotes)
    assert source.coverage_status() == {
        "version": EVM_ONCHAIN_VERSION,
        "mode": "polling_eth_getLogs",
        "configured_chains": ["ethereum"],
        "ready_chains": ["ethereum"],
        "block_lookback": 4,
        "last_blocks": {"ethereum": 100},
        "last_errors": {},
        "read_only": True,
        "transactions_submitted": False,
    }
    assert [call["method"] for call in client.calls] == ["eth_blockNumber", "eth_getLogs"]
    log_filter = client.calls[1]["params"][0]
    assert log_filter["fromBlock"] == "0x61"
    assert log_filter["toBlock"] == "0x64"
    assert log_filter["topics"] == [[TOPIC]]

    assert await source.fetch_quotes() == []


@pytest.mark.asyncio
async def test_evm_onchain_source_ignores_logs_from_unrequested_factory():
    client = _RpcClient(
        [
            {
                "address": "0x" + "bb" * 20,
                "topics": [TOPIC, _word(TOKEN0), _word(TOKEN1)],
                "data": _word(PAIR),
                "transactionHash": "0x" + "cd" * 32,
                "logIndex": "0x1",
            }
        ]
    )
    source = EVMOnchainSource(
        rpc_urls={"ethereum": "https://rpc.example"},
        factory_addresses={"ethereum": [FACTORY]},
        event_topics={"ethereum": TOPIC},
        http_client=client,
    )

    assert await source.fetch_quotes() == []


@pytest.mark.asyncio
async def test_evm_onchain_source_empty_configuration_makes_no_requests():
    source = EVMOnchainSource()
    assert await source.fetch_quotes() == []
    assert source.coverage_status()["ready_chains"] == []


@pytest.mark.asyncio
async def test_evm_onchain_source_retries_transient_rpc_transport_errors():
    client = _FlakyRpcClient([])
    sleeps: list[float] = []
    source = EVMOnchainSource(
        rpc_urls={"base": "https://rpc.example"},
        factory_addresses={"base": [FACTORY]},
        event_topics={"base": TOPIC},
        http_client=client,
        retry_policy=EVMRetryPolicy(max_attempts=2, initial_backoff_seconds=0.1),
        sleep=lambda delay: _record_sleep(sleeps, delay),
    )

    assert await source.fetch_quotes() == []
    assert client.block_attempts == 2
    assert sleeps == [0.1]


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [None, "not-a-block", {"block": "0x64"}])
async def test_evm_onchain_source_rejects_malformed_block_number(result):
    client = _MalformedRpcClient(result)
    source = EVMOnchainSource(
        rpc_urls={"ethereum": "https://rpc.example"},
        factory_addresses={"ethereum": [FACTORY]},
        event_topics={"ethereum": TOPIC},
        http_client=client,
    )

    assert await source.fetch_quotes() == []
    assert source.coverage_status()["last_errors"] == {"ethereum": "RuntimeError"}


@pytest.mark.asyncio
async def test_evm_onchain_source_rejects_malformed_logs_result():
    class _LogsShapeClient(_RpcClient):
        async def post(self, url, json):
            self.calls.append({"url": url, **json})
            if json["method"] == "eth_blockNumber":
                return _Response({"result": "0x64"})
            return _Response({"result": {"unexpected": "shape"}})

    client = _LogsShapeClient([])
    source = EVMOnchainSource(
        rpc_urls={"ethereum": "https://rpc.example"},
        factory_addresses={"ethereum": [FACTORY]},
        event_topics={"ethereum": TOPIC},
        http_client=client,
    )

    assert await source.fetch_quotes() == []
    assert source.coverage_status()["last_errors"] == {"ethereum": "RuntimeError"}


async def _record_sleep(sleeps: list[float], delay: float) -> None:
    sleeps.append(delay)


def test_evm_onchain_source_rejects_unsafe_or_incomplete_configuration():
    with pytest.raises(ValueError, match="credential query"):
        EVMOnchainSource(
            rpc_urls={"ethereum": "https://rpc.example?api_key=fixture"},
            factory_addresses={"ethereum": [FACTORY]},
            event_topics={"ethereum": TOPIC},
        )
    with pytest.raises(ValueError, match="event topics"):
        EVMOnchainSource(
            rpc_urls={"ethereum": "https://rpc.example"},
            factory_addresses={"ethereum": [FACTORY]},
            event_topics={"ethereum": "0x1234"},
        )


def test_market_scanner_exposes_evm_onchain_coverage():
    source = EVMOnchainSource(
        rpc_urls={"base": "https://rpc.example"},
        factory_addresses={"base": [FACTORY]},
        event_topics={"base": TOPIC},
    )
    scanner = MarketScanner(enabled_sources=["degen"], evm_onchain_source=source)

    coverage = scanner.sources["degen"].coverage_status()

    assert coverage["target_chains"] == ["solana", "bsc", "ethereum", "base", "arbitrum"]
    assert coverage["evm_onchain"]["ready_chains"] == ["base"]
    assert coverage["evm_security"]["enabled"] is False


def test_market_scanner_loads_evm_onchain_source_from_explicit_env(monkeypatch):
    monkeypatch.setenv("EVM_ONCHAIN_RPC_URLS_JSON", '{"ethereum":"https://rpc.example"}')
    monkeypatch.setenv("EVM_ONCHAIN_FACTORY_ADDRESSES_JSON", f'{{"ethereum":["{FACTORY}"]}}')
    monkeypatch.setenv("EVM_ONCHAIN_EVENT_TOPICS_JSON", f'{{"ethereum":"{TOPIC}"}}')

    scanner = MarketScanner(enabled_sources=["degen"])

    source = scanner.sources["degen"]._evm_onchain_source
    assert source is not None
    assert source.coverage_status()["ready_chains"] == ["ethereum"]
