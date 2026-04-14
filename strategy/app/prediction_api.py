"""
AI Prediction API Endpoints
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import logging
from app.predictor import predictor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["AI Predictions"])


class PredictionRequest(BaseModel):
    prices: List[float]
    volume: Optional[List[float]] = None
    symbol: Optional[str] = None


class PredictionResponse(BaseModel):
    symbol: Optional[str]
    prediction: str
    confidence: float
    current_price: float
    recommendation: str
    indicators: dict
    message: str


@router.post("/predict", response_model=PredictionResponse)
async def predict_price(request: PredictionRequest):
    """
    Predict price direction using AI/ML analysis
    
    Returns:
    - prediction: BULLISH, BEARISH, or NEUTRAL
    - confidence: 0.0 to 1.0
    - recommendation: BUY, SELL, or HOLD
    """
    try:
        result = predictor.predict(request.prices, request.volume)
        
        # Map prediction to recommendation
        if result['prediction'] == 'BULLISH' and result['confidence'] > 0.6:
            recommendation = "BUY"
        elif result['prediction'] == 'BEARISH' and result['confidence'] > 0.6:
            recommendation = "SELL"
        else:
            recommendation = "HOLD"
        
        return PredictionResponse(
            symbol=request.symbol,
            prediction=result['prediction'],
            confidence=result['confidence'],
            current_price=result.get('current_price', 0),
            recommendation=recommendation,
            indicators=result.get('indicators', {}),
            message=result.get('message', '')
        )
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prediction/{symbol}")
async def get_prediction_for_symbol(symbol: str):
    """
    Get latest prediction for a symbol
    Requires historical data to be loaded
    """
    # This would integrate with your historical data service
    # For now, return placeholder
    return {
        "symbol": symbol,
        "message": "Historical prediction requires data service integration",
        "status": "placeholder"
    }
