"""
Arbitrage Detection Service
Finds price differences across exchanges to identify profit opportunities
"""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ArbitrageDetector:
    """
    Detects arbitrage opportunities across multiple exchanges
    
    Monitors prices on:
    - Binance Global
    - Binance Thailand
    - Bitkub
    
    Alerts when price difference > threshold (after fees)
    """
    
    def __init__(self, min_profit_percent: float = 0.5):
        self.min_profit_percent = min_profit_percent
        self.exchanges = {}
        self.opportunities = []
        
    def update_price(self, exchange: str, symbol: str, price: float, volume: float = 0):
        """Update price for an exchange"""
        if exchange not in self.exchanges:
            self.exchanges[exchange] = {}
        
        self.exchanges[exchange][symbol] = {
            'price': price,
            'volume': volume,
            'timestamp': datetime.now()
        }
        
        # Check for arbitrage opportunities
        self._check_arbitrage(symbol)
    
    def _check_arbitrage(self, symbol: str):
        """Check if there's an arbitrage opportunity for this symbol"""
        prices = []
        
        for exchange, symbols in self.exchanges.items():
            if symbol in symbols:
                prices.append({
                    'exchange': exchange,
                    'price': symbols[symbol]['price'],
                    'volume': symbols[symbol]['volume'],
                    'timestamp': symbols[symbol]['timestamp']
                })
        
        if len(prices) < 2:
            return
        
        # Find best buy/sell pair
        prices.sort(key=lambda x: x['price'])
        cheapest = prices[0]
        most_expensive = prices[-1]
        
        # Calculate profit after fees (assume 0.1% per trade)
        buy_price = cheapest['price']
        sell_price = most_expensive['price']
        fees = buy_price * 0.001 + sell_price * 0.001  # 0.1% buy + 0.1% sell
        gross_profit = sell_price - buy_price
        net_profit = gross_profit - fees
        profit_percent = (net_profit / buy_price) * 100
        
        if profit_percent > self.min_profit_percent:
            opportunity = {
                'symbol': symbol,
                'buy_exchange': cheapest['exchange'],
                'buy_price': buy_price,
                'sell_exchange': most_expensive['exchange'],
                'sell_price': sell_price,
                'gross_profit': gross_profit,
                'net_profit': net_profit,
                'profit_percent': profit_percent,
                'timestamp': datetime.now()
            }
            
            self.opportunities.append(opportunity)
            
            logger.info(
                f"🔍 ARBITRAGE DETECTED: {symbol} | "
                f"Buy: {cheapest['exchange']} @ {buy_price:.2f} | "
                f"Sell: {most_expensive['exchange']} @ {sell_price:.2f} | "
                f"Profit: {profit_percent:.2f}%"
            )
    
    def get_opportunities(self, limit: int = 10) -> List[Dict]:
        """Get recent arbitrage opportunities"""
        sorted_opps = sorted(
            self.opportunities,
            key=lambda x: x['profit_percent'],
            reverse=True
        )
        
        return [
            {
                'symbol': opp['symbol'],
                'buy_exchange': opp['buy_exchange'],
                'buy_price': opp['buy_price'],
                'sell_exchange': opp['sell_exchange'],
                'sell_price': opp['sell_price'],
                'profit_percent': opp['profit_percent'],
                'net_profit': opp['net_profit'],
                'timestamp': opp['timestamp'].isoformat()
            }
            for opp in sorted_opps[:limit]
        ]
    
    def get_best_opportunity(self, symbol: str) -> Optional[Dict]:
        """Get best current arbitrage opportunity for a symbol"""
        opportunities = [opp for opp in self.opportunities if opp['symbol'] == symbol]
        
        if not opportunities:
            return None
        
        return max(opportunities, key=lambda x: x['profit_percent'])


# Singleton instance
detector = ArbitrageDetector(min_profit_percent=0.5)
