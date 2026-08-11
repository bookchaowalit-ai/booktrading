"""Safe USDⓈ-M futures MVP for paper trading and Binance Futures Testnet.

This module intentionally refuses mainnet execution. Leveraged trading can lose
more quickly than spot trading, so every entry is capped, reconciled with the
exchange, and protected by exchange-side stop-loss/take-profit orders.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from decimal import ROUND_CEILING, ROUND_DOWN, Decimal
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

import httpx

logger = logging.getLogger("futures_bot")

FUTURES_TESTNET_BASE = "https://demo-fapi.binance.com"
ALLOWED_EXECUTION_MODES = {"paper", "testnet"}
HARD_MAX_LEVERAGE = 5


class FuturesSafetyError(RuntimeError):
    """Raised when execution cannot be proven safe."""


class FuturesAPIError(RuntimeError):
    """Raised when Binance returns an error or an ambiguous response."""


@dataclass(frozen=True)
class SymbolRules:
    step_size: Decimal
    min_qty: Decimal
    max_qty: Decimal
    min_notional: Decimal
    tick_size: Decimal


@dataclass
class FuturesConfig:
    symbol: str
    leverage: int = 3
    risk_per_trade_pct: float = 1.0
    max_margin_usdt: float = 25.0
    max_notional_usdt: float = 75.0
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 4.0
    min_liquidation_buffer_pct: float = 10.0
    ema_fast: int = 9
    ema_slow: int = 21
    adx_threshold: float = 20.0
    check_interval_sec: int = 60

    def validate(self) -> None:
        errors: list[str] = []
        if not self.symbol or not self.symbol.isalnum():
            errors.append("symbol must be alphanumeric")
        if not 1 <= self.leverage <= HARD_MAX_LEVERAGE:
            errors.append(f"leverage must be between 1 and {HARD_MAX_LEVERAGE}")
        if not 0 < self.risk_per_trade_pct <= 1:
            errors.append("risk_per_trade_pct must be > 0 and <= 1")
        if self.max_margin_usdt <= 0:
            errors.append("max_margin_usdt must be > 0")
        if self.max_notional_usdt <= 0:
            errors.append("max_notional_usdt must be > 0")
        if self.max_notional_usdt > self.max_margin_usdt * self.leverage:
            errors.append("max_notional_usdt cannot exceed max_margin_usdt * leverage")
        if not 0 < self.stop_loss_pct <= 5:
            errors.append("stop_loss_pct must be > 0 and <= 5")
        if not self.take_profit_pct > 0:
            errors.append("take_profit_pct must be > 0")
        if not 5 <= self.min_liquidation_buffer_pct <= 100:
            errors.append("min_liquidation_buffer_pct must be between 5 and 100")
        if self.ema_fast <= 0 or self.ema_slow <= self.ema_fast:
            errors.append("EMA periods must satisfy 0 < ema_fast < ema_slow")
        if self.check_interval_sec < 5:
            errors.append("check_interval_sec must be at least 5")
        if errors:
            raise FuturesSafetyError(f"Invalid futures config for {self.symbol}: {'; '.join(errors)}")


@dataclass
class FuturesState:
    symbol: str
    position_side: str = "NONE"
    position_amt: float = 0.0
    entry_price: float = 0.0
    mark_price: float = 0.0
    liquidation_price: float = 0.0
    liquidation_buffer_pct: float = 0.0
    notional: float = 0.0
    initial_margin: float = 0.0
    maintenance_margin: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    funding_rate: float = 0.0
    total_trades: int = 0
    win_trades: int = 0
    loss_trades: int = 0
    last_signal: str = "NONE"
    last_signal_time: float = 0.0
    current_trend: str = "NEUTRAL"
    adx_value: float = 0.0
    stop_algo_id: int | None = None
    take_profit_algo_id: int | None = None
    halted: bool = False
    halt_reason: str = ""
    last_cycle_at: float = 0.0
    last_cycle_status: str = "NEVER"
    last_error: str = ""


class FuturesBot:
    """Fail-closed USDⓈ-M futures engine for paper or testnet only."""

    def __init__(
        self,
        execution_mode: str | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        max_total_notional_usdt: float | None = None,
    ):
        mode = (execution_mode or os.getenv("FUTURES_EXECUTION_MODE", "paper")).strip().lower()
        if mode not in ALLOWED_EXECUTION_MODES:
            raise FuturesSafetyError("FUTURES_EXECUTION_MODE must be 'paper' or 'testnet'; mainnet is disabled")
        self.execution_mode = mode
        self.configs: list[FuturesConfig] = []
        self.states: dict[str, FuturesState] = {}
        self._api_key = api_key if api_key is not None else os.getenv("BINANCE_FUTURES_API_KEY", "")
        self._api_secret = api_secret if api_secret is not None else os.getenv("BINANCE_FUTURES_API_SECRET", "")
        self._http = http_client
        self._owns_http = http_client is None
        self._redis: Any = None
        self._running = False
        self._rules: dict[str, SymbolRules] = {}
        self._base_url = FUTURES_TESTNET_BASE
        self.max_total_notional_usdt = (
            max_total_notional_usdt
            if max_total_notional_usdt is not None
            else float(os.getenv("FUTURES_MAX_TOTAL_NOTIONAL_USDT", "150"))
        )

    @property
    def is_testnet(self) -> bool:
        return self.execution_mode == "testnet"

    def set_redis(self, redis_client: Any) -> None:
        self._redis = redis_client

    def add_config(self, cfg: FuturesConfig) -> None:
        cfg.symbol = cfg.symbol.strip().upper()
        cfg.validate()
        self.configs.append(cfg)
        self.states[cfg.symbol] = FuturesState(symbol=cfg.symbol)

    def validate_startup(self) -> None:
        if not self.configs:
            raise FuturesSafetyError("At least one futures symbol must be configured")
        for cfg in self.configs:
            cfg.validate()
        if self.max_total_notional_usdt <= 0:
            raise FuturesSafetyError("FUTURES_MAX_TOTAL_NOTIONAL_USDT must be > 0")
        if self.is_testnet and (not self._api_key or not self._api_secret):
            raise FuturesSafetyError("Testnet mode requires BINANCE_FUTURES_API_KEY and BINANCE_FUTURES_API_SECRET")

    async def preflight(self) -> dict[str, Any]:
        """Run read-only readiness checks without placing or cancelling orders."""
        report: dict[str, Any] = {
            "ready": False,
            "checked_at": time.time(),
            "execution_mode": self.execution_mode,
            "mainnet_allowed": False,
            "checks": [],
            "symbols": {},
        }

        def add_check(name: str, ok: bool, detail: str) -> None:
            report["checks"].append({"name": name, "ok": ok, "detail": detail})

        try:
            self.validate_startup()
            add_check("configuration", True, f"{len(self.configs)} symbol configuration(s) valid")
        except FuturesSafetyError as exc:
            add_check("configuration", False, str(exc))
            return report

        add_check("mainnet_gate", True, "Mainnet execution is disabled in code")
        credentials_ready = not self.is_testnet or bool(self._api_key and self._api_secret)
        add_check(
            "credentials",
            credentials_ready,
            "Demo credentials configured" if self.is_testnet else "Credentials are not required in paper mode",
        )

        created_client = self._http is None
        if created_client:
            self._http = httpx.AsyncClient(timeout=30)
        try:
            if self.is_testnet:
                try:
                    await self._assert_one_way_mode()
                    add_check("position_mode", True, "Futures Demo account is in One-way Mode")
                except (FuturesAPIError, FuturesSafetyError) as exc:
                    add_check("position_mode", False, str(exc))

                try:
                    available_balance = await self._get_available_balance()
                    report["available_balance_usdt"] = available_balance
                    add_check("account_read", available_balance >= 0, "USDT balance endpoint is accessible")
                except FuturesAPIError as exc:
                    add_check("account_read", False, str(exc))

            for cfg in self.configs:
                try:
                    rules = await self._load_symbol_rules(cfg.symbol)
                    price = await self._get_price(cfg.symbol)
                    funding_rate = await self._get_funding(cfg.symbol)
                    symbol_ready = price > 0 and rules.step_size > 0 and rules.min_notional > 0
                    report["symbols"][cfg.symbol] = {
                        "ready": symbol_ready,
                        "price": price,
                        "funding_rate": funding_rate,
                        "step_size": str(rules.step_size),
                        "min_notional": str(rules.min_notional),
                        "leverage": cfg.leverage,
                        "max_margin_usdt": cfg.max_margin_usdt,
                        "max_notional_usdt": cfg.max_notional_usdt,
                    }
                    add_check(
                        f"symbol:{cfg.symbol}",
                        symbol_ready,
                        "Public price, funding, and exchange filters are available",
                    )
                except (FuturesAPIError, FuturesSafetyError, KeyError, ValueError) as exc:
                    report["symbols"][cfg.symbol] = {"ready": False, "error": str(exc)}
                    add_check(f"symbol:{cfg.symbol}", False, str(exc))
        finally:
            if created_client and self._http:
                await self._http.aclose()
                self._http = None

        report["ready"] = bool(report["checks"]) and all(check["ok"] for check in report["checks"])
        return report

    async def run_paper_cycle(self, *, allow_entry: bool = False) -> dict[str, Any]:
        """Run exactly one ephemeral paper cycle; never available in testnet mode."""
        if self.execution_mode != "paper":
            raise FuturesSafetyError("Single-cycle smoke execution is restricted to paper mode")
        self.validate_startup()
        created_client = self._http is None
        if created_client:
            self._http = httpx.AsyncClient(timeout=30)
        try:
            results = []
            for cfg in self.configs:
                state = self.states[cfg.symbol]
                try:
                    results.append(await self._run_cycle(cfg, allow_entry=allow_entry))
                except Exception as exc:
                    state.last_cycle_at = time.time()
                    state.last_cycle_status = "ERROR"
                    state.last_error = f"{type(exc).__name__}: {exc}"
                    self._halt(state, state.last_error)
                    results.append({"symbol": cfg.symbol, "action": "HALTED", "error": state.last_error})
            return {
                "execution_mode": self.execution_mode,
                "allow_entry": allow_entry,
                "mainnet_allowed": False,
                "results": results,
                "status": self.get_status(),
            }
        finally:
            if created_client and self._http:
                await self._http.aclose()
                self._http = None

    async def start(self) -> None:
        self.validate_startup()
        self._running = True
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30)
        try:
            await self._assert_one_way_mode()
            await self._load_states()
            logger.warning(
                "USDⓈ-M futures bot started in %s mode for %s; mainnet execution is disabled",
                self.execution_mode.upper(),
                [cfg.symbol for cfg in self.configs],
            )
            await asyncio.gather(*(self._run_symbol(cfg) for cfg in self.configs))
        except BaseException:
            self._running = False
            if self._http and self._owns_http:
                await self._http.aclose()
            raise

    async def stop(self) -> None:
        self._running = False
        await self._save_states()
        if self._http and self._owns_http:
            await self._http.aclose()
        logger.info("USDⓈ-M futures bot stopped")

    def _sign_request(self, params: dict[str, Any]) -> dict[str, Any]:
        signed = {**params, "recvWindow": 5000, "timestamp": int(time.time() * 1000)}
        signature = hmac.new(self._api_secret.encode(), urlencode(signed).encode(), hashlib.sha256).hexdigest()
        return {**signed, "signature": signature}

    def _headers(self) -> dict[str, str]:
        return {"X-MBX-APIKEY": self._api_key}

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        signed: bool = False,
        acceptable_codes: set[int] | None = None,
    ) -> Any:
        if self._http is None:
            raise FuturesAPIError("HTTP client is not initialized")
        payload = dict(params or {})
        if signed:
            if not self.is_testnet:
                raise FuturesSafetyError("Authenticated orders are allowed only in testnet mode")
            payload = self._sign_request(payload)
        try:
            response = await self._http.request(
                method,
                f"{self._base_url}{path}",
                params=payload if method == "GET" else None,
                data=payload if method != "GET" else None,
                headers=self._headers() if signed else None,
            )
        except httpx.HTTPError as exc:
            raise FuturesAPIError(f"{method} {path} transport error: {exc}") from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise FuturesAPIError(f"{method} {path} returned non-JSON status {response.status_code}") from exc
        if response.status_code not in (acceptable_codes or {200}):
            code = body.get("code") if isinstance(body, dict) else None
            message = body.get("msg") if isinstance(body, dict) else str(body)
            raise FuturesAPIError(f"{method} {path} failed ({response.status_code}/{code}): {message}")
        return body

    async def _get_price(self, symbol: str) -> float:
        body = await self._request("GET", "/fapi/v1/ticker/price", {"symbol": symbol})
        return float(body["price"])

    async def _get_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> list[dict[str, float]]:
        rows = await self._request("GET", "/fapi/v1/klines", {"symbol": symbol, "interval": interval, "limit": limit})
        return [{"high": float(row[2]), "low": float(row[3]), "close": float(row[4])} for row in rows]

    async def _get_available_balance(self) -> float:
        if not self.is_testnet:
            return float(os.getenv("FUTURES_PAPER_BALANCE_USDT", "1000"))
        balances = await self._request("GET", "/fapi/v3/balance", signed=True)
        for balance in balances:
            if balance.get("asset") == "USDT":
                return float(balance.get("availableBalance", 0))
        raise FuturesAPIError("USDT availableBalance was absent from futures balance response")

    async def _get_position(self, symbol: str) -> dict[str, Any]:
        if not self.is_testnet:
            state = self.states[symbol]
            return {
                "symbol": symbol,
                "positionAmt": str(state.position_amt),
                "entryPrice": str(state.entry_price),
                "markPrice": str(state.mark_price),
                "liquidationPrice": str(state.liquidation_price),
                "notional": str(state.notional),
                "initialMargin": str(state.initial_margin),
                "maintMargin": str(state.maintenance_margin),
                "unRealizedProfit": str(state.unrealized_pnl),
            }
        positions = await self._request("GET", "/fapi/v3/positionRisk", {"symbol": symbol}, signed=True)
        position = next((item for item in positions if item.get("symbol") == symbol), None)
        if position is None:
            raise FuturesAPIError(f"Position response omitted {symbol}")
        return position

    async def _get_funding(self, symbol: str) -> float:
        body = await self._request("GET", "/fapi/v1/premiumIndex", {"symbol": symbol})
        return float(body.get("lastFundingRate", 0))

    async def _assert_one_way_mode(self) -> None:
        if not self.is_testnet:
            return
        result = await self._request("GET", "/fapi/v1/positionSide/dual", signed=True)
        dual_side = result.get("dualSidePosition")
        if dual_side is True or str(dual_side).lower() == "true":
            raise FuturesSafetyError("Hedge mode is not supported; switch Futures Testnet to One-way Mode")

    async def _load_symbol_rules(self, symbol: str) -> SymbolRules:
        if symbol in self._rules:
            return self._rules[symbol]
        info = await self._request("GET", "/fapi/v1/exchangeInfo")
        item = next((entry for entry in info.get("symbols", []) if entry.get("symbol") == symbol), None)
        if not item or item.get("status") != "TRADING":
            raise FuturesSafetyError(f"{symbol} is not available for trading")
        filters = {entry["filterType"]: entry for entry in item.get("filters", [])}
        lot = filters.get("MARKET_LOT_SIZE") or filters.get("LOT_SIZE")
        price = filters.get("PRICE_FILTER")
        if not lot or not price:
            raise FuturesSafetyError(f"{symbol} is missing required exchange filters")
        notional = filters.get("MIN_NOTIONAL", {})
        rules = SymbolRules(
            step_size=Decimal(lot["stepSize"]),
            min_qty=Decimal(lot["minQty"]),
            max_qty=Decimal(lot["maxQty"]),
            min_notional=Decimal(notional.get("notional", "0")),
            tick_size=Decimal(price["tickSize"]),
        )
        self._rules[symbol] = rules
        return rules

    @staticmethod
    def calculate_notional(available_balance: float, cfg: FuturesConfig) -> float:
        risk_budget = available_balance * cfg.risk_per_trade_pct / 100
        risk_limited = risk_budget / (cfg.stop_loss_pct / 100)
        margin_limited = cfg.max_margin_usdt * cfg.leverage
        return max(0.0, min(risk_limited, margin_limited, cfg.max_notional_usdt))

    @staticmethod
    def round_quantity(raw_quantity: float, rules: SymbolRules) -> float:
        raw = Decimal(str(raw_quantity))
        quantity = (raw / rules.step_size).to_integral_value(rounding=ROUND_DOWN) * rules.step_size
        if quantity < rules.min_qty or quantity > rules.max_qty:
            raise FuturesSafetyError("Calculated quantity violates exchange lot-size limits")
        return float(quantity)

    @staticmethod
    def round_price(raw_price: float, rules: SymbolRules, *, round_up: bool = False) -> float:
        raw = Decimal(str(raw_price))
        rounding = ROUND_CEILING if round_up else ROUND_DOWN
        return float((raw / rules.tick_size).to_integral_value(rounding=rounding) * rules.tick_size)

    async def _calculate_quantity(self, cfg: FuturesConfig, price: float) -> float:
        balance = await self._get_available_balance()
        notional = self.calculate_notional(balance, cfg)
        open_notional = sum(
            state.notional for symbol, state in self.states.items() if symbol != cfg.symbol and state.position_amt != 0
        )
        notional = min(notional, max(0.0, self.max_total_notional_usdt - open_notional))
        if notional <= 0:
            raise FuturesSafetyError("Account-wide futures notional cap has been reached")
        rules = await self._load_symbol_rules(cfg.symbol)
        quantity = self.round_quantity(notional / price, rules)
        if Decimal(str(quantity)) * Decimal(str(price)) < rules.min_notional:
            raise FuturesSafetyError("Risk-capped position is below exchange minimum notional")
        return quantity

    async def _set_isolated_margin(self, symbol: str) -> None:
        if not self.is_testnet:
            return
        try:
            await self._request(
                "POST", "/fapi/v1/marginType", {"symbol": symbol, "marginType": "ISOLATED"}, signed=True
            )
        except FuturesAPIError as exc:
            if "-4046" not in str(exc):
                raise

    async def _set_leverage(self, symbol: str, leverage: int) -> None:
        if not self.is_testnet:
            return
        result = await self._request("POST", "/fapi/v1/leverage", {"symbol": symbol, "leverage": leverage}, signed=True)
        if int(result.get("leverage", 0)) != leverage:
            raise FuturesSafetyError(f"Exchange did not confirm {leverage}x leverage for {symbol}")

    async def _place_order(
        self, symbol: str, side: str, quantity: float, *, reduce_only: bool = False
    ) -> dict[str, Any]:
        if not self.is_testnet:
            logger.info("[Paper] %s %s %.8f reduceOnly=%s", symbol, side, quantity, reduce_only)
            return {"orderId": 0, "status": "FILLED", "paper": True}
        params: dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": format(quantity, ".12g"),
            "newOrderRespType": "RESULT",
            "newClientOrderId": f"bookfin_{uuid4().hex[:20]}",
        }
        if reduce_only:
            params["reduceOnly"] = "true"
        result = await self._request("POST", "/fapi/v1/order", params, signed=True)
        if result.get("status") != "FILLED":
            raise FuturesAPIError(f"Order status is ambiguous: {result.get('status')}")
        return result

    async def _place_protection(
        self, cfg: FuturesConfig, side: str, entry_price: float
    ) -> tuple[int | None, int | None]:
        if not self.is_testnet:
            return 0, 0
        rules = await self._load_symbol_rules(cfg.symbol)
        if side == "LONG":
            stop = entry_price * (1 - cfg.stop_loss_pct / 100)
            take = entry_price * (1 + cfg.take_profit_pct / 100)
            close_side = "SELL"
        else:
            stop = entry_price * (1 + cfg.stop_loss_pct / 100)
            take = entry_price * (1 - cfg.take_profit_pct / 100)
            close_side = "BUY"

        async def create(order_type: str, trigger_price: float) -> int:
            # Round toward the current price so protection never becomes looser
            # solely because of an exchange tick-size constraint.
            round_up = (side == "LONG" and order_type == "STOP_MARKET") or (
                side == "SHORT" and order_type == "TAKE_PROFIT_MARKET"
            )
            result = await self._request(
                "POST",
                "/fapi/v1/algoOrder",
                {
                    "algoType": "CONDITIONAL",
                    "symbol": cfg.symbol,
                    "side": close_side,
                    "type": order_type,
                    "triggerPrice": format(self.round_price(trigger_price, rules, round_up=round_up), ".12g"),
                    "closePosition": "true",
                    "workingType": "MARK_PRICE",
                    "priceProtect": "true",
                    "clientAlgoId": f"bookfin_{uuid4().hex[:20]}",
                },
                signed=True,
            )
            algo_id = result.get("algoId")
            if algo_id is None:
                raise FuturesAPIError(f"{order_type} response omitted algoId")
            return int(algo_id)

        stop_id = await create("STOP_MARKET", stop)
        try:
            take_id = await create("TAKE_PROFIT_MARKET", take)
        except Exception:
            try:
                await self._request(
                    "DELETE",
                    "/fapi/v1/algoOrder",
                    {"symbol": cfg.symbol, "algoId": stop_id},
                    signed=True,
                )
            except FuturesAPIError as cancel_exc:
                logger.critical("Failed to cancel orphan stop order %s: %s", stop_id, cancel_exc)
            raise
        return stop_id, take_id

    async def _cancel_protection(self, state: FuturesState) -> None:
        if not self.is_testnet:
            state.stop_algo_id = None
            state.take_profit_algo_id = None
            return
        for algo_id in (state.stop_algo_id, state.take_profit_algo_id):
            if algo_id is None:
                continue
            try:
                await self._request(
                    "DELETE", "/fapi/v1/algoOrder", {"symbol": state.symbol, "algoId": algo_id}, signed=True
                )
            except FuturesAPIError as exc:
                logger.warning("Could not cancel protection %s for %s: %s", algo_id, state.symbol, exc)
        state.stop_algo_id = None
        state.take_profit_algo_id = None

    @staticmethod
    def _liquidation_buffer(position_amt: float, mark_price: float, liquidation_price: float) -> float:
        if position_amt == 0 or mark_price <= 0 or liquidation_price <= 0:
            return 0.0
        if position_amt > 0:
            return max(0.0, (mark_price - liquidation_price) / mark_price * 100)
        return max(0.0, (liquidation_price - mark_price) / mark_price * 100)

    def _sync_state(self, state: FuturesState, position: dict[str, Any]) -> None:
        state.position_amt = float(position.get("positionAmt", 0))
        state.entry_price = float(position.get("entryPrice", 0))
        state.mark_price = float(position.get("markPrice", 0))
        state.liquidation_price = float(position.get("liquidationPrice", 0))
        state.notional = abs(float(position.get("notional", 0)))
        state.initial_margin = float(position.get("initialMargin", 0))
        state.maintenance_margin = float(position.get("maintMargin", 0))
        state.unrealized_pnl = float(position.get("unRealizedProfit", position.get("unrealizedProfit", 0)))
        state.position_side = "LONG" if state.position_amt > 0 else "SHORT" if state.position_amt < 0 else "NONE"
        state.liquidation_buffer_pct = self._liquidation_buffer(
            state.position_amt, state.mark_price, state.liquidation_price
        )

    def _halt(self, state: FuturesState, reason: str) -> None:
        state.halted = True
        state.halt_reason = reason
        state.last_error = reason
        logger.error("[Futures %s] HALTED: %s", state.symbol, reason)

    async def _open_position(self, cfg: FuturesConfig, state: FuturesState, signal: str, price: float) -> None:
        if state.halted:
            return
        quantity = await self._calculate_quantity(cfg, price)
        await self._set_isolated_margin(cfg.symbol)
        await self._set_leverage(cfg.symbol, cfg.leverage)
        side = "BUY" if signal == "LONG" else "SELL"
        await self._place_order(cfg.symbol, side, quantity)

        if self.is_testnet:
            position = await self._get_position(cfg.symbol)
            actual_amt = float(position.get("positionAmt", 0))
            if actual_amt == 0 or (signal == "LONG" and actual_amt < 0) or (signal == "SHORT" and actual_amt > 0):
                raise FuturesSafetyError("Entry order filled but exchange position did not reconcile")
            self._sync_state(state, position)
        else:
            state.position_amt = quantity if signal == "LONG" else -quantity
            state.position_side = signal
            state.entry_price = price
            state.mark_price = price
            state.notional = quantity * price
            state.initial_margin = state.notional / cfg.leverage

        try:
            state.stop_algo_id, state.take_profit_algo_id = await self._place_protection(cfg, signal, state.entry_price)
        except Exception as protection_exc:
            close_side = "SELL" if state.position_amt > 0 else "BUY"
            await self._place_order(cfg.symbol, close_side, abs(state.position_amt), reduce_only=True)
            if self.is_testnet:
                position = await self._get_position(cfg.symbol)
                if float(position.get("positionAmt", 0)) != 0:
                    raise FuturesSafetyError(
                        "Protection failed and emergency close did not reconcile"
                    ) from protection_exc
            state.position_side = "NONE"
            state.position_amt = 0.0
            state.entry_price = 0.0
            state.mark_price = 0.0
            state.notional = 0.0
            state.initial_margin = 0.0
            raise

        state.last_signal = signal
        state.last_signal_time = time.time()
        state.total_trades += 1

    async def _close_position(self, state: FuturesState, reason: str) -> None:
        if state.position_amt == 0:
            return
        previous_pnl = state.unrealized_pnl
        side = "SELL" if state.position_amt > 0 else "BUY"
        await self._place_order(state.symbol, side, abs(state.position_amt), reduce_only=True)
        if self.is_testnet:
            position = await self._get_position(state.symbol)
            if float(position.get("positionAmt", 0)) != 0:
                raise FuturesSafetyError("Close order filled but exchange still reports an open position")
        await self._cancel_protection(state)
        state.realized_pnl += previous_pnl
        state.win_trades += int(previous_pnl > 0)
        state.loss_trades += int(previous_pnl <= 0)
        state.position_side = "NONE"
        state.position_amt = 0.0
        state.entry_price = 0.0
        state.mark_price = 0.0
        state.liquidation_price = 0.0
        state.liquidation_buffer_pct = 0.0
        state.notional = 0.0
        state.initial_margin = 0.0
        state.maintenance_margin = 0.0
        state.unrealized_pnl = 0.0
        state.last_signal = f"CLOSE:{reason}"
        state.last_signal_time = time.time()

    def _calculate_ema(self, prices: list[float], period: int) -> float:
        if len(prices) < period:
            return prices[-1] if prices else 0.0
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    def _calculate_adx(self, klines: list[dict[str, float]], period: int = 14) -> float:
        if len(klines) < period + 1:
            return 0.0
        plus_dm: list[float] = []
        minus_dm: list[float] = []
        true_ranges: list[float] = []
        for current, previous in zip(klines[1:], klines, strict=False):
            up = max(current["high"] - previous["high"], 0)
            down = max(previous["low"] - current["low"], 0)
            plus_dm.append(up if up > down else 0)
            minus_dm.append(down if down > up else 0)
            true_ranges.append(
                max(
                    current["high"] - current["low"],
                    abs(current["high"] - previous["close"]),
                    abs(current["low"] - previous["close"]),
                )
            )
        atr = sum(true_ranges[:period]) / period
        plus_smooth = sum(plus_dm[:period]) / period
        minus_smooth = sum(minus_dm[:period]) / period
        dx: list[float] = []
        for index in range(period, len(true_ranges)):
            atr = (atr * (period - 1) + true_ranges[index]) / period
            plus_smooth = (plus_smooth * (period - 1) + plus_dm[index]) / period
            minus_smooth = (minus_smooth * (period - 1) + minus_dm[index]) / period
            if atr == 0:
                continue
            plus_di = plus_smooth / atr * 100
            minus_di = minus_smooth / atr * 100
            total = plus_di + minus_di
            dx.append(abs(plus_di - minus_di) / total * 100 if total else 0)
        return sum(dx) / len(dx) if dx else 0.0

    async def _analyze_signal(self, cfg: FuturesConfig, state: FuturesState) -> str:
        klines = await self._get_klines(cfg.symbol)
        closes = [row["close"] for row in klines]
        if not closes:
            return "NEUTRAL"
        fast = self._calculate_ema(closes, cfg.ema_fast)
        slow = self._calculate_ema(closes, cfg.ema_slow)
        state.adx_value = self._calculate_adx(klines)
        if state.adx_value < cfg.adx_threshold:
            state.current_trend = "NEUTRAL"
            return "NEUTRAL"
        state.current_trend = "UP" if fast > slow else "DOWN"
        return "LONG" if fast > slow else "SHORT"

    async def _run_cycle(self, cfg: FuturesConfig, *, allow_entry: bool = True) -> dict[str, Any]:
        state = self.states[cfg.symbol]
        action = "OBSERVE"
        position = await self._get_position(cfg.symbol)
        self._sync_state(state, position)
        if (
            self.is_testnet
            and state.position_amt != 0
            and (state.stop_algo_id is None or state.take_profit_algo_id is None)
        ):
            await self._close_position(state, "UNTRACKED_UNPROTECTED_POSITION")
            self._halt(state, "Exchange position had no tracked protection and was closed")
            action = "CLOSE_UNPROTECTED_AND_HALT"
        else:
            state.funding_rate = await self._get_funding(cfg.symbol)
            ticker_price = await self._get_price(cfg.symbol)
            if not self.is_testnet:
                state.mark_price = ticker_price
                if state.position_amt:
                    state.unrealized_pnl = (ticker_price - state.entry_price) * state.position_amt
            price = state.mark_price or ticker_price
            signal = await self._analyze_signal(cfg, state)
            state.last_signal = signal
            state.last_signal_time = time.time()

            pnl_pct = 0.0
            if state.position_amt and state.entry_price > 0:
                direction = 1 if state.position_amt > 0 else -1
                pnl_pct = (price - state.entry_price) / state.entry_price * 100 * direction

            if (
                state.position_amt != 0
                and state.liquidation_buffer_pct > 0
                and state.liquidation_buffer_pct <= cfg.min_liquidation_buffer_pct
            ):
                await self._close_position(state, "LIQUIDATION_BUFFER")
                self._halt(state, "Liquidation buffer breached")
                action = "CLOSE_LIQUIDATION_BUFFER_AND_HALT"
            elif state.position_amt != 0 and pnl_pct <= -cfg.stop_loss_pct:
                await self._close_position(state, "STOP_LOSS_WATCHDOG")
                action = "CLOSE_STOP_LOSS"
            elif state.position_amt != 0 and pnl_pct >= cfg.take_profit_pct:
                await self._close_position(state, "TAKE_PROFIT_WATCHDOG")
                action = "CLOSE_TAKE_PROFIT"
            elif allow_entry and state.position_amt == 0 and not state.halted and signal in {"LONG", "SHORT"}:
                await self._open_position(cfg, state, signal, price)
                action = f"OPEN_{signal}"
            elif (state.position_amt > 0 and signal == "SHORT") or (state.position_amt < 0 and signal == "LONG"):
                await self._close_position(state, "SIGNAL_REVERSAL")
                action = "CLOSE_SIGNAL_REVERSAL"

        state.last_cycle_at = time.time()
        state.last_cycle_status = "HALTED" if state.halted else "OK"
        if not state.halted:
            state.last_error = ""
        await self._save_state(cfg.symbol, state)
        return {
            "symbol": cfg.symbol,
            "action": action,
            "signal": state.last_signal,
            "trend": state.current_trend,
            "adx": state.adx_value,
            "mark_price": state.mark_price,
            "funding_rate": state.funding_rate,
            "position_side": state.position_side,
            "position_amt": state.position_amt,
            "halted": state.halted,
        }

    async def _run_symbol(self, cfg: FuturesConfig) -> None:
        state = self.states[cfg.symbol]
        while self._running:
            try:
                await self._run_cycle(cfg)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                state.last_cycle_at = time.time()
                state.last_cycle_status = "ERROR"
                state.last_error = f"{type(exc).__name__}: {exc}"
                self._halt(state, state.last_error)
                await self._save_state(cfg.symbol, state)
            await asyncio.sleep(cfg.check_interval_sec)

    async def _save_state(self, symbol: str, state: FuturesState) -> None:
        if not self._redis:
            return
        try:
            await self._redis.hset(
                f"futures_bot:{symbol}:state",
                mapping={key: json.dumps(value) for key, value in asdict(state).items()},
            )
        except Exception as exc:
            logger.warning("Redis save failed for %s: %s", symbol, exc)

    async def _save_states(self) -> None:
        await asyncio.gather(*(self._save_state(symbol, state) for symbol, state in self.states.items()))

    async def _load_states(self) -> None:
        if not self._redis:
            return
        for symbol, state in self.states.items():
            try:
                data = await self._redis.hgetall(f"futures_bot:{symbol}:state")
                for key, raw in data.items():
                    if isinstance(key, bytes):
                        key = key.decode()
                    if isinstance(raw, bytes):
                        raw = raw.decode()
                    if hasattr(state, key):
                        setattr(state, key, json.loads(raw))
            except Exception as exc:
                logger.warning("Redis load failed for %s: %s", symbol, exc)

    def get_status(self) -> dict[str, Any]:
        return {
            "enabled": self._running,
            "execution_mode": self.execution_mode,
            "mainnet_allowed": False,
            "hard_max_leverage": HARD_MAX_LEVERAGE,
            "max_total_notional_usdt": self.max_total_notional_usdt,
            "positions": {symbol: asdict(state) for symbol, state in self.states.items()},
        }


_futures_bot: FuturesBot | None = None


def get_futures_bot() -> FuturesBot:
    global _futures_bot
    if _futures_bot is None:
        bot = FuturesBot()
        symbols = os.getenv("FUTURES_SYMBOLS", "BTCUSDT,ETHUSDT").split(",")
        leverage = int(os.getenv("FUTURES_LEVERAGE", "3"))
        for symbol in symbols:
            if symbol.strip():
                bot.add_config(
                    FuturesConfig(
                        symbol=symbol,
                        leverage=leverage,
                        risk_per_trade_pct=float(os.getenv("FUTURES_RISK_PER_TRADE_PCT", "1")),
                        max_margin_usdt=float(os.getenv("FUTURES_MAX_MARGIN_USDT", "25")),
                        max_notional_usdt=float(os.getenv("FUTURES_MAX_NOTIONAL_USDT", "75")),
                        stop_loss_pct=float(os.getenv("FUTURES_STOP_LOSS_PCT", "2")),
                        take_profit_pct=float(os.getenv("FUTURES_TAKE_PROFIT_PCT", "4")),
                        min_liquidation_buffer_pct=float(os.getenv("FUTURES_MIN_LIQUIDATION_BUFFER_PCT", "10")),
                    )
                )
        _futures_bot = bot
    return _futures_bot
