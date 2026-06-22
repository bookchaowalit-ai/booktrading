"""
Tests for grid_bot.py safety constraints.

Ensures that:
1. Default paper config is conservative (aligned with real_grid_bot.py BTCTHB).
2. validate_grid_config rejects unsafe parameters.
3. Runtime exposure check blocks orders that exceed notional cap.
4. GridBot refuses to start with unsafe configs.
"""

import pytest
from app.grid_bot import (
    GridBot,
    GridConfig,
    safe_paper_defaults,
    validate_grid_config,
    DEFAULT_MAX_NOTIONAL,
)


# ── validate_grid_config ──────────────────────────────────────────────────────

class TestValidateGridConfig:
    def test_safe_config_passes(self):
        cfg = GridConfig(
            symbol="BTCTHB",
            grid_spacing_pct=2.0,
            grid_levels=2,
            order_size=0.00005,
            max_position=0.001,
            max_notional=3000.0,
        )
        violations = validate_grid_config(cfg)
        assert violations == []

    def test_safe_config_with_price_passes(self):
        cfg = GridConfig(
            symbol="BTCTHB",
            grid_spacing_pct=2.0,
            grid_levels=2,
            order_size=0.00005,
            max_position=0.001,
            max_notional=3000.0,
        )
        # 0.001 BTC × ฿2,120,000 = ฿2,120 < ฿3,000 cap
        violations = validate_grid_config(cfg, ref_price=2_120_000.0)
        assert violations == []

    def test_exposure_exceeds_cap(self):
        cfg = GridConfig(
            symbol="BTCUSDT",
            grid_spacing_pct=1.5,
            grid_levels=5,
            order_size=0.001,
            max_position=0.05,       # 0.05 × $60,000 = $3,000
            max_notional=100.0,
        )
        violations = validate_grid_config(cfg, ref_price=60_000.0)
        assert len(violations) == 1
        assert "exceeds cap" in violations[0]
        assert "3,000.00" in violations[0]

    def test_grid_levels_too_high(self):
        cfg = GridConfig(symbol="BTCTHB", grid_levels=10)
        violations = validate_grid_config(cfg)
        assert any("exceeds safety cap" in v for v in violations)

    def test_grid_levels_zero(self):
        cfg = GridConfig(symbol="BTCTHB", grid_levels=0)
        violations = validate_grid_config(cfg)
        assert any("must be >= 1" in v for v in violations)

    def test_negative_order_size(self):
        cfg = GridConfig(symbol="BTCTHB", order_size=-0.001)
        violations = validate_grid_config(cfg)
        assert any("order_size must be > 0" in v for v in violations)

    def test_zero_order_size(self):
        cfg = GridConfig(symbol="BTCTHB", order_size=0)
        violations = validate_grid_config(cfg)
        assert any("order_size must be > 0" in v for v in violations)

    def test_negative_max_position(self):
        cfg = GridConfig(symbol="BTCTHB", max_position=-1.0)
        violations = validate_grid_config(cfg)
        assert any("max_position must be > 0" in v for v in violations)

    def test_spacing_too_tight(self):
        cfg = GridConfig(symbol="BTCTHB", grid_spacing_pct=0.1)
        violations = validate_grid_config(cfg)
        assert any("below minimum 0.5%" in v for v in violations)

    def test_negative_notional_cap(self):
        cfg = GridConfig(symbol="BTCTHB", max_notional=-50.0)
        violations = validate_grid_config(cfg)
        assert any("max_notional must be > 0" in v for v in violations)

    def test_multiple_violations(self):
        cfg = GridConfig(
            symbol="BTCUSDT",
            grid_levels=0,
            order_size=-0.001,
            max_position=-1.0,
            grid_spacing_pct=0.1,
            max_notional=-50.0,
        )
        violations = validate_grid_config(cfg)
        assert len(violations) >= 4


# ── safe_paper_defaults ───────────────────────────────────────────────────────

class TestSafePaperDefaults:
    def test_returns_btcthb_only(self):
        configs = safe_paper_defaults()
        assert len(configs) == 1
        assert configs[0].symbol == "BTCTHB"

    def test_conservative_order_size(self):
        configs = safe_paper_defaults()
        cfg = configs[0]
        assert cfg.order_size == 0.00005  # ~฿106 per order

    def test_conservative_grid_levels(self):
        configs = safe_paper_defaults()
        cfg = configs[0]
        assert cfg.grid_levels == 2

    def test_conservative_max_position(self):
        configs = safe_paper_defaults()
        cfg = configs[0]
        assert cfg.max_position == 0.001  # ~฿2,120 max

    def test_notional_cap_set(self):
        configs = safe_paper_defaults()
        cfg = configs[0]
        assert cfg.max_notional == 3000.0

    def test_defaults_pass_validation(self):
        configs = safe_paper_defaults()
        for cfg in configs:
            violations = validate_grid_config(cfg)
            assert violations == [], f"Default config for {cfg.symbol} has violations: {violations}"

    def test_defaults_pass_with_btcthb_price(self):
        """Validate defaults against realistic BTCTHB price (~฿2.1M)."""
        configs = safe_paper_defaults()
        for cfg in configs:
            violations = validate_grid_config(cfg, ref_price=2_120_000.0)
            assert violations == [], f"Defaults unsafe at BTCTHB price: {violations}"


# ── GridBot startup validation ────────────────────────────────────────────────

class TestGridBotStartup:
    def test_default_bot_uses_safe_config(self):
        bot = GridBot()
        assert len(bot.configs) == 1
        assert bot.configs[0].symbol == "BTCTHB"
        assert bot.configs[0].order_size == 0.00005

    def test_rejects_unsafe_config(self):
        unsafe = [GridConfig(
            symbol="BTCUSDT",
            grid_levels=10,  # exceeds cap
            order_size=0.001,
            max_position=0.05,
        )]
        with pytest.raises(ValueError, match="Unsafe grid config"):
            GridBot(configs=unsafe)

    def test_rejects_oversized_exposure(self):
        oversized = [GridConfig(
            symbol="BTCUSDT",
            grid_spacing_pct=1.5,
            grid_levels=5,
            order_size=0.001,
            max_position=0.05,       # $3,000 at $60K
            max_notional=100.0,      # cap $100
        )]
        # Startup validation is without price, but grid_levels=5 is OK (<=5)
        # The exposure check needs a price — test via validate_grid_config instead
        violations = validate_grid_config(oversized[0], ref_price=60_000.0)
        assert len(violations) > 0
        assert "exceeds cap" in violations[0]

    def test_accepts_explicit_safe_config(self):
        safe = [GridConfig(
            symbol="BTCTHB",
            grid_spacing_pct=2.0,
            grid_levels=2,
            order_size=0.00005,
            max_position=0.001,
            max_notional=3000.0,
        )]
        bot = GridBot(configs=safe)
        assert bot.configs[0].symbol == "BTCTHB"

    def test_max_exposure_under_cap_at_btcthb_price(self):
        """End-to-end: default config max exposure < ฿3,000 at ฿2.1M BTC price."""
        bot = GridBot()
        cfg = bot.configs[0]
        btc_price_thb = 2_120_000.0
        max_exposure_thb = cfg.max_position * btc_price_thb
        assert max_exposure_thb < cfg.max_notional, (
            f"Max exposure ฿{max_exposure_thb:,.2f} exceeds cap ฿{cfg.max_notional:,.2f}"
        )


# ── DEFAULT_MAX_NOTIONAL ──────────────────────────────────────────────────────

class TestNotionalCap:
    def test_default_cap_is_3000(self):
        assert DEFAULT_MAX_NOTIONAL == 3000.0

    def test_cap_applied_to_default_config(self):
        cfg = GridConfig(symbol="BTCTHB")
        assert cfg.max_notional == 3000.0
