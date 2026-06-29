"""
Brain — Intelligence layer for signal-driven grid modulation.

Three-layer architecture:
  Layer 1: Technical indicators (ATR, RSI, Bollinger)
  Layer 2: On-chain signals (funding rate, open interest)
  Layer 3: Sentiment analysis (CryptoPanic + LLM)

The Brain outputs a GridDirective per symbol:
  - spacing_multiplier: adjust grid width (0.5x = tighter, 2.0x = wider)
  - center_offset_pct: shift grid center up/down
  - pause_buys: halt new buy orders
  - pause_sells: halt new sell orders
  - confidence: 0.0-1.0 signal confidence
"""
