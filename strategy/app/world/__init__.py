"""Read-only World Markets adapter and paper-research helpers."""

from app.world.client import (
    DEFAULT_API_BASE,
    DEFAULT_WS_URL,
    WorldApiError,
    WorldEventPage,
    WorldMarketsClient,
    WorldMarketsConfig,
    parse_price_tick,
    parse_world_market,
)
from app.world.models import WorldMarket, WorldPaperSignal, WorldPriceTick
from app.world.replay import (
    WorldReplayConfig,
    WorldReplayError,
    WorldReplayFrame,
    WorldReplayReport,
    WorldReplayRunner,
    WorldSettlement,
    load_replay_fixture,
)
from app.world.scanner import WorldPaperScanner, WorldScannerConfig

__all__ = [
    "DEFAULT_API_BASE",
    "DEFAULT_WS_URL",
    "WorldApiError",
    "WorldEventPage",
    "WorldLandingWriter",
    "WorldMarket",
    "WorldMarketsClient",
    "WorldMarketsConfig",
    "WorldPaperScanner",
    "WorldPaperSignal",
    "WorldPriceTick",
    "WorldReadinessReport",
    "WorldReplayConfig",
    "WorldReplayError",
    "WorldReplayFrame",
    "WorldReplayReport",
    "WorldReplayRunner",
    "WorldScannerConfig",
    "WorldSettlement",
    "check_world_readiness",
    "load_replay_fixture",
    "parse_price_tick",
    "parse_world_market",
]


def __getattr__(name: str):
    """Load the lake writer lazily to keep ``app.world`` import-cycle safe."""

    if name == "WorldLandingWriter":
        from app.world.landing import WorldLandingWriter

        return WorldLandingWriter
    if name in {"WorldReadinessReport", "check_world_readiness"}:
        from app.world.readiness import WorldReadinessReport, check_world_readiness

        return {"WorldReadinessReport": WorldReadinessReport, "check_world_readiness": check_world_readiness}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
