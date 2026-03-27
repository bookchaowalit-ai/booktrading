"""
Main entry point for the strategy service.
"""
import asyncio
import logging
import sys
from pathlib import Path

import uvicorn

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config import Config
from infrastructure.api.app import create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    # Load configuration
    config = Config.from_env()
    
    logger.info("Starting Trading Strategy Service...")
    logger.info(f"Redis: {config.redis_host}:{config.redis_port}")
    logger.info(f"API: {config.api_host}:{config.api_port}")
    logger.info(f"Strategy: RSI({config.rsi_period}), EMA({config.ema_period})")
    logger.info(f"Symbols: {config.symbols}")
    
    # Create FastAPI app
    app = create_app(config.to_dict())
    
    # Run the application
    uvicorn.run(
        app,
        host=config.api_host,
        port=config.api_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
