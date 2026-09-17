from __future__ import annotations

import pytest

from app.portfolio.models import CapabilityStatus, PlatformCapability, PlatformDomain
from app.portfolio.registry import PlatformRegistry, PlatformRegistryError, default_platform_registry


def test_default_registry_is_deterministic_and_execution_is_disabled():
    registry = default_platform_registry()
    platform_ids = [platform.platform_id for platform in registry.all()]

    assert platform_ids == sorted(platform_ids)
    assert registry.as_dict() == default_platform_registry().as_dict()
    assert registry.as_dict()["execution_enabled"] is False
    assert all(not platform.is_execution_enabled for platform in registry.all())


def test_world_is_paper_blocked_until_read_access_is_approved():
    world = default_platform_registry().get("world_xyz")

    assert world.status is CapabilityStatus.BLOCKED
    assert world.market_data is True
    assert world.paper_trading is True
    assert world.is_paper_ready is False
    assert world.live_execution is False


def test_fomo_is_explicitly_planned_without_invented_api_capabilities():
    fomo = default_platform_registry().get("fomo")

    assert fomo.status is CapabilityStatus.PLANNED
    assert fomo.domain is PlatformDomain.UNKNOWN
    assert fomo.source_url is None
    assert fomo.market_data is False
    assert fomo.paper_trading is False
    assert "official URL" in fomo.next_gate


def test_registry_supports_a_new_platform_without_mutating_the_original():
    original = PlatformRegistry()
    custom = PlatformCapability(
        platform_id="future_venue",
        display_name="Future Venue",
        domain=PlatformDomain.EXCHANGE,
        status=CapabilityStatus.PAPER,
        market_data=True,
        paper_trading=True,
    )

    expanded = original.register(custom)

    assert original.find("future_venue") is None
    assert expanded.get("future_venue") == custom
    with pytest.raises(PlatformRegistryError, match="already registered"):
        expanded.register(custom)


def test_capability_rejects_embedded_credentials_and_secret_values_are_not_model_fields():
    with pytest.raises(ValueError, match="embedded credentials"):
        PlatformCapability(
            platform_id="unsafe",
            display_name="Unsafe",
            domain=PlatformDomain.UNKNOWN,
            status=CapabilityStatus.PLANNED,
            source_url="https://user:password@example.com/venue",
        )

    with pytest.raises(ValueError, match="credential-like query"):
        PlatformCapability(
            platform_id="unsafe-query",
            display_name="Unsafe query",
            domain=PlatformDomain.UNKNOWN,
            status=CapabilityStatus.PLANNED,
            source_url="https://example.com/venue?api_key=do-not-store",
        )
