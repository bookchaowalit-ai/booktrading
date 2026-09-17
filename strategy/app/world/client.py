"""Read-only HTTP/WebSocket client for World Markets.

The public web application currently uses a proxy under the World domain.  The
adapter keeps the endpoint configurable because access, schema, and API-key
requirements may change.  It never signs transactions or sends trading
instructions.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from app.world.models import WorldEventPage, WorldMarket, WorldPriceTick

logger = logging.getLogger(__name__)

DEFAULT_API_BASE = "https://markets-api-proxy.world-xyz.workers.dev/api/v1"
DEFAULT_WS_URL = "wss://markets-api-proxy.world-xyz.workers.dev/api/v1/ws"
CLIENT_VERSION = "booktrading-world-readonly/1"


class WorldApiError(RuntimeError):
    """A safe, redacted error from the World Markets read path."""

    def __init__(self, message: str, *, endpoint: str = "", status_code: int | None = None):
        super().__init__(message)
        self.endpoint = endpoint
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class WorldMarketsConfig:
    """Runtime configuration without exposing API-key values in repr/logs."""

    api_base: str = DEFAULT_API_BASE
    ws_url: str = DEFAULT_WS_URL
    api_key: str | None = field(default=None, repr=False)
    api_key_header: str = "Authorization"
    api_key_scheme: str = "Bearer"
    timeout_seconds: float = 15.0
    max_retries: int = 2

    def __post_init__(self) -> None:
        _validate_url(self.api_base, allowed_schemes={"http", "https"}, name="api_base")
        _validate_url(self.ws_url, allowed_schemes={"ws", "wss"}, name="ws_url")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if not self.api_key_header or any(char in self.api_key_header for char in "\r\n:"):
            raise ValueError("api_key_header must be a valid header name")
        if self.api_key and any(char in self.api_key for char in "\r\n"):
            raise ValueError("api_key contains invalid control characters")
        if self.api_key_scheme and any(char in self.api_key_scheme for char in "\r\n"):
            raise ValueError("api_key_scheme contains invalid control characters")

    @classmethod
    def from_env(cls) -> WorldMarketsConfig:
        """Load non-secret settings and an optional injected API key."""

        return cls(
            api_base=os.getenv("WORLD_MARKETS_API_BASE", DEFAULT_API_BASE).strip() or DEFAULT_API_BASE,
            ws_url=os.getenv("WORLD_MARKETS_WS_URL", DEFAULT_WS_URL).strip() or DEFAULT_WS_URL,
            api_key=os.getenv("WORLD_MARKETS_API_KEY") or os.getenv("WORLD_XYZ_API_KEY"),
            api_key_header=os.getenv("WORLD_MARKETS_API_KEY_HEADER", "Authorization").strip() or "Authorization",
            api_key_scheme=os.getenv("WORLD_MARKETS_API_KEY_SCHEME", "Bearer").strip(),
            timeout_seconds=_env_float("WORLD_MARKETS_TIMEOUT_SECONDS", 15.0),
            max_retries=_env_int("WORLD_MARKETS_MAX_RETRIES", 2),
        )


class WorldMarketsClient:
    """Bounded read-only client for event pages and price ticks."""

    def __init__(
        self,
        config: WorldMarketsConfig | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config or WorldMarketsConfig.from_env()
        self._http = http_client
        self._owns_http = http_client is None

    async def __aenter__(self) -> WorldMarketsClient:
        return self

    async def __aexit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_http and self._http is not None:
            await self._http.aclose()
            self._http = None

    async def list_events(
        self,
        *,
        limit: int = 200,
        cursor: str | None = None,
        category: str | None = None,
        tags: Sequence[str] | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
        updated_since: int | None = None,
        include_settled: bool = False,
    ) -> WorldEventPage:
        """Fetch one page from ``/events`` using the web app's query shape."""

        if limit <= 0 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        params: dict[str, str] = {
            "withNestedMarkets": "true",
            "limit": str(limit),
        }
        if cursor:
            params["cursor"] = cursor
        if category:
            params["category"] = category.strip().lower()
        clean_tags = [tag.strip().lower() for tag in (tags or ()) if tag and tag.strip()]
        if clean_tags:
            params["tags"] = ",".join(clean_tags)
        if sort_by:
            params["sortBy"] = sort_by.strip()
        if sort_order:
            params["sortOrder"] = sort_order.strip()
        if updated_since is not None:
            params["updatedSince"] = str(updated_since)
        if not include_settled:
            params["status"] = "active"

        payload, raw_bytes = await self._get_json("events", params)
        events = tuple(_extract_events(payload))
        return WorldEventPage(
            events=events,
            cursor=_extract_cursor(payload),
            raw=payload,
            raw_bytes=raw_bytes,
            endpoint="/events",
            request_params=params,
        )

    async def iter_event_pages(
        self,
        *,
        limit: int = 200,
        max_pages: int = 5,
        category: str | None = None,
        tags: Sequence[str] | None = None,
        sort_by: str | None = None,
        sort_order: str | None = None,
        updated_since: int | None = None,
        include_settled: bool = False,
    ) -> AsyncIterator[WorldEventPage]:
        """Yield pages with bounded, loop-safe cursor pagination."""

        if max_pages <= 0 or max_pages > 100:
            raise ValueError("max_pages must be between 1 and 100")
        cursor: str | None = None
        seen_cursors: set[str] = set()
        for _page_number in range(max_pages):
            page = await self.list_events(
                limit=limit,
                cursor=cursor,
                category=category,
                tags=tags,
                sort_by=sort_by,
                sort_order=sort_order,
                updated_since=updated_since,
                include_settled=include_settled,
            )
            yield page
            next_cursor = page.cursor
            if not next_cursor or next_cursor in seen_cursors:
                return
            seen_cursors.add(next_cursor)
            cursor = next_cursor

    async def list_markets(
        self,
        *,
        limit: int = 200,
        max_pages: int = 5,
        category: str | None = None,
        tags: Sequence[str] | None = None,
        include_settled: bool = False,
    ) -> list[WorldMarket]:
        """Flatten nested event pages into normalized markets."""

        markets: list[WorldMarket] = []
        seen_tickers: set[str] = set()
        async for page in self.iter_event_pages(
            limit=limit,
            max_pages=max_pages,
            category=category,
            tags=tags,
            include_settled=include_settled,
        ):
            for event in page.events:
                for market_payload in _event_markets(event):
                    market = parse_world_market(market_payload, event=event)
                    if not market.ticker or market.ticker in seen_tickers:
                        continue
                    seen_tickers.add(market.ticker)
                    markets.append(market)
        return markets

    async def get_market(self, ticker: str) -> WorldMarket:
        """Fetch one market when the provider exposes a REST detail route."""

        clean_ticker = ticker.strip()
        if not clean_ticker:
            raise ValueError("ticker cannot be empty")
        payload, _raw_bytes = await self._get_json(f"markets/{quote(clean_ticker, safe='')}", {})
        event: Mapping[str, Any] = {}
        market_payload: Any = payload
        if isinstance(payload, Mapping):
            event_value = payload.get("event")
            if isinstance(event_value, Mapping):
                event = event_value
            market_payload = payload.get("market") or payload.get("data") or payload
        if not isinstance(market_payload, Mapping):
            raise WorldApiError("World Markets detail response is not an object", endpoint="/markets/:ticker")
        return parse_world_market(market_payload, event=event)

    async def get_orderbook(self, ticker: str) -> Any:
        """Read an orderbook payload without placing or signing an order."""

        clean_ticker = ticker.strip()
        if not clean_ticker:
            raise ValueError("ticker cannot be empty")
        payload, _raw_bytes = await self._get_json(f"markets/{quote(clean_ticker, safe='')}/orderbook", {})
        return payload

    async def stream_prices(
        self,
        tickers: Sequence[str],
        *,
        max_messages: int | None = None,
        idle_timeout_seconds: float | None = None,
    ) -> AsyncIterator[WorldPriceTick]:
        """Subscribe to the read-only ``world_prices`` WebSocket channel."""

        clean_tickers = sorted({ticker.strip() for ticker in tickers if ticker and ticker.strip()})
        if not clean_tickers:
            raise ValueError("at least one ticker is required")
        if max_messages is not None and max_messages <= 0:
            raise ValueError("max_messages must be greater than zero")
        if idle_timeout_seconds is not None and idle_timeout_seconds <= 0:
            raise ValueError("idle_timeout_seconds must be greater than zero")

        try:
            import websockets
        except ImportError as exc:  # pragma: no cover - dependency is pinned in the image
            raise WorldApiError("WebSocket support requires the websockets package") from exc

        connect_kwargs: dict[str, Any] = {"open_timeout": self.config.timeout_seconds}
        parameters = inspect.signature(websockets.connect).parameters
        header_name = "additional_headers" if "additional_headers" in parameters else "extra_headers"
        connect_kwargs[header_name] = self._headers()
        subscription = {
            "type": "subscribe",
            "channel": "world_prices",
            "tickers": clean_tickers,
        }

        try:
            async with websockets.connect(self.config.ws_url, **connect_kwargs) as socket:
                await socket.send(json.dumps(subscription, separators=(",", ":")))
                received = 0
                while max_messages is None or received < max_messages:
                    try:
                        raw_message = await (
                            asyncio.wait_for(socket.recv(), timeout=idle_timeout_seconds)
                            if idle_timeout_seconds is not None
                            else socket.recv()
                        )
                    except TimeoutError as exc:
                        raise WorldApiError("World Markets WebSocket idle timeout") from exc
                    raw_text = raw_message.decode("utf-8") if isinstance(raw_message, bytes) else raw_message
                    try:
                        payload = json.loads(raw_text)
                    except (TypeError, json.JSONDecodeError):
                        logger.debug("Ignoring non-JSON World Markets WebSocket frame")
                        continue
                    tick = parse_price_tick(payload)
                    if tick is None:
                        continue
                    received += 1
                    yield tick
        except WorldApiError:
            raise
        except Exception as exc:
            raise WorldApiError(f"World Markets WebSocket request failed: {type(exc).__name__}") from exc

    async def _get_json(self, path: str, params: Mapping[str, str]) -> tuple[Any, bytes]:
        client = self._http_client()
        url = f"{self.config.api_base.rstrip('/')}/{path.lstrip('/')}"
        for attempt in range(self.config.max_retries + 1):
            try:
                response = await client.get(url, params=dict(params), headers=self._headers())
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt >= self.config.max_retries:
                    raise WorldApiError(
                        f"World Markets request failed at /{path}: {type(exc).__name__}",
                        endpoint=f"/{path}",
                    ) from exc
                await asyncio.sleep(_retry_delay(attempt))
                continue

            if response.status_code in {408, 425, 429, 500, 502, 503, 504} and attempt < self.config.max_retries:
                await asyncio.sleep(_retry_delay(attempt, response.headers.get("Retry-After")))
                continue
            if response.status_code < 200 or response.status_code >= 300:
                raise WorldApiError(
                    f"World Markets API returned HTTP {response.status_code} for /{path}",
                    endpoint=f"/{path}",
                    status_code=response.status_code,
                )
            try:
                payload = response.json()
            except (TypeError, ValueError) as exc:
                raise WorldApiError(
                    f"World Markets API returned invalid JSON for /{path}",
                    endpoint=f"/{path}",
                    status_code=response.status_code,
                ) from exc
            return payload, response.content

        raise WorldApiError(f"World Markets request exhausted retries at /{path}", endpoint=f"/{path}")

    def _http_client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self.config.timeout_seconds)
        return self._http

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": CLIENT_VERSION,
        }
        if self.config.api_key:
            value = self.config.api_key
            if self.config.api_key_header.lower() == "authorization" and self.config.api_key_scheme:
                value = f"{self.config.api_key_scheme} {value}"
            headers[self.config.api_key_header] = value
        return headers


def parse_world_market(payload: Mapping[str, Any], *, event: Mapping[str, Any] | None = None) -> WorldMarket:
    """Parse known World shapes while retaining unknown provider fields."""

    market = dict(payload)
    event_data = dict(event or {})
    nested_quote = _mapping(_first(market, "quote", "quotes", "orderbook", "order_book"))
    yes_quote = _mapping(_first(nested_quote, "yes", "YES"))
    no_quote = _mapping(_first(nested_quote, "no", "NO"))
    outcome_prices = _outcome_prices(_first(market, "outcomePrices", "outcome_prices", "prices", "outcomes"))
    yes_price = _number(_first(market, "yes_price", "yesPrice", "yes_probability"))
    no_price = _number(_first(market, "no_price", "noPrice", "no_probability"))
    if yes_price is None and outcome_prices:
        yes_price = outcome_prices[0]
    if no_price is None and len(outcome_prices) > 1:
        no_price = outcome_prices[1]

    yes_bid = _quote_number(
        market,
        nested_quote,
        yes_quote,
        ("yes_bid", "yesBid", "yes_bid_price"),
    )
    if yes_bid is None:
        yes_bid = _quote_number({}, nested_quote, yes_quote, ("bid", "best_bid"))
    yes_ask = _quote_number(
        market,
        nested_quote,
        yes_quote,
        ("yes_ask", "yesAsk", "yes_ask_price"),
    )
    if yes_ask is None:
        yes_ask = _quote_number({}, nested_quote, yes_quote, ("ask", "best_ask"))
    no_bid = _quote_number(
        market,
        nested_quote,
        no_quote,
        ("no_bid", "noBid", "no_bid_price"),
    )
    if no_bid is None:
        no_bid = _quote_number({}, nested_quote, no_quote, ("bid", "best_bid"))
    no_ask = _quote_number(
        market,
        nested_quote,
        no_quote,
        ("no_ask", "noAsk", "no_ask_price"),
    )
    if no_ask is None:
        no_ask = _quote_number({}, nested_quote, no_quote, ("ask", "best_ask"))
    yes_ask_size = _quote_number(
        market,
        nested_quote,
        yes_quote,
        (
            "yes_ask_size",
            "yesAskSize",
            "yes_ask_quantity",
            "yesAskQuantity",
        ),
    )
    if yes_ask_size is None:
        yes_ask_size = _quote_number(
            {},
            nested_quote,
            yes_quote,
            ("ask_size", "askSize", "ask_quantity", "askQuantity"),
        )
    no_ask_size = _quote_number(
        market,
        nested_quote,
        no_quote,
        (
            "no_ask_size",
            "noAskSize",
            "no_ask_quantity",
            "noAskQuantity",
        ),
    )
    if no_ask_size is None:
        no_ask_size = _quote_number(
            {},
            nested_quote,
            no_quote,
            ("ask_size", "askSize", "ask_quantity", "askQuantity"),
        )
    last_price = _number(_first(market, "last_price", "lastPrice", "last", "price"))
    if last_price is None:
        last_price = yes_price

    tags = _unique_texts(
        _first(market, "tags", "tag") or (),
        _first(event_data, "tags", "tag") or (),
    )
    question = _text(_first(market, "question", "prompt", "description")) or _text(
        _first(event_data, "question", "title", "name")
    )
    title = _text(_first(market, "title", "name")) or _text(_first(event_data, "title", "name")) or question
    raw = {"market": market}
    if event_data:
        raw["event"] = event_data

    return WorldMarket(
        ticker=_text(_first(market, "ticker", "market_ticker", "marketTicker", "symbol", "id")) or "",
        event_ticker=_text(_first(market, "event_ticker", "eventTicker"))
        or _text(_first(event_data, "ticker", "event_ticker", "eventTicker")),
        series_ticker=_text(_first(market, "series_ticker", "seriesTicker"))
        or _text(_first(event_data, "series_ticker", "seriesTicker")),
        title=title,
        question=question,
        category=_text(_first(market, "category")) or _text(_first(event_data, "category")),
        tags=tags,
        status=(
            _text(_first(market, "status", "state")) or _text(_first(event_data, "status", "state")) or "unknown"
        ).lower(),
        yes_bid=yes_bid,
        yes_ask=yes_ask,
        no_bid=no_bid,
        no_ask=no_ask,
        yes_ask_size=yes_ask_size,
        no_ask_size=no_ask_size,
        yes_price=yes_price,
        no_price=no_price,
        last_price=last_price,
        volume=_number(_first(market, "volume", "volume24h", "volume_24h", "totalVolume", "total_volume")),
        liquidity=_number(_first(market, "liquidity", "liquidityUsd", "liquidity_usd")),
        open_time=_text(_first(market, "openTime", "open_time", "openAt")),
        close_time=_text(_first(market, "closeTime", "close_time", "closeAt")),
        strike_date=_text(_first(market, "strikeDate", "strike_date", "resolutionDate"))
        or _text(_first(event_data, "strikeDate", "strike_date", "resolutionDate")),
        resolution_source=_text(
            _first(market, "resolutionSource", "resolution_source", "resolutionRule", "resolution_rule", "oracle")
        )
        or _text(
            _first(event_data, "resolutionSource", "resolution_source", "resolutionRule", "resolution_rule", "oracle")
        ),
        updated_at=_timestamp(_first(market, "updatedAt", "updated_at", "lastUpdated", "last_updated", "timestamp"))
        or _timestamp(_first(event_data, "updatedAt", "updated_at", "lastUpdated", "last_updated", "timestamp")),
        raw=raw,
    )


def parse_price_tick(payload: Any) -> WorldPriceTick | None:
    """Normalize a ticker WebSocket frame; acknowledgements return ``None``."""

    if not isinstance(payload, Mapping):
        return None
    candidate: Mapping[str, Any] = payload
    for key in ("data", "ticker", "quote"):
        nested = candidate.get(key)
        if isinstance(nested, Mapping):
            candidate = nested
    ticker = _text(_first(candidate, "market_ticker", "marketTicker", "ticker", "symbol", "id"))
    if not ticker:
        return None
    nested_quote = _mapping(_first(candidate, "quote", "quotes", "orderbook", "order_book"))
    yes_quote = _mapping(_first(nested_quote, "yes", "YES"))
    no_quote = _mapping(_first(nested_quote, "no", "NO"))
    return WorldPriceTick(
        ticker=ticker,
        yes_bid=_quote_number(candidate, nested_quote, yes_quote, ("yes_bid", "yesBid", "yes_bid_price")),
        yes_ask=_quote_number(candidate, nested_quote, yes_quote, ("yes_ask", "yesAsk", "yes_ask_price")),
        no_bid=_quote_number(candidate, nested_quote, no_quote, ("no_bid", "noBid", "no_bid_price")),
        no_ask=_quote_number(candidate, nested_quote, no_quote, ("no_ask", "noAsk", "no_ask_price")),
        last_price=_number(_first(candidate, "last_price", "lastPrice", "last", "price")),
        timestamp=_timestamp(_first(candidate, "timestamp", "ts", "time", "updatedAt", "updated_at")),
        raw=dict(payload),
    )


def _event_markets(event: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    nested = event.get("markets")
    if isinstance(nested, Mapping):
        nested = [nested]
    if isinstance(nested, Sequence) and not isinstance(nested, (str, bytes, bytearray)):
        return [item for item in nested if isinstance(item, Mapping)]
    if _first(event, "ticker", "market_ticker", "marketTicker", "symbol"):
        return [event]
    return []


def _extract_events(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        return [dict(item) for item in payload if isinstance(item, Mapping)]
    if not isinstance(payload, Mapping):
        return []
    for key in ("events", "items"):
        value = payload.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return [dict(item) for item in value if isinstance(item, Mapping)]
    data = payload.get("data")
    if isinstance(data, Mapping):
        return _extract_events(data)
    if isinstance(data, Sequence) and not isinstance(data, (str, bytes, bytearray)):
        return [dict(item) for item in data if isinstance(item, Mapping)]
    days = payload.get("days")
    if isinstance(days, Sequence) and not isinstance(days, (str, bytes, bytearray)):
        events: list[dict[str, Any]] = []
        for day in days:
            if isinstance(day, Mapping):
                events.extend(_extract_events(day))
        return events
    return []


def _extract_cursor(payload: Any) -> str | None:
    if isinstance(payload, Mapping):
        for key in ("cursor", "next_cursor", "nextCursor"):
            value = payload.get(key)
            if value is not None and str(value):
                return str(value)
        pagination = payload.get("pagination")
        if isinstance(pagination, Mapping):
            return _extract_cursor(pagination)
        data = payload.get("data")
        if isinstance(data, Mapping):
            return _extract_cursor(data)
    return None


def _quote_number(
    market: Mapping[str, Any],
    quote: Mapping[str, Any],
    outcome_quote: Mapping[str, Any],
    keys: Sequence[str],
) -> float | None:
    for container in (market, quote, outcome_quote):
        value = _number(_first(container, *keys))
        if value is not None:
            return value
    return None


def _outcome_prices(value: Any) -> list[float]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = [part.strip() for part in value.split(",")]
    if isinstance(value, Mapping):
        values = [_first(value, "yes", "YES", "true"), _first(value, "no", "NO", "false")]
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        values = list(value)
    else:
        return []
    normalized: list[float] = []
    for item in values:
        if isinstance(item, Mapping):
            item = _first(item, "price", "probability", "value", "odds")
        number = _number(item)
        if number is not None:
            normalized.append(number)
    return normalized


def _first(value: Mapping[str, Any] | None, *keys: str) -> Any:
    if not isinstance(value, Mapping):
        return None
    for key in keys:
        if key in value and value[key] is not None:
            return value[key]
    return None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return str(value).strip()
    return ""


def _unique_texts(*values: Any) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        if isinstance(value, str):
            candidates = [value]
        elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
            candidates = list(value)
        else:
            candidates = []
        for candidate in candidates:
            text = _text(candidate)
            if text and text.lower() not in {item.lower() for item in result}:
                result.append(text)
    return tuple(result)


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = float(value)
        if seconds > 10_000_000_000:
            seconds /= 1000
        try:
            return datetime.fromtimestamp(seconds, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _validate_url(value: str, *, allowed_schemes: set[str], name: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in allowed_schemes or not parsed.netloc:
        raise ValueError(f"{name} must use one of: {', '.join(sorted(allowed_schemes))}")
    if parsed.username or parsed.password:
        raise ValueError(f"{name} must not include credentials")


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _retry_delay(attempt: int, retry_after: str | None = None) -> float:
    if retry_after:
        try:
            return min(2.0, max(0.0, float(retry_after)))
        except ValueError:
            pass
    return min(2.0, 0.25 * (2**attempt))
