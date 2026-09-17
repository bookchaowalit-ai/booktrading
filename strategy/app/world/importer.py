"""Import a user-supplied World Markets JSON response into the local lake."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.world.client import _event_markets, _extract_events, parse_world_market
from app.world.landing import WorldLandingWriter
from app.world.models import WorldMarket, WorldPaperSignal
from app.world.scanner import WorldPaperScanner

MAX_IMPORT_BYTES = 20 * 1024 * 1024


class WorldImportError(ValueError):
    """A safe, non-network error raised before or during local import."""


@dataclass(frozen=True, slots=True)
class WorldImportReport:
    """Normalized evidence and paper signals produced by one local import."""

    landing: dict[str, Any]
    received_at: str
    raw_sha256: str
    markets: tuple[dict[str, Any], ...]
    signals: tuple[dict[str, Any], ...]
    quality_eligible_market_count: int
    invalid_market_count: int
    incomplete_resolution_count: int
    mode: str = "local_json_paper_import"

    @property
    def markets_scanned(self) -> int:
        return len(self.markets)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": "world_xyz",
            "mode": self.mode,
            "execution_enabled": False,
            "lake_persisted": True,
            "received_at": self.received_at,
            "raw_sha256": self.raw_sha256,
            "landing": self.landing,
            "markets_scanned": self.markets_scanned,
            "quality_eligible_market_count": self.quality_eligible_market_count,
            "invalid_market_count": self.invalid_market_count,
            "incomplete_resolution_count": self.incomplete_resolution_count,
            "signals": list(self.signals),
            "markets": list(self.markets),
        }


def import_world_snapshot(
    payload_path: str | Path,
    lake_root: str | Path,
    *,
    endpoint: str = "/events",
    received_at: datetime | None = None,
    scanner: WorldPaperScanner | None = None,
) -> WorldImportReport:
    """Validate and land one local World JSON response, then scan it.

    The source bytes are read and validated before any lake object is written.
    The landing writer derives identity from the raw checksum, so retrying the
    same file reuses the existing immutable objects.
    """

    raw, payload = _read_payload(Path(payload_path))
    return _build_import_report(
        raw,
        payload,
        lake_root,
        endpoint=endpoint,
        received_at=received_at,
        scanner=scanner,
        mode="local_json_paper_import",
        ingest_mode="local_file",
    )


def import_world_response(
    raw: bytes,
    lake_root: str | Path,
    *,
    endpoint: str = "/events",
    received_at: datetime | None = None,
    scanner: WorldPaperScanner | None = None,
) -> WorldImportReport:
    """Validate and land one HTTP response body, then scan it.

    The body is accepted as bytes so the lake receives the exact producer
    response.  This is the shared implementation used by the backend API and
    the local-file adapter.
    """

    payload = _parse_payload(raw)
    return _build_import_report(
        raw,
        payload,
        lake_root,
        endpoint=endpoint,
        received_at=received_at,
        scanner=scanner,
        mode="api_json_paper_import",
        ingest_mode="api_request",
    )


def _build_import_report(
    raw: bytes,
    payload: Any,
    lake_root: str | Path,
    *,
    endpoint: str,
    received_at: datetime | None,
    scanner: WorldPaperScanner | None,
    mode: str,
    ingest_mode: str,
) -> WorldImportReport:
    """Persist one already-validated payload and build its paper report."""

    stable_received_at = _normalise_received_at(received_at)
    active_scanner = scanner or WorldPaperScanner()
    landing = WorldLandingWriter(lake_root).write_snapshot(
        raw,
        endpoint=endpoint,
        record_type="events",
        request_params={"ingest_mode": ingest_mode},
        received_at=stable_received_at,
    )
    markets = _normalise_markets(payload)
    signals = active_scanner.scan(markets, now=stable_received_at)
    return WorldImportReport(
        landing=landing,
        received_at=stable_received_at.isoformat(),
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        markets=tuple(_market_dict(market) for market in markets),
        signals=tuple(_signal_dict(signal) for signal in signals),
        quality_eligible_market_count=sum(active_scanner.is_eligible(market) for market in markets),
        invalid_market_count=sum(bool(market.validation_errors) for market in markets),
        incomplete_resolution_count=sum(bool(market.resolution_errors) for market in markets),
        mode=mode,
    )


def _read_payload(path: Path) -> tuple[bytes, Any]:
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_IMPORT_BYTES + 1)
    except OSError as exc:
        raise WorldImportError("World JSON payload file is unavailable") from exc
    if not raw:
        raise WorldImportError("World JSON payload is empty")
    if len(raw) > MAX_IMPORT_BYTES:
        raise WorldImportError(f"World JSON payload exceeds the {MAX_IMPORT_BYTES} byte limit")
    return raw, _parse_payload(raw)


def _parse_payload(raw: bytes) -> Any:
    if not raw:
        raise WorldImportError("World JSON payload is empty")
    if len(raw) > MAX_IMPORT_BYTES:
        raise WorldImportError(f"World JSON payload exceeds the {MAX_IMPORT_BYTES} byte limit")
    try:
        text = raw.decode("utf-8")
        payload = json.loads(text, parse_constant=_reject_non_json_constant)
    except (UnicodeDecodeError, ValueError) as exc:
        raise WorldImportError("World JSON payload is invalid JSON") from exc
    if not isinstance(payload, (Mapping, list)):
        raise WorldImportError("World JSON payload must be an object or array")
    return payload


def _normalise_received_at(value: datetime | None) -> datetime:
    result = value or datetime.now(UTC)
    if result.tzinfo is None or result.utcoffset() is None:
        raise WorldImportError("received_at requires a timezone")
    return result.astimezone(UTC)


def _normalise_markets(payload: Any) -> list[WorldMarket]:
    markets: list[WorldMarket] = []
    seen_tickers: set[str] = set()
    for event in _extract_events(payload):
        for item in _event_markets(event):
            market = parse_world_market(item, event=event)
            if not market.ticker or market.ticker in seen_tickers:
                continue
            seen_tickers.add(market.ticker)
            markets.append(market)
    return markets


def _market_dict(market: WorldMarket) -> dict[str, Any]:
    return {
        "ticker": market.ticker,
        "event_ticker": market.event_ticker,
        "series_ticker": market.series_ticker,
        "title": market.title,
        "question": market.question,
        "category": market.category,
        "tags": list(market.tags),
        "status": market.status,
        "yes_bid": market.yes_bid,
        "yes_ask": market.yes_ask,
        "no_bid": market.no_bid,
        "no_ask": market.no_ask,
        "yes_ask_size": market.yes_ask_size,
        "no_ask_size": market.no_ask_size,
        "yes_mid": market.yes_mid,
        "no_mid": market.no_mid,
        "volume": market.volume,
        "liquidity": market.liquidity,
        "open_time": market.open_time,
        "close_time": market.close_time,
        "strike_date": market.strike_date,
        "resolution_source": market.resolution_source,
        "updated_at": market.updated_at.isoformat() if market.updated_at else None,
        "validation_errors": list(market.validation_errors),
        "resolution_errors": list(market.resolution_errors),
    }


def _signal_dict(signal: WorldPaperSignal) -> dict[str, Any]:
    return {
        "ticker": signal.ticker,
        "signal_type": signal.signal_type,
        "side": signal.side,
        "rank_score": signal.rank_score,
        "data_confidence": signal.data_confidence,
        "reason": signal.reason,
        "metadata": signal.metadata,
    }


def _reject_non_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")
