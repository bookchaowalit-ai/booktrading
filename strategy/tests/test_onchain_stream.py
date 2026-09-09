from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from app.market_intel.onchain_stream import SolanaOnchainStream


@pytest.mark.asyncio
async def test_stream_falls_back_to_incomplete_event_when_transaction_unavailable():
    stream = SolanaOnchainStream(
        ws_url="wss://stream.example",
        rpc_url="https://rpc.example",
        program_ids=["Program111"],
    )

    async def failing_rpc(method, params):
        raise RuntimeError("temporary rpc failure")

    stream._rpc = failing_rpc
    events = await stream._fetch_events(
        signature="SigStream",
        slot=88,
        program_id="Program111",
        logs=["Program log: Instruction: Create"],
    )

    assert len(events) == 1
    assert events[0]["data_complete"] is False
    assert events[0]["risk_flags"] == ["transaction_unavailable"]


def test_stream_checkpoint_is_atomic_and_redacts_endpoint(tmp_path):
    checkpoint = tmp_path / "checkpoint.json"
    stream = SolanaOnchainStream(
        ws_url="wss://provider.example/socket?api-key=secret-value",
        checkpoint_path=str(checkpoint),
    )
    stream._last_slot = 99
    stream._seen_signatures.add("SigA")
    stream._pending["SigPending"] = {"slot": 98, "program_id": "Program111", "logs": [], "last_attempt": 0.0}
    stream._save_checkpoint()

    saved = json.loads(checkpoint.read_text())
    assert saved["last_slot"] == 99
    assert saved["seen_signatures"] == ["SigA"]
    assert "SigPending" in saved["pending"]
    assert "secret-value" not in json.dumps(stream.status())

    restored = SolanaOnchainStream(checkpoint_path=str(checkpoint))
    assert restored.status()["last_slot"] == 99
    assert restored.status()["pending_enrichment"] == 1


@pytest.mark.asyncio
async def test_stream_stop_event_does_not_block_before_connect(monkeypatch):
    stream = SolanaOnchainStream(program_ids=["Program111"], backfill_limit=0)
    stop_event = asyncio.Event()
    stop_event.set()
    called = False

    async def callback(_event):
        nonlocal called
        called = True

    await stream.run(callback, stop_event)
    assert called is False
    assert stream.status()["reconnects"] == 0


@pytest.mark.asyncio
async def test_stream_subscribes_and_dispatches_log_notification(monkeypatch):
    import app.market_intel.onchain_stream as stream_module

    stop_event = asyncio.Event()

    class FakeSocket:
        def __init__(self):
            self.sent = []
            self.notification = json.dumps(
                {
                    "method": "logsNotification",
                    "params": {
                        "subscription": 7,
                        "result": {
                            "context": {"slot": 100},
                            "value": {"signature": "SigRealtime", "err": None, "logs": ["Instruction: Create"]},
                        },
                    },
                }
            )
            self.messages = [
                json.dumps({"jsonrpc": "2.0", "id": 1, "result": 7}),
                self.notification,
            ]

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def send(self, message):
            self.sent.append(json.loads(message))

        async def recv(self):
            if self.messages:
                return self.messages.pop(0)
            raise ConnectionError("test stream complete")

    socket = FakeSocket()
    monkeypatch.setattr(stream_module, "websockets", SimpleNamespace(connect=lambda *args, **kwargs: socket))

    class FakeLanding:
        def __init__(self):
            self.calls = []

        def write_raw(self, raw, event):
            self.calls.append((raw, event))

    landing = FakeLanding()
    stream = SolanaOnchainStream(
        program_ids=["Program111"],
        reconnect_min_seconds=0.01,
        backfill_limit=0,
        landing_writer=landing,
    )

    async def fake_fetch_events(**kwargs):
        return [
            {
                "event_id": "event-1",
                "event_type": "token_created",
                "signature": kwargs["signature"],
                "slot": kwargs["slot"],
                "observed_at": "2026-01-01T00:00:00+00:00",
            }
        ]

    monkeypatch.setattr(stream, "_fetch_events", fake_fetch_events)
    received = []

    async def callback(event):
        received.append(event)
        stop_event.set()

    await stream.run(callback, stop_event)

    assert socket.sent[0]["method"] == "logsSubscribe"
    assert received[0]["signature"] == "SigRealtime"
    assert stream.status()["last_slot"] == 100
    assert stream.status()["landing_enabled"] is True
    assert landing.calls[0][0] == socket.notification
    assert landing.calls[0][1]["signature"] == "SigRealtime"
