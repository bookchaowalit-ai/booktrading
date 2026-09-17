"""Deterministic, offline paper replay for World Markets fixtures."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.world.client import parse_world_market
from app.world.models import WorldMarket
from app.world.scanner import WorldPaperScanner

FIXTURE_VERSION = 1
MAX_FIXTURE_BYTES = 20 * 1024 * 1024
MAX_FIXTURE_FRAMES = 100_000


class WorldReplayError(ValueError):
    """A malformed or unsafe offline replay fixture."""


@dataclass(frozen=True, slots=True)
class WorldSettlement:
    """A settlement event revealed at a fixture timestamp."""

    ticker: str
    payout: float


@dataclass(frozen=True, slots=True)
class WorldReplayFrame:
    """One chronological observation or settlement frame."""

    observed_at: datetime
    markets: tuple[WorldMarket, ...] = ()
    settlements: tuple[WorldSettlement, ...] = ()


@dataclass(frozen=True, slots=True)
class WorldReplayConfig:
    """Paper-cost assumptions for a replay; these are not execution settings."""

    fee_bps_per_leg: float = 50.0
    slippage_bps_per_leg: float = 0.0
    min_net_edge: float = 0.0
    max_open_positions: int = 100
    max_quote_age_seconds: float = 30.0
    target_units: float = 1.0
    unknown_size_fill_ratio: float = 1.0

    def __post_init__(self) -> None:
        for name in (
            "fee_bps_per_leg",
            "slippage_bps_per_leg",
            "min_net_edge",
            "max_quote_age_seconds",
            "target_units",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} cannot be negative or non-finite")
        if self.max_open_positions <= 0:
            raise ValueError("max_open_positions must be greater than zero")
        if self.max_quote_age_seconds <= 0:
            raise ValueError("max_quote_age_seconds must be greater than zero")
        if self.target_units <= 0:
            raise ValueError("target_units must be greater than zero")
        if not math.isfinite(self.unknown_size_fill_ratio) or not 0.0 <= self.unknown_size_fill_ratio <= 1.0:
            raise ValueError("unknown_size_fill_ratio must be between 0 and 1")


@dataclass(slots=True)
class _PaperPosition:
    ticker: str
    entered_at: datetime
    yes_ask: float
    no_ask: float
    filled_units: float
    fill_ratio: float
    quote_age_seconds: float | None
    gross_cost: float
    fees: float
    slippage: float
    total_cost: float
    payout: float | None = None
    resolved_at: datetime | None = None

    @property
    def gross_pnl(self) -> float | None:
        if self.payout is None:
            return None
        return self.payout - self.gross_cost

    @property
    def net_pnl(self) -> float | None:
        if self.payout is None:
            return None
        return self.payout - self.total_cost

    def as_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "entered_at": self.entered_at.astimezone(UTC).isoformat(),
            "yes_ask": _round(self.yes_ask),
            "no_ask": _round(self.no_ask),
            "filled_units": _round(self.filled_units),
            "fill_ratio": _round(self.fill_ratio),
            "quote_age_seconds": (None if self.quote_age_seconds is None else _round(self.quote_age_seconds)),
            "gross_cost": _round(self.gross_cost),
            "fees": _round(self.fees),
            "slippage": _round(self.slippage),
            "total_cost": _round(self.total_cost),
            "payout": None if self.payout is None else _round(self.payout),
            "resolved_at": None if self.resolved_at is None else self.resolved_at.astimezone(UTC).isoformat(),
            "gross_pnl": None if self.gross_pnl is None else _round(self.gross_pnl),
            "net_pnl": None if self.net_pnl is None else _round(self.net_pnl),
            "status": "resolved" if self.payout is not None else "unresolved",
        }


@dataclass(frozen=True, slots=True)
class WorldReplayReport:
    """Serializable summary of an offline, hypothetical replay."""

    frame_count: int
    market_observations: int
    invalid_market_observations: int
    signal_count: int
    buy_both_signal_count: int
    entry_count: int
    resolved_entry_count: int
    unresolved_entry_count: int
    gross_pnl: float
    net_pnl: float
    win_rate: float
    max_drawdown: float
    stale_signal_count: int
    partial_fill_entry_count: int
    unresolved_cost: float
    max_open_exposure: float
    assumptions: dict[str, float | int]
    trades: tuple[dict[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": "world_xyz",
            "mode": "offline_fixture_paper_replay",
            "execution_enabled": False,
            "lookahead_safe": True,
            "frame_count": self.frame_count,
            "market_observations": self.market_observations,
            "invalid_market_observations": self.invalid_market_observations,
            "signal_count": self.signal_count,
            "buy_both_signal_count": self.buy_both_signal_count,
            "entry_count": self.entry_count,
            "resolved_entry_count": self.resolved_entry_count,
            "unresolved_entry_count": self.unresolved_entry_count,
            "gross_pnl": _round(self.gross_pnl),
            "net_pnl": _round(self.net_pnl),
            "win_rate": _round(self.win_rate),
            "max_drawdown": _round(self.max_drawdown),
            "stale_signal_count": self.stale_signal_count,
            "partial_fill_entry_count": self.partial_fill_entry_count,
            "unresolved_cost": _round(self.unresolved_cost),
            "max_open_exposure": _round(self.max_open_exposure),
            "assumptions": dict(self.assumptions),
            "trades": list(self.trades),
        }


class WorldReplayRunner:
    """Replay scanner observations chronologically without contacting World."""

    def __init__(
        self,
        *,
        scanner: WorldPaperScanner | None = None,
        config: WorldReplayConfig | None = None,
    ) -> None:
        self.scanner = scanner or WorldPaperScanner()
        self.config = config or WorldReplayConfig()

    def run(self, frames: Sequence[WorldReplayFrame]) -> WorldReplayReport:
        previous_time: datetime | None = None
        open_positions: dict[str, _PaperPosition] = {}
        settled_tickers: set[str] = set()
        all_positions: list[_PaperPosition] = []
        frame_count = 0
        market_observations = 0
        invalid_market_observations = 0
        signal_count = 0
        buy_both_signal_count = 0
        stale_signal_count = 0
        partial_fill_entry_count = 0
        max_open_exposure = 0.0

        for frame in frames:
            observed_at = _utc(frame.observed_at)
            if previous_time is not None and observed_at < previous_time:
                raise WorldReplayError("replay frames must be ordered by observed_at")
            previous_time = observed_at
            frame_count += 1
            market_observations += len(frame.markets)
            invalid_market_observations += sum(
                1 for market in frame.markets if market.validation_errors or market.resolution_errors
            )

            # A settlement at this timestamp is known before any quote at the
            # same timestamp is considered. This prevents same-frame lookahead.
            for settlement in frame.settlements:
                settled_tickers.add(settlement.ticker)
                position = open_positions.pop(settlement.ticker, None)
                if position is None:
                    continue
                position.payout = settlement.payout * position.filled_units
                position.resolved_at = observed_at

            signals = self.scanner.scan(frame.markets, now=observed_at)
            signal_count += len(signals)
            buy_both_signal_count += sum(signal.side == "BUY_BOTH_REVIEW" for signal in signals)
            markets_by_ticker = {market.ticker: market for market in frame.markets}
            for signal in signals:
                if signal.side != "BUY_BOTH_REVIEW":
                    continue
                if signal.ticker in settled_tickers or signal.ticker in open_positions:
                    continue
                if len(open_positions) >= self.config.max_open_positions:
                    continue
                market = markets_by_ticker.get(signal.ticker)
                if market is None or market.yes_ask is None or market.no_ask is None:
                    continue
                quote_age_seconds = _quote_age_seconds(market, observed_at)
                if quote_age_seconds is not None and quote_age_seconds > self.config.max_quote_age_seconds:
                    stale_signal_count += 1
                    continue
                if quote_age_seconds is not None and quote_age_seconds < 0:
                    stale_signal_count += 1
                    continue
                fill_ratio = _fill_ratio(market, self.config)
                if fill_ratio <= 0:
                    continue
                if fill_ratio < 1.0:
                    partial_fill_entry_count += 1
                filled_units = self.config.target_units * fill_ratio
                gross_cost = market.yes_ask + market.no_ask
                gross_cost *= filled_units
                fees = gross_cost * self.config.fee_bps_per_leg / 10_000
                slippage = gross_cost * self.config.slippage_bps_per_leg / 10_000
                total_cost = gross_cost + fees + slippage
                if 1.0 - total_cost < self.config.min_net_edge:
                    continue
                position = _PaperPosition(
                    ticker=market.ticker,
                    entered_at=observed_at,
                    yes_ask=market.yes_ask,
                    no_ask=market.no_ask,
                    filled_units=filled_units,
                    fill_ratio=fill_ratio,
                    quote_age_seconds=quote_age_seconds,
                    gross_cost=gross_cost,
                    fees=fees,
                    slippage=slippage,
                    total_cost=total_cost,
                )
                open_positions[market.ticker] = position
                all_positions.append(position)
                max_open_exposure = max(max_open_exposure, sum(item.total_cost for item in open_positions.values()))

        resolved = [position for position in all_positions if position.net_pnl is not None]
        gross_pnl = sum(position.gross_pnl or 0.0 for position in resolved)
        net_pnl = sum(position.net_pnl or 0.0 for position in resolved)
        wins = sum((position.net_pnl or 0.0) > 0 for position in resolved)
        max_drawdown = _max_drawdown(resolved)
        return WorldReplayReport(
            frame_count=frame_count,
            market_observations=market_observations,
            invalid_market_observations=invalid_market_observations,
            signal_count=signal_count,
            buy_both_signal_count=buy_both_signal_count,
            entry_count=len(all_positions),
            resolved_entry_count=len(resolved),
            unresolved_entry_count=len(all_positions) - len(resolved),
            gross_pnl=_round(gross_pnl),
            net_pnl=_round(net_pnl),
            win_rate=_round(wins / len(resolved) if resolved else 0.0),
            max_drawdown=_round(max_drawdown),
            stale_signal_count=stale_signal_count,
            partial_fill_entry_count=partial_fill_entry_count,
            unresolved_cost=_round(sum(position.total_cost for position in open_positions.values())),
            max_open_exposure=_round(max_open_exposure),
            assumptions={
                "fee_bps_per_leg": self.config.fee_bps_per_leg,
                "slippage_bps_per_leg": self.config.slippage_bps_per_leg,
                "min_net_edge": self.config.min_net_edge,
                "max_open_positions": self.config.max_open_positions,
                "max_quote_age_seconds": self.config.max_quote_age_seconds,
                "target_units": self.config.target_units,
                "unknown_size_fill_ratio": self.config.unknown_size_fill_ratio,
            },
            trades=tuple(position.as_dict() for position in all_positions),
        )


def load_replay_fixture(path: str | Path) -> tuple[WorldReplayFrame, ...]:
    """Load strict JSONL frames with no network or provider dependency."""

    fixture_path = Path(path)
    try:
        size = fixture_path.stat().st_size
    except OSError as exc:
        raise WorldReplayError(f"cannot read replay fixture: {fixture_path}") from exc
    if size > MAX_FIXTURE_BYTES:
        raise WorldReplayError("replay fixture exceeds the 20 MiB safety limit")

    frames: list[WorldReplayFrame] = []
    try:
        stream = fixture_path.open("r", encoding="utf-8")
    except OSError as exc:
        raise WorldReplayError(f"cannot open replay fixture: {fixture_path}") from exc
    with stream:
        for line_number, line in enumerate(stream, start=1):
            if len(frames) >= MAX_FIXTURE_FRAMES:
                raise WorldReplayError("replay fixture exceeds the frame safety limit")
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise WorldReplayError(f"invalid JSON on replay fixture line {line_number}") from exc
            if not isinstance(record, Mapping):
                raise WorldReplayError(f"replay fixture line {line_number} must be an object")
            version = record.get("fixture_version", FIXTURE_VERSION)
            if str(version) != str(FIXTURE_VERSION):
                raise WorldReplayError(f"unsupported replay fixture version on line {line_number}")
            observed_at = _parse_fixture_time(record.get("observed_at"), line_number)
            markets = _parse_markets(record.get("markets", []), line_number)
            settlements = _parse_settlements(record.get("settlements", []), line_number)
            if not markets and not settlements:
                raise WorldReplayError(f"replay fixture line {line_number} has no markets or settlements")
            frames.append(
                WorldReplayFrame(
                    observed_at=observed_at,
                    markets=tuple(markets),
                    settlements=tuple(settlements),
                )
            )
    if not frames:
        raise WorldReplayError("replay fixture is empty")
    return tuple(frames)


def _parse_markets(value: Any, line_number: int) -> list[WorldMarket]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise WorldReplayError(f"markets must be an array on replay fixture line {line_number}")
    markets: list[WorldMarket] = []
    seen: set[str] = set()
    for payload in value:
        if not isinstance(payload, Mapping):
            raise WorldReplayError(f"market must be an object on replay fixture line {line_number}")
        market = parse_world_market(payload)
        if not market.ticker:
            raise WorldReplayError(f"market ticker is required on replay fixture line {line_number}")
        if market.ticker in seen:
            raise WorldReplayError(f"duplicate market ticker on replay fixture line {line_number}")
        seen.add(market.ticker)
        markets.append(market)
    return markets


def _parse_settlements(value: Any, line_number: int) -> list[WorldSettlement]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise WorldReplayError(f"settlements must be an array on replay fixture line {line_number}")
    settlements: list[WorldSettlement] = []
    seen: set[str] = set()
    for payload in value:
        if not isinstance(payload, Mapping):
            raise WorldReplayError(f"settlement must be an object on replay fixture line {line_number}")
        ticker = str(payload.get("ticker") or payload.get("market_ticker") or "").strip()
        payout = payload.get("payout")
        if not ticker or ticker in seen:
            raise WorldReplayError(f"settlement ticker is missing or duplicated on replay fixture line {line_number}")
        try:
            payout_value = float(payout)
        except (TypeError, ValueError) as exc:
            raise WorldReplayError(f"settlement payout is invalid on replay fixture line {line_number}") from exc
        if not math.isfinite(payout_value) or not 0.0 <= payout_value <= 1.0:
            raise WorldReplayError(f"settlement payout must be between 0 and 1 on replay fixture line {line_number}")
        seen.add(ticker)
        settlements.append(WorldSettlement(ticker=ticker, payout=payout_value))
    return settlements


def _parse_fixture_time(value: Any, line_number: int) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise WorldReplayError(f"observed_at is required on replay fixture line {line_number}")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise WorldReplayError(f"observed_at is invalid on replay fixture line {line_number}") from exc
    if parsed.tzinfo is None:
        raise WorldReplayError(f"observed_at must include a timezone on replay fixture line {line_number}")
    return parsed.astimezone(UTC)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise WorldReplayError("replay timestamps must include a timezone")
    return value.astimezone(UTC)


def _max_drawdown(positions: Sequence[_PaperPosition]) -> float:
    cumulative = 0.0
    peak = 0.0
    drawdown = 0.0
    ordered = sorted(
        positions,
        key=lambda position: (
            position.resolved_at or datetime.max.replace(tzinfo=UTC),
            position.entered_at,
        ),
    )
    for position in ordered:
        cumulative += position.net_pnl or 0.0
        peak = max(peak, cumulative)
        drawdown = max(drawdown, peak - cumulative)
    return drawdown


def _round(value: float) -> float:
    return round(float(value), 10)


def _quote_age_seconds(market: WorldMarket, observed_at: datetime) -> float | None:
    if market.updated_at is None:
        return None
    return (observed_at - _utc(market.updated_at)).total_seconds()


def _fill_ratio(market: WorldMarket, config: WorldReplayConfig) -> float:
    sizes = [size for size in (market.yes_ask_size, market.no_ask_size) if size is not None]
    if not sizes:
        return config.unknown_size_fill_ratio
    available_units = min(sizes)
    return min(1.0, available_units / config.target_units)
