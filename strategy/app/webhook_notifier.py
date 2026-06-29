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

    # ── Evidence Loop Notifications ──────────────────────────────────────────

    async def send_signal_evaluation(self, stats: dict):
        """Send signal evaluation summary when signals are evaluated."""
        if not self._enabled:
            return
        
        evaluated_24h = stats.get("evaluated_24h", 0)
        evaluated_7d = stats.get("evaluated_7d", 0)
        total = stats.get("total_signals", 0)
        correct_24h = stats.get("correct_24h", 0)
        correct_7d = stats.get("correct_7d", 0)
        
        # Calculate accuracy
        accuracy_24h = (correct_24h / evaluated_24h * 100) if evaluated_24h > 0 else 0
        accuracy_7d = (correct_7d / evaluated_7d * 100) if evaluated_7d > 0 else 0
        
        text = (
            f"📊 *Signal Evaluation Update*\n"
            f"\n"
            f"🔍 Total Signals: `{total}`\n"
            f"⏱️ 24h Evaluated: `{evaluated_24h}` (Accuracy: `{accuracy_24h:.1f}%`)\n"
            f"📅 7d Evaluated: `{evaluated_7d}` (Accuracy: `{accuracy_7d:.1f}%`)\n"
            f"\n"
            f"✅ Correct 24h: `{correct_24h}`\n"
            f"✅ Correct 7d: `{correct_7d}`"
        )
        await self._queue.put(text)

    async def send_gate_progression(self, gate_name: str, gate_status: str, details: str = ""):
        """Send notification when a gate unlocks or status changes."""
        if not self._enabled:
            return
        
        status_emoji = {
            "unlocked": "🔓",
            "locked": "🔒",
            "waiting": "⏳",
            "passed": "✅",
            "failed": "❌",
        }.get(gate_status.lower(), "⚪")
        
        text = (
            f"{status_emoji} *Gate {gate_name}*\n"
            f"\n"
            f"Status: `{gate_status.upper()}`\n"
        )
        if details:
            text += f"\n{details}"
        
        await self._queue.put(text)

    async def send_evidence_loop_milestone(self, milestone: str, metrics: dict):
        """Send milestone notification (e.g., first 100 signals evaluated)."""
        if not self._enabled:
            return
        
        text = f"🎯 *Evidence Loop Milestone*\n\n{milestone}\n"
        
        if metrics:
            text += "\n*Metrics:*\n"
            for key, value in metrics.items():
                if isinstance(value, float):
                    text += f"  • {key}: `{value:.2f}`\n"
                else:
                    text += f"  • {key}: `{value}`\n"
        
        await self._queue.put(text)

    # ── Market Intelligence Alerts ─────────────────────────────────────────

    async def send_market_opportunity(
        self,
        symbol: str,
        market: str,
        severity: str,
        title: str,
        description: str,
        confidence: float,
        price: float = 0.0,
        opp_type: str = "",
    ):
        """Send market intelligence opportunity alert."""
        if not self._enabled:
            return

        severity_emoji = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🔵",
        }.get(severity, "⚪")

        market_emoji = {
            "crypto": "💰",
            "airdrop": "🎁",
            "degen": "🔥",
            "prediction": "🎯",
            "stock": "📈",
            "forex": "💱",
        }.get(market, "📊")

        price_str = f"\n💵 Price: `${price:,.2f}`" if price > 0 else ""
        opp_label = opp_type.replace("_", " ").title() if opp_type else ""

        text = (
            f"{severity_emoji} *Market Intel: {market.title()}*\n"
            f"\n"
            f"{market_emoji} *{symbol}* — {title}\n"
            f"📝 {description[:200]}\n"
            f"🎯 Confidence: `{confidence * 100:.0f}%`{price_str}"
        )
        if opp_label:
            text += f"\n🏷️ Type: `{opp_label}`"

        await self._queue.put(text)

    async def send_market_scan_summary(
        self,
        total_opps: int,
        by_severity: dict,
        by_market: dict,
        top_opps: list,
    ):
        """Send periodic market scan summary."""
        if not self._enabled:
            return

        critical = by_severity.get("critical", 0)
        high = by_severity.get("high", 0)

        # Only send if there's something noteworthy
        if total_opps == 0:
            return

        lines = [
            f"📊 *Market Scan Summary*\n",
            f"🔍 Total Opportunities: `{total_opps}`",
            f"🔴 Critical: `{critical}`  🟠 High: `{high}`\n",
        ]

        # Market breakdown
        if by_market:
            lines.append("*By Market:*")
            for market, count in sorted(by_market.items(), key=lambda x: -x[1])[:5]:
                lines.append(f"  • {market.title()}: {count}")
            lines.append("")

        # Top opportunities
        if top_opps:
            lines.append("*Top Picks:*")
            for opp in top_opps[:3]:
                symbol = opp.get("symbol", "?")
                title = opp.get("title", "")[:50]
                conf = opp.get("confidence", 0) * 100
                lines.append(f"  • `{symbol}` — {title} ({conf:.0f}%)")

        await self._queue.put("\n".join(lines))

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
