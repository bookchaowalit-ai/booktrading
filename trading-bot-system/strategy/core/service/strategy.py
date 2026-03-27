"""
Trading strategy service that generates signals based on technical indicators.
"""
import logging
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Callable

from core.domain.models import (
    MarketData,
    OrderSide,
    OrderSignal,
    StrategyConfig,
    TechnicalIndicators,
    TradeSymbol,
)
from core.service.indicators import (
    SignalStrengthCalculator,
    TechnicalAnalysisService,
)

logger = logging.getLogger(__name__)


class TradingStrategy:
    """
    Main trading strategy implementation.
    
    Logic:
    - If RSI < 30 (oversold): Generate BUY signal
    - If RSI > 70 (overbought): Generate SELL signal
    - Use EMA for trend confirmation
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
        )
        self.order_executor = order_executor  # gRPC callback
        
        # Store price history for each symbol
        self.price_history: Dict[TradeSymbol, deque] = {
            symbol: deque(maxlen=100)  # Keep last 100 data points
            for symbol in self.config.symbols
        }
        
        # Track last signal time to avoid spam
        self.last_signal_time: Dict[TradeSymbol, datetime] = {}
        self.signal_cooldown = 60  # Seconds between signals
    
    def process_market_data(self, data: MarketData) -> Optional[OrderSignal]:
        """
        Process incoming market data and generate trading signals.
        """
        symbol = data.symbol
        
        # Add to price history
        self.price_history[symbol].append(data)
        
        # Check if we have enough data
        history = list(self.price_history[symbol])
        if len(history) < self.config.rsi_period + 1:
            return None
        
        # Calculate indicators
        indicators = self.ta_service.calculate_all_indicators(symbol, history)
        
        # Generate signal based on RSI
        signal = self._generate_signal(data, indicators)
        
        if signal:
            logger.info(
                f"Signal generated: {signal.side.value} for {symbol.value} "
                f"(RSI: {indicators.rsi}, Strength: {signal.strength})"
            )
        
        return signal
    
    def _generate_signal(
        self, 
        data: MarketData, 
        indicators: TechnicalIndicators
    ) -> Optional[OrderSignal]:
        """
        Generate trading signal based on indicators.
        """
        symbol = data.symbol
        rsi = indicators.rsi
        
        if rsi is None:
            return None
        
        # Check cooldown
        if self._is_in_cooldown(symbol):
            return None
        
        side = None
        reason = ""
        
        # RSI-based signals
        if rsi < self.config.rsi_oversold:
            side = OrderSide.BUY
            reason = f"RSI oversold ({rsi:.2f} < {self.config.rsi_oversold})"
        elif rsi > self.config.rsi_overbought:
            side = OrderSide.SELL
            reason = f"RSI overbought ({rsi:.2f} > {self.config.rsi_overbought})"
        
        if side is None:
            return None
        
        # Calculate signal strength
        strength = SignalStrengthCalculator.calculate_combined_strength(
            rsi=rsi,
            ema=indicators.ema,
            current_price=data.price,
        )
        
        # Check minimum strength
        if strength < self.config.min_signal_strength:
            return None
        
        # Update last signal time
        self.last_signal_time[symbol] = datetime.now()
        
        signal = OrderSignal(
            symbol=symbol,
            side=side,
            strength=strength,
            reason=reason,
        )
        
        # Execute order via gRPC if executor is configured
        if self.order_executor:
            logger.info(f"Executing order via gRPC: {signal}")
            self.order_executor(signal)
        
        return signal
    
    def _is_in_cooldown(self, symbol: TradeSymbol) -> bool:
        """Check if symbol is in signal cooldown period."""
        if symbol not in self.last_signal_time:
            return False
        
        elapsed = (datetime.now() - self.last_signal_time[symbol]).total_seconds()
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
    """
    Strategy manager for multiple symbols.
    """
    
    def __init__(
        self, 
        config: Optional[StrategyConfig] = None,
        order_executor: Optional[Callable[[OrderSignal], bool]] = None,
    ):
        self.config = config or StrategyConfig()
        self.strategies: Dict[TradeSymbol, TradingStrategy] = {}
        self.order_executor = order_executor
        
        # Initialize strategy for each symbol
        for symbol in self.config.symbols:
            symbol_config = StrategyConfig(
                rsi_period=self.config.rsi_period,
                ema_period=self.config.ema_period,
                rsi_oversold=self.config.rsi_oversold,
                rsi_overbought=self.config.rsi_overbought,
                symbols=[symbol],
            )
            self.strategies[symbol] = TradingStrategy(
                symbol_config, 
                order_executor=order_executor,
            )
    
    def process_market_data(self, data: MarketData) -> Optional[OrderSignal]:
        """Process market data for the corresponding symbol."""
        if data.symbol not in self.strategies:
            logger.warning(f"No strategy for symbol: {data.symbol}")
            return None
        
        return self.strategies[data.symbol].process_market_data(data)
    
    def get_all_indicators(self) -> Dict[TradeSymbol, TechnicalIndicators]:
        """Get current indicators for all symbols."""
        return {
            symbol: strategy.get_current_indicators(symbol)
            for symbol, strategy in self.strategies.items()
        }


class MultiSymbolStrategyWithGRPC(MultiSymbolStrategy):
    """
    Multi-symbol strategy with gRPC order execution.
    """
    
    def __init__(self, order_executor: Callable[[OrderSignal], bool]):
        super().__init__(order_executor=order_executor)
