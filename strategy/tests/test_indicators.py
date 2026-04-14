"""
Tests for the technical analysis service (RSI, EMA, SMA, MACD).
"""
import math
from core.service.indicators import TechnicalAnalysisService


class TestRSI:
    """Tests for RSI calculation."""

    def setup_method(self):
        self.ta = TechnicalAnalysisService(rsi_period=14)

    def test_rsi_constant_prices(self):
        """RSI should be 50 when prices are constant (no losses, no gains)."""
        prices = [100.0] * 20
        rsi = self.ta.calculate_rsi(prices)
        assert rsi is not None
        assert math.isclose(rsi, 50.0, abs_tol=1.0), f"RSI={rsi}, expected ~50"

    def test_rsi_rising_prices(self):
        """RSI should be high (near 100) when prices consistently rise."""
        prices = [float(i) for i in range(1, 30)]
        rsi = self.ta.calculate_rsi(prices)
        assert rsi is not None
        assert rsi > 80, f"RSI={rsi}, expected >80 for rising prices"

    def test_rsi_falling_prices(self):
        """RSI should be low (near 0) when prices consistently fall."""
        prices = [float(30 - i) for i in range(30)]
        rsi = self.ta.calculate_rsi(prices)
        assert rsi is not None
        assert rsi < 20, f"RSI={rsi}, expected <20 for falling prices"

    def test_rsi_insufficient_data(self):
        """RSI should return None when there's not enough data."""
        prices = [100.0, 101.0]
        rsi = self.ta.calculate_rsi(prices)
        assert rsi is None

    def test_rsi_empty_prices(self):
        """RSI should return None for empty prices."""
        rsi = self.ta.calculate_rsi([])
        assert rsi is None


class TestEMA:
    """Tests for EMA calculation."""

    def setup_method(self):
        self.ta = TechnicalAnalysisService(ema_period=5)

    def test EMA_constant_prices(self):
        """EMA of constant prices should equal the constant value."""
        prices = [100.0] * 20
        ema = self.ta.calculate_ema(prices)
        assert ema is not None
        assert math.isclose(ema, 100.0, abs_tol=0.01), f"EMA={ema}, expected 100"

    def test_ema_insufficient_data(self):
        """EMA should return None with insufficient data."""
        prices = [100.0]
        ema = self.ta.calculate_ema(prices)
        assert ema is None

    def test_ema_empty_prices(self):
        """EMA should return None for empty prices."""
        ema = self.ta.calculate_ema([])
        assert ema is None


class TestSMA:
    """Tests for SMA calculation."""

    def setup_method(self):
        self.ta = TechnicalAnalysisService(ema_period=5)

    def test_sma_constant_prices(self):
        """SMA of constant prices should equal the constant value."""
        prices = [100.0] * 20
        sma = self.ta.calculate_sma(prices, period=5)
        assert sma is not None
        assert math.isclose(sma, 100.0, abs_tol=0.01), f"SMA={sma}, expected 100"


class TestMACD:
    """Tests for MACD calculation."""

    def setup_method(self):
        self.ta = TechnicalAnalysisService()

    def test_macd_constant_prices(self):
        """MACD of constant prices should be near 0."""
        prices = [100.0] * 50
        macd = self.ta.calculate_macd(prices)
        assert macd is not None
        assert math.isclose(macd, 0.0, abs_tol=1.0), f"MACD={macd}, expected ~0"


class TestCalculateAllIndicators:
    """Tests for the combined indicator calculation."""

    def setup_method(self):
        from core.domain.models import TradeSymbol
        self.ta = TechnicalAnalysisService(rsi_period=14, ema_period=14)

    def test_calculate_all_indicators_with_sufficient_data(self):
        from core.domain.models import MarketData
        import datetime
        symbol = TradeSymbol.BTCUSDT

        prices = [40000 + i * 100 for i in range(30)]
        history = [
            MarketData(
                symbol=symbol,
                price=p,
                high=p + 50,
                low=p - 50,
                open=p - 10,
                volume=1000.0,
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
            for p in prices
        ]

        indicators = self.ta.calculate_all_indicators(symbol, history)
        assert indicators is not None
        assert indicators.rsi is not None
        assert indicators.ema is not None
