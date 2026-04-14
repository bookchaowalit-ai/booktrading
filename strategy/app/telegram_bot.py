"""
Telegram Bot Control Service
Control trading bot and receive alerts via Telegram
"""

import os
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


class TelegramBot:
    """
    Telegram Bot for:
    - Start/Stop trading bot
    - Check bot status
    - Receive trade notifications
    - Check balance
    - View arbitrage opportunities
    """
    
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = bool(self.bot_token and self.chat_id)
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        
    async def send_message(self, message: str, parse_mode: str = "Markdown"):
        """Send message to Telegram chat"""
        if not self.enabled:
            logger.warning("Telegram bot not configured")
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": message,
                        "parse_mode": parse_mode
                    }
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    async def notify_trade(self, symbol: str, side: str, price: float, quantity: float, total: float):
        """Send trade notification"""
        emoji = "🟢" if side == "BUY" else "🔴"
        message = f"""
{emoji} *Grid {side} Executed*

📊 Symbol: `{symbol}`
💰 Price: `{price:,.2f}` THB
📦 Quantity: `{quantity:.6f}`
💵 Total: `{total:,.2f}` THB
"""
        await self.send_message(message)
    
    async def notify_bot_status(self, is_running: bool, mode: str = "GRID"):
        """Send bot status notification"""
        status = "✅ *Bot Started*" if is_running else "⏸️ *Bot Stopped*"
        message = f"""
{status}

🤖 Mode: `{mode}`
⏰ Time: Now
"""
        await self.send_message(message)
    
    async def notify_arbitrage(self, symbol: str, buy_exchange: str, buy_price: float, 
                               sell_exchange: str, sell_price: float, profit_percent: float):
        """Send arbitrage opportunity notification"""
        message = f"""
🔍 *Arbitrage Opportunity*

📊 Symbol: `{symbol}`
💚 Buy: `{buy_exchange}` @ `{buy_price:,.2f}`
💛 Sell: `{sell_exchange}` @ `{sell_price:,.2f}`
💰 Profit: `{profit_percent:.2f}%`

⚡️ Act fast!
"""
        await self.send_message(message)
    
    async def notify_alert(self, title: str, message: str, level: str = "info"):
        """Send general alert"""
        emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "success": "✅"
        }.get(level, "ℹ️")
        
        full_message = f"{emoji} *{title}*\n\n{message}"
        await self.send_message(full_message)


# Singleton instance
telegram_bot = TelegramBot()
