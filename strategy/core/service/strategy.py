"""
Trading strategy service that generates signals based on composite multi-indicator scoring.
"""
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable

from core.domain.models import (
    MarketData,
    OrderSide,
    OrderSignal,
    StrategyConfig,
    TechnicalIndicators,
    TradeSymbol,
)
from core.service.indicators import TechnicalAnalysisService
from core.service.scoring import CompositeScorer

logger = logging.getLogger(__name__)


class TradingStrategy:
    """
    Composite scoring trading strategy.

    Combines trend (EMA cross + ADX), momentum (MACD + StochRSI),
    volatility (Bollinger Bands), and RSI into a weighted score.
    BUY when composite >  threshold, SELL when composite < -threshold.
    """

    def __init__(
        self,
        config: Optional[StrategyConfig] = None,
        order_executor: Optional[Callable[[OrderSignal], bool]] = None,
    ):
        self.config = config or StrategyConfig()
        self.ta_service = TechnicalAnalysisService(
            rsi_period=self.config.rsi_period,
            ema_period=self.config.ema_period,
            ema_fast_period=self.config.ema_fast_period,
            ema_slow_period=self.config.ema_slow_period,
            macd_fast=self.config.macd_fast,
            macd_slow=self.config.macd_slow,
            macd_signal=self.config.macd_signal,
            bollinger_period=self.config.bollinger_period,
            bollinger_std=self.config.bollinger_std,
            atr_period=self.config.atr_period,
            adx_period=self.config.adx_period,
            roc_period=self.config.roc_period,
            stoch_rsi_period=self.config.stoch_rsi_period,
        )
        self.order_executor = order_executor

        # Store price history for each symbol
        self.price_history: Dict[TradeSymbol, deque] = {
            symbol: deque(maxlen=200)
            for symbol in self.config.symbols
        }

        # Track last signal time to avoid spam
        self.last_signal_time: Dict[TradeSymbol, datetime] = {}
        self.signal_cooldown = 120  # Seconds between signals

    def process_market_data(self, data: MarketData) -> Optional[OrderSignal]:
        """Process incoming market data and generate trading signals."""
        symbol = data.symbol

        # Add to price history
        self.price_history[symbol].append(data)

        # Check if we have enough data for the longest indicator (Bollinger Bands = 20)
        history = list(self.price_history[symbol])
        if len(history) < self.config.bollinger_period + 1:
            return None

        # Calculate all indicators
        indicators = self.ta_service.calculate_all_indicators(symbol, history)

        # Generate composite signal
        signal = self._generate_signal(data, indicators)

        if signal:
            logger.info(
                "Signal generated: %s for %s (Composite: %.3f, Reason: %s)",
                signal.side.value,
                symbol.value,
                signal.strength,
                signal.reason,
            )

        return signal

    def _generate_signal(
        self,
        data: MarketData,
        indicators: TechnicalIndicators,
    ) -> Optional[OrderSignal]:
        """Generate trading signal based on composite scoring."""
        symbol = data.symbol

        # Check cooldown
        if self._is_in_cooldown(symbol):
            return None

        # Calculate composite score
        composite_score, breakdown = CompositeScorer.composite(
            indicators, data.price, self.config
        )

        threshold = self.config.min_composite_score

        # Determine direction
        side = None
        if composite_score > threshold:
            side = OrderSide.BUY
        elif composite_score < -threshold:
            side = OrderSide.SELL

        if side is None:
            return None

        # Build reason string from breakdown
        reason_parts = []
        for component in ("trend", "momentum", "volatility", "rsi"):
            if component in breakdown:
                entry = breakdown[component]
                reason_parts.append(f"{entry['reason']}")

        # Extract key reasons from breakdown
        key_reasons = []
        if breakdown.get("trend", {}).get("reason"):
            key_reasons.append(breakdown["trend"]["reason"])
        if breakdown.get("momentum", {}).get("reason"):
            key_reasons.append(breakdown["momentum"]["reason"])
        if breakdown.get("volatility", {}).get("reason"):
            key_reasons.append(breakdown["volatility"]["reason"])
        if breakdown.get("rsi", {}).get("reason"):
            key_reasons.append(breakdown["rsi"]["reason"])

        reason = f"Score={composite_score:.3f}: " + "; ".join(
            r for r in key_reasons if r
        )

        # Strength = absolute composite score (0.0 to 1.0)
        strength = round(abs(composite_score), 3)

        # Check minimum strength
        if strength < self.config.min_signal_strength:
            return None

        # Update last signal time
        self.last_signal_time[symbol] = datetime.now(timezone.utc)

        signal = OrderSignal(
            symbol=symbol,
            side=side,
            strength=strength,
            reason=reason,
        )

        # Execute order via gRPC if executor is configured
        if self.order_executor:
            logger.info("Executing order via gRPC: %s", signal)
            self.order_executor(signal)

        return signal

    def _is_in_cooldown(self, symbol: TradeSymbol) -> bool:
        """Check if symbol is in signal cooldown period."""
        if symbol not in self.last_signal_time:
            return False

        elapsed = (datetime.now(timezone.utc) - self.last_signal_time[symbol]).total_seconds()
        return elapsed < self.signal_cooldown

    def get_current_indicators(self, symbol: TradeSymbol) -> Optional[TechnicalIndicators]:
        """Get current technical indicators for a symbol."""
        history = list(self.price_history.get(symbol, []))
        if not history:
            return None

        return self.ta_service.calculate_all_indicators(symbol, history)

    def get_price_history(self, symbol: TradeSymbol) -> List[MarketData]:
        """Get price history for a symbol."""
        return list(self.price_history.get(symbol, []))


class MultiSymbolStrategy:
    """Strategy manager for multiple symbols."""

    def __init__(
        self,
        config: Optional[StrategyConfig] = None,
        order_executor: Optional[Callable[[OrderSignal], bool]] = None,
    ):
        self.config = config or StrategyConfig()
        self.strategies: Dict[TradeSymbol, TradingStrategy] = {}
        self.order_executor = order_executor

        # Initialize strategy for each symbol (convert strings to TradeSymbol enum)
        for symbol in self.config.symbols:
            if isinstance(symbol, str):
                try:
                    symbol_enum = TradeSymbol(symbol)
                except ValueError:
                    # Dynamically add new symbol to enum
                    TradeSymbol._value2member_map_[symbol] = TradeSymbol.__new__(TradeSymbol, symbol)
                    TradeSymbol._member_names_.append(symbol)
                    symbol_enum = TradeSymbol(symbol)
                symbol = symbol_enum
            symbol_config = StrategyConfig(
                rsi_period=self.config.rsi_period,
                ema_period=self.config.ema_period,
                rsi_oversold=self.config.rsi_oversold,
                rsi_overbought=self.config.rsi_overbought,
                min_signal_strength=self.config.min_signal_strength,
                weight_trend=self.config.weight_trend,
                weight_momentum=self.config.weight_momentum,
                weight_volatility=self.config.weight_volatility,
                weight_rsi=self.config.weight_rsi,
                ema_fast_period=self.config.ema_fast_period,
                ema_slow_period=self.config.ema_slow_period,
                macd_fast=self.config.macd_fast,
                macd_slow=self.config.macd_slow,
                macd_signal=self.config.macd_signal,
                bollinger_period=self.config.bollinger_period,
                bollinger_std=self.config.bollinger_std,
                atr_period=self.config.atr_period,
                adx_period=self.config.adx_period,
                roc_period=self.config.roc_period,
                stoch_rsi_period=self.config.stoch_rsi_period,
                adx_min_trend=self.config.adx_min_trend,
                min_composite_score=self.config.min_composite_score,
                symbols=[symbol],
            )
            self.strategies[symbol] = TradingStrategy(
                symbol_config,
                order_executor=order_executor,
            )

    def process_market_data(self, data: MarketData) -> Optional[OrderSignal]:
        """Process market data for the corresponding symbol."""
        if data.symbol not in self.strategies:
            logger.warning("No strategy for symbol: %s", data.symbol)
            return None

        return self.strategies[data.symbol].process_market_data(data)

    def get_all_indicators(self) -> Dict[TradeSymbol, TechnicalIndicators]:
        """Get current indicators for all symbols."""
        return {
            symbol: strategy.get_current_indicators(symbol)
            for symbol, strategy in self.strategies.items()
        }


class MultiSymbolStrategyWithGRPC(MultiSymbolStrategy):
    """Multi-symbol strategy with gRPC order execution."""

    def __init__(
        self,
        order_executor: Callable[[OrderSignal], bool],
        config: Optional[StrategyConfig] = None,
    ):
        super().__init__(config=config, order_executor=order_executor)
