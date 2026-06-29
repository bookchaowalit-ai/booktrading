"""
Layer 2: Funding Rate Signals
===============================
Uses Bybit's public API for perpetual funding rates.
High positive funding → longs pay shorts → bearish pressure → tighten sells.
High negative funding → shorts pay longs → bullish pressure → tighten buys.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger("brain.funding_rate")

# Bybit v5 public API — no auth needed for ticker
BYBIT_TICKERS = "https://api.bybit.com/v5/market/tickers"
BYBIT_CATEGORY = "linear"  # USDT perpetuals


@dataclass
class FundingSignal:
    """Output from the funding rate layer."""
    symbol: str
    funding_rate: Optional[float] = None      # Current funding rate (e.g. 0.0001 = 0.01%)
    predicted_funding: Optional[float] = None  # Next predicted funding
    open_interest: Optional[float] = None      # Open interest in contracts
    oi_change_pct: Optional[float] = None      # OI change % (24h)

    # Grid modulation outputs
    spacing_multiplier: float = 1.0
    pause_buys: bool = False
    pause_sells: bool = False
    center_offset_pct: float = 0.0
    confidence: float = 0.0


# Mapping from grid bot symbol → Bybit perpetual symbol
SYMBOL_MAP = {
    "BTCUSDT": "BTCUSDT",
    "ETHUSDT": "ETHUSDT",
    "SOLUSDT": "SOLUSDT",
    "BNBUSDT": "BNBUSDT",
    "XRPUSDT": "XRPUSDT",
}


class FundingRateProvider:
    """
    Fetches funding rate data from Bybit and produces grid modulation signals.

    Logic:
    - funding > 0.05% → overleveraged longs → reduce sell spacing (expect pullback)
    - funding < -0.05% → overleveraged shorts → reduce buy spacing (expect bounce)
    - |funding| > 0.1% → extreme → pause counter-trend orders
    - OI spike + high funding → potential squeeze → widen spacing
    """

    def __init__(self):
        self._http: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=10.0)
        return self._http

    async def compute_signal(self, symbol: str) -> FundingSignal:
        """Compute funding rate signal for a symbol."""
        signal = FundingSignal(symbol=symbol)

        bybit_symbol = SYMBOL_MAP.get(symbol)
        if not bybit_symbol:
            # THB pairs don't have perpetual markets
            logger.debug("No Bybit mapping for %s, skipping funding signal", symbol)
            return signal

        client = await self._get_client()

        try:
            resp = await client.get(
                BYBIT_TICKERS,
                params={"category": BYBIT_CATEGORY, "symbol": bybit_symbol},
            )
            if resp.status_code != 200:
                logger.warning("Bybit ticker fetch failed for %s: %d", symbol, resp.status_code)
                return signal

            data = resp.json()
            result = data.get("result", {})
            tickers = result.get("list", [])
            if not tickers:
                logger.debug("No Bybit ticker data for %s", symbol)
                return signal

            ticker = tickers[0]

            # Parse funding rate
            funding_rate = float(ticker.get("fundingRate", 0) or 0)
            signal.funding_rate = funding_rate

            # Parse open interest
            oi = ticker.get("openInterest")
            if oi:
                signal.open_interest = float(oi)

            # ── Funding Rate → Grid Modulation ────────────────────────────
            fr_abs = abs(funding_rate)

            if funding_rate > 0.0005:
                # Extreme positive funding → longs overleveraged
                signal.pause_sells = True   # Don't sell into the squeeze
                signal.center_offset_pct = -0.003  # Shift grid down 0.3%
                signal.confidence = min(0.9, 0.5 + fr_abs * 100)
            elif funding_rate > 0.0001:
                # Moderate positive funding
                signal.spacing_multiplier = 0.85  # Slightly tighter sells
                signal.center_offset_pct = -0.0015  # Shift down 0.15%
                signal.confidence = 0.4
            elif funding_rate < -0.0005:
                # Extreme negative funding → shorts overleveraged
                signal.pause_buys = True    # Don't buy into the squeeze
                signal.center_offset_pct = 0.003   # Shift grid up 0.3%
                signal.confidence = min(0.9, 0.5 + fr_abs * 100)
            elif funding_rate < -0.0001:
                # Moderate negative funding
                signal.spacing_multiplier = 0.85  # Slightly tighter buys
                signal.center_offset_pct = 0.0015  # Shift up 0.15%
                signal.confidence = 0.4
            else:
                # Neutral funding — no strong signal
                signal.confidence = 0.1

            logger.info(
                "[Funding %s] rate=%.4f%% oi=%s → spacing=%.2fx pause_b=%s pause_s=%s "
                "offset=%.1f%% conf=%.2f",
                symbol,
                funding_rate * 100,
                signal.open_interest,
                signal.spacing_multiplier,
                signal.pause_buys,
                signal.pause_sells,
                signal.center_offset_pct,
                signal.confidence,
            )

        except Exception as e:
            logger.warning("Funding rate fetch error for %s: %s", symbol, e)

        return signal

    async def close(self):
        if self._http and not self._http.is_closed:
            await self._http.aclose()
