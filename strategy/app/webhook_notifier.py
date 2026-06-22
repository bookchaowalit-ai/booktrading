"""
Webhook Notifier for Real Grid Bot
===================================
Sends alerts to Telegram/Discord webhooks for key trading events:
- Fill notifications (BUY/SELL executed)
- Kill switch triggered
- Daily P&L summary
- Error alerts

Supports both Telegram Bot API and Discord webhook formats.
"""

import asyncio
import logging
import os
import time
from typing import Optional

import httpx

logger = logging.getLogger("webhook_notifier")


class WebhookNotifier:
    """Sends trading alerts to external webhooks (Telegram/Discord)."""

    def __init__(self):
        self._telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self._telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self._discord_webhook = os.getenv("DISCORD_WEBHOOK_URL", "")
        self._enabled = bool(self._telegram_token or self._discord_webhook)
        self._http: Optional[httpx.AsyncClient] = None
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._worker_task: Optional[asyncio.Task] = None

        if self._enabled:
            logger.info(
                "Webhook notifier enabled: telegram=%s discord=%s",
                bool(self._telegram_token),
                bool(self._discord_webhook),
            )
        else:
            logger.info("Webhook notifier disabled (no TELEGRAM_BOT_TOKEN or DISCORD_WEBHOOK_URL)")

    async def start(self):
        """Start the webhook worker."""
        if not self._enabled:
            return
        self._http = httpx.AsyncClient(timeout=10.0)
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("Webhook notifier worker started")

    async def stop(self):
        """Stop the webhook worker."""
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        if self._http:
            await self._http.aclose()
        logger.info("Webhook notifier stopped")

    async def _worker(self):
        """Process webhook queue in background."""
        while True:
            try:
                message = await self._queue.get()
                await self._send(message)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Webhook worker error: %s", e)
                await asyncio.sleep(5)

    async def send_fill_alert(
        self,
        symbol: str,
        side: str,
        price: float,
        quantity: float,
        profit: float = 0.0,
    ):
        """Send a fill notification."""
        if not self._enabled:
            return

        if side == "SELL" and profit > 0:
            text = f"✅ {symbol} SELL filled @ {int(price)}\nQty: {quantity:.6f}\nProfit: {profit:.2f} THB"
        else:
            text = f"📥 {symbol} BUY filled @ {int(price)}\nQty: {quantity:.6f}"

        await self._queue.put(text)

    async def send_kill_switch_alert(self, symbol: str, reason: str):
        """Send kill switch triggered alert."""
        if not self._enabled:
            return
        text = f"🛑 KILL SWITCH: {symbol}\nReason: {reason}\nAll trading halted."
        await self._queue.put(text)

    async def send_daily_summary(self, symbol: str, daily_pnl: float, daily_trades: int):
        """Send daily P&L summary."""
        if not self._enabled:
            return
        emoji = "📈" if daily_pnl >= 0 else "📉"
        text = f"{emoji} Daily Summary: {symbol}\nP&L: {daily_pnl:.2f} THB\nTrades: {daily_trades}"
        await self._queue.put(text)

    async def send_error_alert(self, error: str):
        """Send error alert."""
        if not self._enabled:
            return
        text = f"⚠️ Grid Bot Error\n{error[:500]}"  # Truncate long errors
        await self._queue.put(text)

    async def _send(self, text: str):
        """Send message to configured webhooks."""
        if self._telegram_token and self._telegram_chat_id:
            await self._send_telegram(text)
        if self._discord_webhook:
            await self._send_discord(text)

    async def _send_telegram(self, text: str):
        """Send message via Telegram Bot API."""
        try:
            url = f"https://api.telegram.org/bot{self._telegram_token}/sendMessage"
            resp = await self._http.post(
                url,
                json={
                    "chat_id": self._telegram_chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                },
            )
            if resp.status_code == 200:
                logger.debug("Telegram alert sent")
            else:
                logger.warning("Telegram alert failed: %s %s", resp.status_code, resp.text)
        except Exception as e:
            logger.warning("Telegram send error: %s", e)

    async def _send_discord(self, text: str):
        """Send message via Discord webhook."""
        try:
            resp = await self._http.post(
                self._discord_webhook,
                json={"content": text},
            )
            if resp.status_code in (200, 204):
                logger.debug("Discord alert sent")
            else:
                logger.warning("Discord alert failed: %s %s", resp.status_code, resp.text)
        except Exception as e:
            logger.warning("Discord send error: %s", e)


# ── Singleton instance ────────────────────────────────────────────────────────

_notifier: Optional[WebhookNotifier] = None


def get_webhook_notifier() -> WebhookNotifier:
    global _notifier
    if _notifier is None:
        _notifier = WebhookNotifier()
    return _notifier
