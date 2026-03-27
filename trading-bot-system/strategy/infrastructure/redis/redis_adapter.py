"""
Redis adapter for subscribing to market data and publishing order signals.
"""
import asyncio
import json
import logging
from typing import Callable, Optional

import redis.asyncio as redis

from core.domain.models import MarketData, OrderSignal, TradeSymbol

logger = logging.getLogger(__name__)


class RedisAdapter:
    """Adapter for Redis pub/sub operations."""
    
    def __init__(
        self, 
        host: str = "localhost", 
        port: int = 6379, 
        password: Optional[str] = None,
        db: int = 0
    ):
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.redis: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
    
    async def connect(self) -> None:
        """Connect to Redis."""
        self.redis = redis.Redis(
            host=self.host,
            port=self.port,
            password=self.password,
            db=self.db,
            decode_responses=True,
        )
        
        try:
            await self.redis.ping()
            logger.info(f"Connected to Redis at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.pubsub:
            await self.pubsub.close()
        if self.redis:
            await self.redis.close()
        logger.info("Disconnected from Redis")
    
    async def subscribe_market_data(
        self, 
        callback: Callable[[MarketData], None]
    ) -> None:
        """
        Subscribe to market data channel.
        
        Args:
            callback: Function to call when market data is received
        """
        self.pubsub = self.redis.pubsub()
        
        # Subscribe to general market_data channel
        await self.pubsub.subscribe("market_data")
        
        logger.info("Subscribed to market_data channel")
        
        async for message in self.pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    market_data = MarketData.from_dict(data)
                    await self._async_callback(callback, market_data)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse market data: {e}")
                except Exception as e:
                    logger.error(f"Error processing market data: {e}")
    
    async def publish_order_signal(self, signal: OrderSignal) -> None:
        """
        Publish order signal to Redis channel.
        
        Args:
            signal: Order signal to publish
        """
        try:
            message = json.dumps(signal.to_dict())
            await self.redis.publish("order_signals", message)
            logger.info(
                f"Published order signal: {signal.side.value} {signal.symbol.value} "
                f"(strength: {signal.strength})"
            )
        except Exception as e:
            logger.error(f"Failed to publish order signal: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Check Redis connection health."""
        try:
            await self.redis.ping()
            return True
        except Exception:
            return False
    
    async def _async_callback(
        self, 
        callback: Callable, 
        market_data: MarketData
    ) -> None:
        """Handle both sync and async callbacks."""
        if asyncio.iscoroutinefunction(callback):
            await callback(market_data)
        else:
            callback(market_data)


class RedisMarketDataStream:
    """
    Stream-based interface for market data from Redis.
    """
    
    def __init__(self, redis_adapter: RedisAdapter):
        self.redis_adapter = redis_adapter
        self.queue: asyncio.Queue = asyncio.Queue()
    
    async def start(self) -> None:
        """Start consuming market data."""
        await self.redis_adapter.subscribe_market_data(self._on_market_data)
    
    def _on_market_data(self, data: MarketData) -> None:
        """Handle incoming market data."""
        try:
            self.queue.put_nowait(data)
        except asyncio.QueueFull:
            logger.warning("Market data queue full, dropping message")
    
    async def get_market_data(self) -> MarketData:
        """Get next market data item."""
        return await self.queue.get()
