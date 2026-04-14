"""
Tests for strategy configuration and signal generation.
"""
import pytest
from pydantic import ValidationError

# Import from the strategy service
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.api.app import StrategyConfigRequest


class TestStrategyConfigRequest:
    """Tests for Pydantic config validation."""

    def test_valid_config(self):
        config = StrategyConfigRequest(
            rsi_period=14,
            ema_period=14,
            rsi_oversold=30.0,
            rsi_overbought=70.0,
            min_signal_strength=0.5,
        )
        assert config.rsi_period == 14
        assert config.rsi_oversold == 30.0
        assert config.rsi_overbought == 70.0

    def test_negative_rsi_period_rejected(self):
        with pytest.raises(ValidationError):
            StrategyConfigRequest(rsi_period=-1)

    def test_zero_rsi_period_rejected(self):
        with pytest.raises(ValidationError):
            StrategyConfigRequest(rsi_period=0)

    def test_rsi_oversold_greater_than_overbought_rejected(self):
        with pytest.raises(ValueError, match="rsi_oversold must be less than rsi_overbought"):
            StrategyConfigRequest(rsi_oversold=70.0, rsi_overbought=30.0)

    def test_zero_min_signal_strength_rejected(self):
        with pytest.raises(ValidationError):
            StrategyConfigRequest(min_signal_strength=0)

    def test_negative_min_signal_strength_rejected(self):
        with pytest.raises(ValidationError):
            StrategyConfigRequest(min_signal_strength=-0.5)

    def test_strength_greater_than_one_rejected(self):
        with pytest.raises(ValidationError):
            StrategyConfigRequest(min_signal_strength=1.1)

    def test_default_values(self):
        config = StrategyConfigRequest()
        assert config.rsi_period == 14
        assert config.ema_period == 14
        assert config.rsi_oversold == 30.0
        assert config.rsi_overbought == 70.0
        assert config.min_signal_strength == 0.5

    def test_oversold_equal_to_overbought_rejected(self):
        with pytest.raises(ValueError, match="rsi_oversold must be less than rsi_overbought"):
            StrategyConfigRequest(rsi_oversold=50.0, rsi_overbought=50.0)
