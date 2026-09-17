"""Capability registry for World, Fomo, and future venues."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app.portfolio.models import CapabilityStatus, PlatformCapability, PlatformDomain

REGISTRY_VERSION = 1


class PlatformRegistryError(ValueError):
    """Raised when a platform capability record cannot be registered."""


@dataclass(frozen=True, slots=True)
class PlatformRegistry:
    """Deterministic in-process registry with no network or credential access."""

    _platforms: dict[str, PlatformCapability]

    def __init__(self, platforms: Iterable[PlatformCapability] = ()) -> None:
        entries: dict[str, PlatformCapability] = {}
        for platform in platforms:
            self._add(entries, platform, replace=False)
        object.__setattr__(self, "_platforms", entries)

    @staticmethod
    def _add(
        entries: dict[str, PlatformCapability],
        platform: PlatformCapability,
        *,
        replace: bool,
    ) -> None:
        if not isinstance(platform, PlatformCapability):
            raise PlatformRegistryError("platform must be a PlatformCapability")
        if platform.platform_id in entries and not replace:
            raise PlatformRegistryError(f"platform already registered: {platform.platform_id}")
        entries[platform.platform_id] = platform

    def register(self, platform: PlatformCapability, *, replace: bool = False) -> PlatformRegistry:
        """Return a new registry containing ``platform``."""

        entries = dict(self._platforms)
        self._add(entries, platform, replace=replace)
        return PlatformRegistry(entries.values())

    def get(self, platform_id: str) -> PlatformCapability:
        return self._platforms[platform_id.lower()]

    def find(self, platform_id: str) -> PlatformCapability | None:
        return self._platforms.get(platform_id.lower())

    def all(self) -> tuple[PlatformCapability, ...]:
        return tuple(self._platforms[key] for key in sorted(self._platforms))

    def paper_ready(self) -> tuple[PlatformCapability, ...]:
        return tuple(platform for platform in self.all() if platform.is_paper_ready)

    def as_dict(self) -> dict[str, Any]:
        return {
            "registry_version": REGISTRY_VERSION,
            "execution_enabled": False,
            "platforms": [platform.as_dict() for platform in self.all()],
        }


def default_platform_registry() -> PlatformRegistry:
    """Return the current built-in integration map.

    Entries report delivery state, not profitability, approval, or permission
    to move funds.  In particular, Fomo remains a placeholder until its
    official URL and permitted API contract are known.
    """

    return PlatformRegistry(
        (
            PlatformCapability(
                platform_id="airdrop_rewards",
                display_name="Airdrop & Rewards Sources",
                domain=PlatformDomain.REWARDS,
                status=CapabilityStatus.READ_ONLY,
                rewards_tracking=True,
                notes=(
                    "Tracks candidate, eligible, and claimed rewards separately from paper P&L; "
                    "estimated values are not cash."
                ),
                next_gate="Attach source evidence and claim proof before treating a reward as realized",
            ),
            PlatformCapability(
                platform_id="binance_global",
                display_name="Binance Global",
                domain=PlatformDomain.EXCHANGE,
                status=CapabilityStatus.TESTNET,
                market_data=True,
                paper_trading=True,
                testnet_execution=True,
                source_url="https://www.binance.com",
                notes="Existing strategy surfaces support research/paper or testnet workflows; live execution is disabled.",
                next_gate="Independent testnet reconciliation and risk approval",
            ),
            PlatformCapability(
                platform_id="binance_th",
                display_name="Binance TH",
                domain=PlatformDomain.EXCHANGE,
                status=CapabilityStatus.PAPER,
                market_data=True,
                paper_trading=True,
                source_url="https://www.binance.th",
                notes="Paper-only registry entry until a separately reviewed execution adapter exists.",
                next_gate="Define venue-specific order, balance, and compliance contract",
            ),
            PlatformCapability(
                platform_id="bitkub",
                display_name="Bitkub",
                domain=PlatformDomain.EXCHANGE,
                status=CapabilityStatus.PAPER,
                market_data=True,
                paper_trading=True,
                source_url="https://www.bitkub.com",
                notes="Paper-only registry entry; no live permission is implied.",
                next_gate="Define venue-specific order, balance, and compliance contract",
            ),
            PlatformCapability(
                platform_id="fomo",
                display_name="Fomo (unverified)",
                domain=PlatformDomain.UNKNOWN,
                status=CapabilityStatus.PLANNED,
                notes="Placeholder only. No API, order, wallet, or reward semantics are assumed.",
                next_gate="Confirm the official URL, API documentation, access permission, and settlement model",
            ),
            PlatformCapability(
                platform_id="polymarket",
                display_name="Polymarket",
                domain=PlatformDomain.PREDICTION,
                status=CapabilityStatus.PAPER,
                market_data=True,
                paper_trading=True,
                source_url="https://polymarket.com",
                notes="Existing prediction-market analysis is treated as paper/research until execution gates pass.",
                next_gate="Keep paper reconciliation and venue policy checks green",
            ),
            PlatformCapability(
                platform_id="world_xyz",
                display_name="World Markets",
                domain=PlatformDomain.PREDICTION,
                status=CapabilityStatus.BLOCKED,
                market_data=True,
                paper_trading=True,
                source_url="https://world.xyz/markets",
                notes=(
                    "Read-only adapter and offline replay exist, but the bounded live readiness probe returned "
                    "HTTP 403 without approved access."
                ),
                next_gate="Obtain approved read access, then validate quote, size, and settlement fields",
            ),
        )
    )
