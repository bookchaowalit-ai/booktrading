"""
Layer 1: Technical Indicator Signals
=====================================
Uses ATR for dynamic grid spacing, RSI for buy/sell filtering,
and Bollinger Bands for range detection.

All calculations use the existing TechnicalAnalysisService from
core/service/indicators.py — this module just wraps it for Brain integration.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

import httpx

from core.service.indicators import TechnicalAnalysisService

logger = logging.getLogger("brain.technical")

# Mapping from grid bot symbol to Binance kline symbol
# THB pairs use Binance TH, USDT pairs use Binance Global
BINANCE_TH_KLINES = "https://api.binance.th/api/v1/klines"
BINANCE_GLOBAL_KLINES = "https://api.binance.com/api/v3/klines"


@dataclass
class TechnicalSignal:
    """Output from the technical signal layer."""
    symbol: str
    atr_pct: Optional[float] = None          # ATR as % of price (volatility)
    rsi: Optional[float] = None              # RSI(14)
    bb_position: Optional[float] = None      # Position within BB: 0=lower, 0.5=mid, 1=upper
    ema_trend: Optional[str] = None          # "bullish" | "bearish" | "neutral"

    # Grid modulation outputs
    spacing_multiplier: float = 1.0          # 0.5=tighter, 1.0=normal, 2.0=wider
    pause_buys: bool = False                 # RSI overbought → pause buys
    pause_sells: bool = False                # RSI oversold → pause sells
    center_offset_pct: float = 0.0           # Shift grid center (positive=up)

    confidence: float = 0.0                  # 0-1 signal confidence


class TechnicalSignalProvider:
    """
    Fetches kline data and computes technical signals for grid modulation.
    """

    def __init__(self, ta_service: Optional[TechnicalAnalysisService] = None):
        self.ta = ta_service or TechnicalAnalysisService()
        self._http: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=10.0)
        return self._http

    async def fetch_kline_closes(self, symbol: str, interval: str = "15m", limit: int = 100) -> List[float]:
        """Fetch recent close prices from Binance klines."""
        client = await self._get_client()

        if symbol.endswith("THB"):
            url = BINANCE_TH_KLINES
        else:
            url = BINANCE_GLOBAL_KLINES

        try:
            resp = await client.get(url, params={
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
            })
            if resp.status_code == 200:
                klines = resp.json()
                # klines format: [open_time, open, high, low, close, volume, ...]
                return [float(k[4]) for k in klines]
            else:
                logger.warning("Kline fetch failed for %s: %d", symbol, resp.status_code)
        except Exception as e:
            logger.warning("Kline fetch error for %s: %s", symbol, e)

        return []

    async def compute_signal(self, symbol: str) -> TechnicalSignal:
        """
        Compute technical signal for a symbol.

        Logic:
        - ATR → spacing_multiplier: low vol = tighter grids, high vol = wider
        - RSI > 75 → pause buys (overbought, likely to pull back)
        - RSI < 25 → pause sells (oversold, likely to bounce)
        - BB position → center_offset: shift grid toward the mean
        - EMA cross → trend confirmation
        """
        closes = await self.fetch_kline_closes(symbol)

        signal = TechnicalSignal(symbol=symbol)

        if len(closes) < 30:
            logger.debug("Insufficient kline data for %s (%d candles)", symbol, len(closes))
            return signal

        current_price = closes[-1]

        # ── ATR → Dynamic Spacing ───────────────────────────────────────────
        atr_pct = self.ta.calculate_atr(closes, period=14)
        if atr_pct is not None:
            signal.atr_pct = atr_pct
            # ATR baseline for crypto: ~1-3% on 15m candles
            # Low vol (< 0.5%): tighten to 0.7x
            # Normal vol (0.5-2%): keep 1.0x
            # High vol (> 2%): widen to 1.5x
            # Extreme vol (> 4%): widen to 2.0x
            if atr_pct < 0.005:
                signal.spacing_multiplier = 0.7
            elif atr_pct < 0.02:
                signal.spacing_multiplier = 1.0
            elif atr_pct < 0.04:
                signal.spacing_multiplier = 1.5
            else:
                signal.spacing_multiplier = 2.0

        # ── RSI → Buy/Sell Filter ───────────────────────────────────────────
        rsi = self.ta.calculate_rsi(closes, period=14)
        if rsi is not None:
            signal.rsi = rsi
            if rsi > 75:
                signal.pause_buys = True    # Overbought — don't buy the top
                signal.center_offset_pct = -0.005  # Shift grid down 0.5%
            elif rsi < 25:
                signal.pause_sells = True   # Oversold — don't sell the bottom
                signal.center_offset_pct = 0.005   # Shift grid up 0.5%

        # ── Bollinger Bands → Center Offset ─────────────────────────────────
        bb_upper, bb_mid, bb_lower = self.ta.calculate_bollinger_bands(closes, period=20)
        if bb_upper and bb_mid and bb_lower and (bb_upper - bb_lower) > 0:
            bb_position = (current_price - bb_lower) / (bb_upper - bb_lower)
            signal.bb_position = round(bb_position, 3)

            # If price near upper band (>0.8) → shift grid down (expect mean reversion)
            # If price near lower band (<0.2) → shift grid up
            if bb_position > 0.85:
                signal.center_offset_pct = -0.003  # Shift down 0.3%
            elif bb_position < 0.15:
                signal.center_offset_pct = 0.003   # Shift up 0.3%

        # ── EMA Trend ───────────────────────────────────────────────────────
        ema_fast, ema_slow, cross = self.ta.calculate_ema_cross(closes, fast_period=9, slow_period=21)
        if ema_fast is not None and ema_slow is not None:
            if ema_fast > ema_slow * 1.001:
                signal.ema_trend = "bullish"
            elif ema_fast < ema_slow * 0.999:
                signal.ema_trend = "bearish"
            else:
                signal.ema_trend = "neutral"

        # ── Confidence ──────────────────────────────────────────────────────
        # Higher confidence when multiple signals agree
        signals_active = sum([
            signal.atr_pct is not None,
            signal.rsi is not None,
            signal.bb_position is not None,
            signal.ema_trend is not None,
        ])
        signal.confidence = round(signals_active / 4.0, 2)

        logger.info(
            "[Technical %s] atr=%.3f%% rsi=%.1f bb_pos=%.2f trend=%s "
            "→ spacing=%.1fx pause_b=%s pause_s=%s offset=%.1f%% conf=%.2f",
            symbol,
            (signal.atr_pct or 0) * 100,
            signal.rsi or 50,
            signal.bb_position or 0.5,
            signal.ema_trend or "unknown",
            signal.spacing_multiplier,
            signal.pause_buys,
            signal.pause_sells,
            signal.center_offset_pct,
            signal.confidence,
        )

        return signal

    async def close(self):
        if self._http and not self._http.is_closed:
            await self._http.aclose()
