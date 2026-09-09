from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.market_intel.models import MarketType
from app.market_intel.sources.degen import MIN_TXNS_24H, DegenSource
from app.market_intel.sources.solana_onchain import (
    PUMP_PROGRAM_ID,
    SolanaOnchainSource,
    transaction_to_events,
)


def _pair(*, address: str = "Mint111111111111111111111111111111111111111", buys: int = 40, sells: int = 20):
    return {
        "chainId": "solana",
        "priceUsd": "0.00001",
        "priceChange": {"h24": 35},
        "volume": {"h24": 25000},
        "liquidity": {"usd": 12000},
        "txns": {"h24": {"buys": buys, "sells": sells}},
        "fdv": 500000,
        "pairCreatedAt": int(datetime.now(UTC).timestamp() * 1000) - 30000,
        "pairAddress": "Pair11111111111111111111111111111111111111",
        "dexId": "raydium",
        "url": "https://dexscreener.example/pair",
        "baseToken": {"address": address, "symbol": "SAME", "name": "Same Name"},
    }


def test_pair_identity_uses_chain_and_address_and_calculates_age():
    source = DegenSource()
    quote = source._pair_to_quote(_pair())

    assert quote.market_type is MarketType.DEGEN
    assert quote.symbol == "DEGEN_solana_Mint1111"
    assert quote.metadata["token_address"].startswith("Mint")
    assert 0 <= quote.metadata["pair_age_seconds"] < 60


@pytest.mark.asyncio
async def test_low_transaction_pairs_are_not_opportunities():
    source = DegenSource()
    quote = source._pair_to_quote(_pair(buys=MIN_TXNS_24H - 1, sells=0))

    assert await source.scan_opportunities([quote]) == []


def test_duplicate_symbols_are_distinct_tokens():
    source = DegenSource()
    first = source._pair_to_quote(_pair(address="MintA111111111111111111111111111111111111"))
    second = source._pair_to_quote(_pair(address="MintB111111111111111111111111111111111111"))

    deduped = source._deduplicate_quotes([first, second])
    assert {quote.metadata["token_address"] for quote in deduped} == {
        "MintA111111111111111111111111111111111111",
        "MintB111111111111111111111111111111111111",
    }


def test_onchain_transaction_event_preserves_signature_slot_and_mint():
    transaction = {
        "blockTime": 1700000000,
        "meta": {
            "err": None,
            "logMessages": ["Program log: Instruction: Create"],
            "postTokenBalances": [{"mint": "MintOnchain1111111111111111111111111111111"}],
        },
        "transaction": {"message": {"accountKeys": [{"pubkey": "Creator111"}], "instructions": []}},
    }

    events = transaction_to_events(
        transaction,
        signature="Sig111",
        slot=123,
        program_id=PUMP_PROGRAM_ID,
    )

    assert len(events) == 1
    assert events[0]["event_type"] == "token_created"
    assert events[0]["token_address"].startswith("MintOnchain")
    assert events[0]["slot"] == 123
    assert events[0]["signature"] == "Sig111"


class _Response:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


class _RpcClient:
    def __init__(self):
        self.calls = []

    async def post(self, url, json):
        self.calls.append(json["method"])
        if json["method"] == "getSignaturesForAddress":
            return _Response({"result": [{"signature": "SigRpc", "slot": 44, "err": None}]})
        return _Response({"result": {
                "blockTime": 1700000000,
                "meta": {
                    "err": None,
                    "logMessages": ["Program log: Instruction: Create"],
                    "postTokenBalances": [{"mint": "MintRpc111111111111111111111111111111111"}],
                },
                "transaction": {"message": {"accountKeys": [], "instructions": []}},
            }})


@pytest.mark.asyncio
async def test_onchain_source_uses_bounded_rpc_backfill():
    client = _RpcClient()
    source = SolanaOnchainSource(
        rpc_url="https://rpc.example",
        program_ids=[PUMP_PROGRAM_ID],
        signature_limit=3,
        risk_enabled=False,
        http_client=client,
    )

    quotes = await source.fetch_quotes()

    assert len(quotes) == 1
    assert quotes[0].source == "solana_rpc"
    assert quotes[0].metadata["token_address"].startswith("MintRpc")
    assert client.calls == ["getSignaturesForAddress", "getTransaction"]


class _RiskRpcClient:
    async def post(self, url, json):
        if json["method"] == "getAccountInfo":
            return _Response({"result": {"value": {
                "owner": "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxu",
                "data": {"parsed": {"info": {
                    "mintAuthority": "Authority111",
                    "freezeAuthority": "Freeze111",
                    "supply": "1000",
                    "extensions": [{"extension": "transferHook"}, {"extension": "permanentDelegate"}],
                }}},
            }}})
        return _Response({"result": {"value": [
            {"amount": "700"},
            {"amount": "100"},
            {"amount": "50"},
        ]}})


@pytest.mark.asyncio
async def test_token_risk_reports_controls_and_holder_concentration():
    source = SolanaOnchainSource(http_client=_RiskRpcClient())

    risk = await source.inspect_token_risk("MintRisk111")

    assert risk["status"] == "observed"
    assert "mint_authority_present" in risk["risk_flags"]
    assert "freeze_authority_present" in risk["risk_flags"]
    assert "permanent_delegate" in risk["risk_flags"]
    assert "transfer_hook" in risk["risk_flags"]
    assert "top5_holder_concentration_high" in risk["risk_flags"]
    assert risk["top5_holder_concentration"] == 0.85
