"""Reconnectable, read-only Solana log stream for degen discovery.

The stream observes program logs and asks the configured RPC endpoint for the
confirmed transaction.  It never signs, submits, or routes an order.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from app.market_intel.onchain_landing import OnchainLandingWriter
from app.market_intel.sources.solana_onchain import (
    PUMP_PROGRAM_ID,
    SOLANA_RPC_URL,
    classify_logs,
    transaction_to_events,
)

try:  # uvicorn[standard] normally supplies websockets; import lazily in tests.
    import websockets
except ImportError:  # pragma: no cover - exercised only in minimal installs
    websockets = None

logger = logging.getLogger(__name__)

EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class SolanaOnchainStream:
    """Subscribe to launchpad/AMM logs with reconnect and replay safety."""

    def __init__(
        self,
        ws_url: str | None = None,
        rpc_url: str | None = None,
        program_ids: list[str] | None = None,
        checkpoint_path: str | None = None,
        reconnect_min_seconds: float = 1.0,
        reconnect_max_seconds: float = 30.0,
        backfill_limit: int = 25,
        http_client: httpx.AsyncClient | None = None,
        landing_writer: OnchainLandingWriter | None = None,
    ):
        self.ws_url = ws_url or os.getenv("SOLANA_WS_URL", "wss://api.mainnet-beta.solana.com")
        self.rpc_url = rpc_url or os.getenv("SOLANA_RPC_URL", SOLANA_RPC_URL)
        configured_ids = os.getenv("SOLANA_ONCHAIN_PROGRAM_IDS", "")
        self.program_ids = program_ids or [
            item.strip() for item in (configured_ids or PUMP_PROGRAM_ID).split(",") if item.strip()
        ]
        checkpoint_value = checkpoint_path or os.getenv("SOLANA_DEGEN_CHECKPOINT")
        self.checkpoint_path = Path(checkpoint_value) if checkpoint_value else None
        self.reconnect_min_seconds = max(0.1, reconnect_min_seconds)
        self.reconnect_max_seconds = max(self.reconnect_min_seconds, reconnect_max_seconds)
        self.backfill_limit = max(0, min(int(backfill_limit), 100))
        self._http_client = http_client
        self.landing_writer = landing_writer
        self._seen_signatures: set[str] = set()
        self._last_slot = 0
        self._last_signature: str | None = None
        self._connected = False
        self._reconnects = 0
        self._events_seen = 0
        self._last_event_at: str | None = None
        self._landing_errors = 0
        self._last_landing_error: str | None = None
        self._pending: dict[str, dict[str, Any]] = {}
        self._enrichment_tasks: set[asyncio.Task] = set()
        self._load_checkpoint()

    @classmethod
    def from_env(cls) -> SolanaOnchainStream:
        return cls(landing_writer=OnchainLandingWriter.from_env())

    def _load_checkpoint(self) -> None:
        if not self.checkpoint_path or not self.checkpoint_path.exists():
            return
        try:
            checkpoint = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
            self._last_slot = int(checkpoint.get("last_slot", 0))
            self._last_signature = checkpoint.get("last_signature") or None
            signatures = checkpoint.get("seen_signatures", [])
            self._seen_signatures = {str(item) for item in signatures[-2000:]}
            pending = checkpoint.get("pending", {})
            if isinstance(pending, dict):
                self._pending = {
                    str(signature): {
                        "slot": _as_int(item.get("slot")),
                        "program_id": item.get("program_id"),
                        "logs": item.get("logs") or [],
                        "last_attempt": 0.0,
                    }
                    for signature, item in list(pending.items())[:200]
                    if isinstance(item, dict) and item.get("program_id")
                }
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("Ignoring invalid Solana stream checkpoint: %s", exc)

    def _save_checkpoint(self) -> None:
        if not self.checkpoint_path:
            return
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "last_slot": self._last_slot,
            "last_signature": self._last_signature,
            "seen_signatures": sorted(self._seen_signatures)[-2000:],
            "pending": {
                signature: {
                    "slot": item["slot"],
                    "program_id": item["program_id"],
                    "logs": item["logs"][:100],
                }
                for signature, item in list(self._pending.items())[:200]
            },
            "updated_at": datetime.now(UTC).isoformat(),
        }
        temp_path = self.checkpoint_path.with_suffix(self.checkpoint_path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        os.replace(temp_path, self.checkpoint_path)

    def status(self) -> dict[str, Any]:
        """Return operational state without exposing endpoint credentials."""
        return {
            "enabled": True,
            "connected": self._connected,
            "program_count": len(self.program_ids),
            "last_slot": self._last_slot,
            "last_signature": self._last_signature,
            "events_seen": self._events_seen,
            "reconnects": self._reconnects,
            "pending_enrichment": len(self._pending),
            "last_event_at": self._last_event_at,
            "checkpoint_enabled": self.checkpoint_path is not None,
            "landing_enabled": self.landing_writer is not None,
            "landing_errors": self._landing_errors,
            "last_landing_error": self._last_landing_error,
        }

    async def _rpc(self, method: str, params: list[Any]) -> Any:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        if self._http_client:
            response = await self._http_client.post(self.rpc_url, json=payload)
            response.raise_for_status()
            body = response.json()
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.rpc_url, json=payload)
                response.raise_for_status()
                body = response.json()
        if body.get("error"):
            raise RuntimeError(f"Solana RPC {method} failed: {body['error']}")
        return body.get("result")

    async def _fetch_events(
        self,
        *,
        signature: str,
        slot: int,
        program_id: str,
        logs: list[str],
    ) -> list[dict[str, Any]]:
        try:
            transaction = await self._rpc(
                "getTransaction",
                [
                    signature,
                    {
                        "encoding": "jsonParsed",
                        "commitment": "confirmed",
                        "maxSupportedTransactionVersion": 0,
                    },
                ],
            )
        except Exception as exc:
            logger.debug("Could not fetch transaction %s: %s", signature, exc)
            transaction = None
        if transaction:
            return transaction_to_events(
                transaction,
                signature=signature,
                slot=slot,
                program_id=program_id,
            )

        event_type = classify_logs(logs)
        if not event_type:
            return []
        return [
            {
                "event_id": f"{program_id}:{signature}:{event_type}:unknown",
                "event_type": event_type,
                "signature": signature,
                "slot": slot,
                "block_time": None,
                "program_id": program_id,
                "chain": "solana",
                "token_address": None,
                "log_messages": [str(log)[:1000] for log in logs[:100]],
                "observed_at": datetime.now(UTC).isoformat(),
                "decoder_version": "solana-log-hint.v1",
                "decoder_status": "unverified",
                "data_complete": False,
                "source": "solana_stream",
                "risk_flags": ["transaction_unavailable"],
            }
        ]

    async def _dispatch(self, callback: EventCallback, event: dict[str, Any]) -> None:
        result = callback(event)
        if inspect.isawaitable(result):
            await result

    async def _land_raw_notification(
        self,
        raw_message: bytes | str,
        event: dict[str, Any],
    ) -> None:
        """Persist the source frame before a normalized event reaches a consumer."""

        if self.landing_writer is None:
            return
        try:
            await asyncio.to_thread(self.landing_writer.write_raw, raw_message, event)
        except Exception as exc:
            self._landing_errors += 1
            self._last_landing_error = type(exc).__name__
            # Do not dispatch a source event without its configured lake
            # evidence.  ``run`` will reconnect and retry the bounded frame.
            logger.warning("Solana raw landing failed (%s)", type(exc).__name__)
            raise

    async def _process_signature(
        self,
        callback: EventCallback,
        *,
        signature: str,
        slot: int,
        program_id: str,
        logs: list[str],
        initial: bool = False,
    ) -> None:
        if signature in self._seen_signatures:
            return
        events = await self._fetch_events(
            signature=signature,
            slot=slot,
            program_id=program_id,
            logs=logs,
        )
        self._last_slot = max(self._last_slot, slot)
        complete = bool(events) and all(event.get("data_complete", True) for event in events)
        if initial or complete:
            for event in events:
                await self._dispatch(callback, event)
                self._events_seen += 1
                self._last_event_at = event.get("observed_at")
        if complete or not events:
            self._seen_signatures.add(signature)
            self._last_signature = signature
            self._pending.pop(signature, None)
        else:
            self._pending[signature] = {
                "slot": slot,
                "program_id": program_id,
                "logs": logs,
                "last_attempt": time.monotonic(),
            }
        self._save_checkpoint()

    async def _retry_pending(self, callback: EventCallback) -> None:
        """Retry incomplete confirmations without repeating the first alert."""
        now = time.monotonic()
        for signature, pending in list(self._pending.items()):
            if now - pending["last_attempt"] < 2.0:
                continue
            pending["last_attempt"] = now
            events = await self._fetch_events(
                signature=signature,
                slot=pending["slot"],
                program_id=pending["program_id"],
                logs=pending["logs"],
            )
            if not events or not all(event.get("data_complete", True) for event in events):
                continue
            for event in events:
                await self._dispatch(callback, event)
                self._events_seen += 1
                self._last_event_at = event.get("observed_at")
            self._seen_signatures.add(signature)
            self._last_signature = signature
            self._pending.pop(signature, None)
            self._save_checkpoint()

    @staticmethod
    def _preliminary_event(
        *,
        signature: str,
        slot: int,
        program_id: str,
        logs: list[str],
    ) -> dict[str, Any] | None:
        event_type = classify_logs(logs)
        if not event_type:
            return None
        return {
            "event_id": f"{program_id}:{signature}:{event_type}:unknown",
            "event_type": event_type,
            "signature": signature,
            "slot": slot,
            "block_time": None,
            "program_id": program_id,
            "chain": "solana",
            "token_address": None,
            "log_messages": [str(log)[:1000] for log in logs[:100]],
            "observed_at": datetime.now(UTC).isoformat(),
            "data_complete": False,
            "source": "solana_stream",
            "risk_flags": ["transaction_pending"],
        }

    @staticmethod
    def _raw_notification_event(
        *,
        signature: str,
        slot: int,
        program_id: str,
        logs: list[str],
        failed: bool = False,
    ) -> dict[str, Any]:
        event_type = classify_logs(logs) or ("transaction_failed" if failed else "transaction_log")
        return {
            "event_id": f"{program_id}:{signature}:{event_type}:unknown",
            "event_type": event_type,
            "signature": signature,
            "slot": slot,
            "program_id": program_id,
            "chain": "solana",
            "log_messages": [str(log)[:1000] for log in logs[:100]],
            "observed_at": datetime.now(UTC).isoformat(),
            "data_complete": False,
            "source": "solana_stream",
            "risk_flags": ["transaction_failed" if failed else "unclassified_logs"],
        }

    def _track_enrichment_task(self, task: asyncio.Task) -> None:
        self._enrichment_tasks.add(task)

        def _finish(completed: asyncio.Task) -> None:
            self._enrichment_tasks.discard(completed)
            if not completed.cancelled() and completed.exception():
                logger.debug("Solana event enrichment failed: %s", completed.exception())

        task.add_done_callback(_finish)

    async def _stop_enrichment_tasks(self) -> None:
        tasks = list(self._enrichment_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._enrichment_tasks.clear()

    async def _backfill(self, callback: EventCallback) -> None:
        """Bounded startup backfill for events received during disconnects."""
        if self.backfill_limit <= 0:
            return
        for program_id in self.program_ids:
            try:
                signatures = (
                    await self._rpc(
                        "getSignaturesForAddress",
                        [program_id, {"limit": self.backfill_limit, "commitment": "confirmed"}],
                    )
                    or []
                )
                candidates = [
                    item
                    for item in signatures
                    if isinstance(item, dict)
                    and item.get("signature")
                    and item.get("err") is None
                    and _as_int(item.get("slot")) > self._last_slot
                ]
                for item in sorted(candidates, key=lambda value: _as_int(value.get("slot"))):
                    await self._process_signature(
                        callback,
                        signature=item["signature"],
                        slot=_as_int(item.get("slot")),
                        program_id=program_id,
                        logs=[],
                        initial=True,
                    )
            except Exception as exc:
                logger.debug("Solana backfill failed for %s: %s", program_id, exc)

    async def _consume_connection(self, callback: EventCallback, stop_event: asyncio.Event) -> None:
        if websockets is None:
            raise RuntimeError("websockets package is required for SOLANA_WS_URL streaming")
        subscriptions: dict[int, str] = {}
        async with websockets.connect(
            self.ws_url,
            ping_interval=20,
            close_timeout=1,
            max_size=4 * 1024 * 1024,
        ) as socket:
            self._connected = True
            for request_id, program_id in enumerate(self.program_ids, start=1):
                await socket.send(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "method": "logsSubscribe",
                            "params": [{"mentions": [program_id]}, {"commitment": "processed"}],
                        }
                    )
                )
            await self._backfill(callback)

            while not stop_event.is_set():
                try:
                    raw_message = await asyncio.wait_for(socket.recv(), timeout=1.0)
                except TimeoutError:
                    await self._retry_pending(callback)
                    continue
                try:
                    payload = json.loads(raw_message)
                except (TypeError, json.JSONDecodeError):
                    await self._land_raw_notification(
                        raw_message,
                        {
                            "event_type": "malformed_notification",
                            "observed_at": datetime.now(UTC).isoformat(),
                        },
                    )
                    continue
                if not isinstance(payload, dict):
                    await self._land_raw_notification(
                        raw_message,
                        {
                            "event_type": "malformed_notification",
                            "observed_at": datetime.now(UTC).isoformat(),
                        },
                    )
                    continue
                if "result" in payload and isinstance(payload.get("id"), int):
                    request_id = payload["id"]
                    if request_id <= len(self.program_ids):
                        subscriptions[_as_int(payload.get("result"))] = self.program_ids[request_id - 1]
                    continue
                if payload.get("method") != "logsNotification":
                    continue
                params = payload.get("params") or {}
                if not isinstance(params, dict):
                    continue
                result = params.get("result") or {}
                if not isinstance(result, dict):
                    continue
                context = result.get("context") or {}
                value = result.get("value") or {}
                if not isinstance(context, dict) or not isinstance(value, dict):
                    continue
                signature = value.get("signature")
                if not signature:
                    continue
                program_id = subscriptions.get(_as_int(params.get("subscription")), self.program_ids[0])
                slot = _as_int(context.get("slot"))
                logs = value.get("logs") or []
                preliminary = self._preliminary_event(
                    signature=signature,
                    slot=slot,
                    program_id=program_id,
                    logs=logs,
                )
                failed = value.get("err") is not None
                landing_event = (
                    self._raw_notification_event(
                        signature=signature,
                        slot=slot,
                        program_id=program_id,
                        logs=logs,
                        failed=True,
                    )
                    if failed
                    else preliminary
                    or self._raw_notification_event(
                        signature=signature,
                        slot=slot,
                        program_id=program_id,
                        logs=logs,
                    )
                )
                await self._land_raw_notification(raw_message, landing_event)
                if failed:
                    self._last_slot = max(self._last_slot, slot)
                    self._last_signature = signature
                    self._seen_signatures.add(signature)
                    self._pending.pop(signature, None)
                    self._save_checkpoint()
                    continue
                if preliminary:
                    await self._dispatch(callback, preliminary)
                    self._events_seen += 1
                    self._last_event_at = preliminary["observed_at"]
                    self._last_slot = max(self._last_slot, slot)
                    self._pending[signature] = {
                        "slot": slot,
                        "program_id": program_id,
                        "logs": logs,
                        "last_attempt": time.monotonic(),
                    }
                    self._save_checkpoint()
                    self._track_enrichment_task(
                        asyncio.create_task(
                            self._process_signature(
                                callback,
                                signature=signature,
                                slot=slot,
                                program_id=program_id,
                                logs=logs,
                                initial=False,
                            )
                        )
                    )
                else:
                    await self._process_signature(
                        callback,
                        signature=signature,
                        slot=slot,
                        program_id=program_id,
                        logs=logs,
                        initial=True,
                    )
        self._connected = False

    async def run(self, callback: EventCallback, stop_event: asyncio.Event | None = None) -> None:
        """Run until cancelled/stopped, reconnecting with bounded backoff."""
        stop_event = stop_event or asyncio.Event()
        delay = self.reconnect_min_seconds
        while not stop_event.is_set():
            try:
                await self._consume_connection(callback, stop_event)
                delay = self.reconnect_min_seconds
            except asyncio.CancelledError:
                self._connected = False
                await self._stop_enrichment_tasks()
                raise
            except Exception as exc:
                self._connected = False
                self._reconnects += 1
                logger.warning("Solana on-chain stream disconnected: %s", exc)
                with suppress(TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), timeout=delay)
                delay = min(delay * 2, self.reconnect_max_seconds)
        await self._stop_enrichment_tasks()


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
