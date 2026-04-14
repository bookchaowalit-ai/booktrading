"""
Main entry point for the strategy service.
"""
import logging
import os
import sys
from pathlib import Path

import uvicorn

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config import Config
from infrastructure.api.app import create_app

# ── Structured logging configuration ───────────────────────────────────────────
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}

log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = LOG_LEVELS.get(log_level_name, logging.INFO)

log_format = os.getenv("LOG_FORMAT", "text")

if log_format == "json":
    # JSON structured logging for production
    import json

    class JSONFormatter(logging.Formatter):
        def format(self, record):
            log_entry = {
                "timestamp": self.formatTime(record, self.datefmt),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            if record.exc_info:
                log_entry["exception"] = self.formatException(record.exc_info)
            return json.dumps(log_entry)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
else:
    # Human-readable text logging for development
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    )

root_logger = logging.getLogger()
root_logger.setLevel(log_level)
# Clear default handlers
root_logger.handlers.clear()
root_logger.addHandler(handler)

logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    # Load configuration
    config = Config.from_env()

    logger.info("Starting Trading Strategy Service...")
    logger.info("Redis: %s:%d", config.redis_host, config.redis_port)
    logger.info("API: %s:%d", config.api_host, config.api_port)
    logger.info("Strategy: RSI(%d), EMA(%d)", config.rsi_period, config.ema_period)
    logger.info("Symbols: %s", config.symbols)

    # Log auth status
    auth_token = os.getenv("AUTH_TOKEN")
    if auth_token:
        logger.info("Authentication: ENABLED")
    else:
        logger.warning("Authentication: DISABLED (set AUTH_TOKEN to enable)")

    # Create FastAPI app
    app = create_app(config.to_dict())

    # Run the application
    uvicorn.run(
        app,
        host=config.api_host,
        port=config.api_port,
        log_level=log_level_name.lower(),
    )


if __name__ == "__main__":
    main()
