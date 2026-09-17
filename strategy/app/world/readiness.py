"""Read-only live readiness checks for the World Markets lane."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from app.market_intel.sources.world import WorldSource
from app.world.client import WorldApiError, WorldMarketsClient, WorldMarketsConfig
from app.world.landing import WorldLandingWriter
from app.world.scanner import WorldPaperScanner


@dataclass(frozen=True, slots=True)
class WorldReadinessReport:
    """A safe summary with no response payloads or credential values."""

    api_base: str
    ws_url: str
    lake_status: str
    api_status: str
    api_status_code: int | None
    parser_status: str
    market_count: int
    quality_eligible_market_count: int
    invalid_market_count: int
    incomplete_resolution_count: int
    paper_signal_count: int
    error_class: str | None
    ready_for_paper: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": "world_xyz",
            "mode": "live_readiness_check",
            "execution_enabled": False,
            "api_base": self.api_base,
            "ws_url": self.ws_url,
            "lake_status": self.lake_status,
            "api_status": self.api_status,
            "api_status_code": self.api_status_code,
            "parser_status": self.parser_status,
            "market_count": self.market_count,
            "quality_eligible_market_count": self.quality_eligible_market_count,
            "invalid_market_count": self.invalid_market_count,
            "incomplete_resolution_count": self.incomplete_resolution_count,
            "paper_signal_count": self.paper_signal_count,
            "error_class": self.error_class,
            "ready_for_paper": self.ready_for_paper,
        }


async def check_world_readiness(
    config: WorldMarketsConfig,
    *,
    landing_writer: WorldLandingWriter | None,
    scanner: WorldPaperScanner | None = None,
    client: WorldMarketsClient | None = None,
    page_limit: int = 1,
    category: str | None = None,
    tags: Sequence[str] | None = None,
    require_landing: bool = True,
) -> WorldReadinessReport:
    """Probe one bounded page and validate the normalized result path."""

    safe_api_base = _safe_url(config.api_base)
    safe_ws_url = _safe_url(config.ws_url)
    if require_landing and landing_writer is None:
        return WorldReadinessReport(
            api_base=safe_api_base,
            ws_url=safe_ws_url,
            lake_status="blocked_missing_landing",
            api_status="not_run",
            api_status_code=None,
            parser_status="not_run",
            market_count=0,
            quality_eligible_market_count=0,
            invalid_market_count=0,
            incomplete_resolution_count=0,
            paper_signal_count=0,
            error_class="landing_not_configured",
            ready_for_paper=False,
        )

    active_client = client or WorldMarketsClient(config)
    active_scanner = scanner or WorldPaperScanner()
    source = WorldSource(
        config=config,
        client=active_client,
        landing_writer=landing_writer,
        scanner=active_scanner,
        page_limit=page_limit,
        max_pages=1,
        category=category,
        tags=tags,
        use_env_landing=False,
        require_landing=require_landing,
    )
    try:
        markets = await source.fetch_markets()
    except WorldApiError as exc:
        return WorldReadinessReport(
            api_base=safe_api_base,
            ws_url=safe_ws_url,
            lake_status="not_run" if landing_writer is not None else "skipped_explicit_no_lake",
            api_status="blocked",
            api_status_code=exc.status_code,
            parser_status="not_run",
            market_count=0,
            quality_eligible_market_count=0,
            invalid_market_count=0,
            incomplete_resolution_count=0,
            paper_signal_count=0,
            error_class=type(exc).__name__,
            ready_for_paper=False,
        )
    except RuntimeError as exc:
        return WorldReadinessReport(
            api_base=safe_api_base,
            ws_url=safe_ws_url,
            lake_status="blocked",
            api_status="unknown_after_fetch",
            api_status_code=None,
            parser_status="not_run",
            market_count=0,
            quality_eligible_market_count=0,
            invalid_market_count=0,
            incomplete_resolution_count=0,
            paper_signal_count=0,
            error_class=type(exc).__name__,
            ready_for_paper=False,
        )
    finally:
        if client is None:
            await active_client.close()

    quality_eligible = sum(1 for market in markets if active_scanner.is_eligible(market))
    invalid_count = sum(bool(market.validation_errors) for market in markets)
    incomplete_resolution_count = sum(bool(market.resolution_errors) for market in markets)
    paper_signals = active_scanner.scan(markets)
    return WorldReadinessReport(
        api_base=safe_api_base,
        ws_url=safe_ws_url,
        lake_status="passed" if landing_writer is not None else "skipped_explicit_no_lake",
        api_status="passed",
        api_status_code=200,
        parser_status="passed",
        market_count=len(markets),
        quality_eligible_market_count=quality_eligible,
        invalid_market_count=invalid_count,
        incomplete_resolution_count=incomplete_resolution_count,
        paper_signal_count=len(paper_signals),
        error_class=None,
        ready_for_paper=landing_writer is not None and quality_eligible > 0,
    )


def _safe_url(value: str) -> str:
    parsed = urlsplit(value)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
