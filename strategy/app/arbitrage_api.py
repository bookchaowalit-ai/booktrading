"""
Arbitrage API Endpoints
"""

from fastapi import APIRouter
from typing import List, Optional
from app.arbitrage import detector

router = APIRouter(prefix="/api/arbitrage", tags=["Arbitrage Detection"])


@router.get("/opportunities")
async def get_opportunities(limit: int = 10):
    """Get recent arbitrage opportunities"""
    return {
        "opportunities": detector.get_opportunities(limit),
        "count": len(detector.opportunities)
    }


@router.get("/opportunity/{symbol}")
async def get_best_opportunity(symbol: str):
    """Get best arbitrage opportunity for a specific symbol"""
    opp = detector.get_best_opportunity(symbol)
    
    if opp:
        return {
            "symbol": symbol,
            "opportunity": opp,
            "recommended_action": f"Buy on {opp['buy_exchange']}, Sell on {opp['sell_exchange']}"
        }
    else:
        return {
            "symbol": symbol,
            "opportunity": None,
            "message": "No arbitrage opportunity found"
        }


@router.post("/update-price")
async def update_price(exchange: str, symbol: str, price: float, volume: float = 0):
    """Update price from an exchange"""
    detector.update_price(exchange, symbol, price, volume)
    return {"status": "ok", "message": "Price updated"}
