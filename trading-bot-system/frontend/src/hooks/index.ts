/**
 * Custom hooks for the trading bot application.
 */
import { useEffect, useCallback } from 'react';
import { useAppStore } from '@/store/store';
import { wsService } from '@/services/websocket';

/**
 * Hook for managing WebSocket connection.
 */
export function useWebSocket() {
  const connectWebSocket = useAppStore((state) => state.connectWebSocket);
  const disconnectWebSocket = useAppStore((state) => state.disconnectWebSocket);

  useEffect(() => {
    connectWebSocket();
    return () => {
      disconnectWebSocket();
    };
  }, [connectWebSocket, disconnectWebSocket]);

  return {
    isConnected: wsService.isConnected(),
  };
}

/**
 * Hook for auto-refreshing data.
 */
export function useAutoRefresh(intervalMs: number = 5000) {
  const refreshBotStatus = useAppStore((state) => state.refreshBotStatus);
  const refreshPortfolio = useAppStore((state) => state.refreshPortfolio);
  const refreshOrders = useAppStore((state) => state.refreshOrders);
  const refreshIndicators = useAppStore((state) => state.refreshIndicators);

  useEffect(() => {
    const refreshAll = async () => {
      await Promise.all([
        refreshBotStatus(),
        refreshPortfolio(),
        refreshOrders(),
        refreshIndicators(),
      ]);
    };

    refreshAll();

    const interval = setInterval(refreshAll, intervalMs);
    return () => clearInterval(interval);
  }, [intervalMs, refreshBotStatus, refreshPortfolio, refreshOrders, refreshIndicators]);
}

/**
 * Hook for bot control.
 */
export function useBotControl() {
  const botStatus = useAppStore((state) => state.botStatus);
  const isBotLoading = useAppStore((state) => state.isBotLoading);
  const startBot = useAppStore((state) => state.startBot);
  const stopBot = useAppStore((state) => state.stopBot);

  const isActive = botStatus?.isActive ?? false;

  return {
    isActive,
    isLoading: isBotLoading,
    startBot,
    stopBot,
    totalTrades: botStatus?.totalTrades ?? 0,
    totalProfit: botStatus?.totalProfit ?? 0,
  };
}

/**
 * Hook for market data.
 */
export function useMarketData(symbol: string) {
  const marketData = useAppStore((state) => state.marketData);
  return marketData[symbol] || null;
}

/**
 * Hook for technical indicators.
 */
export function useIndicators(symbol: string) {
  const indicators = useAppStore((state) => state.indicators);
  return indicators[symbol] || null;
}

/**
 * Hook for RSI display with color coding.
 */
export function useRSIStatus(rsi: number | null) {
  if (rsi === null) {
    return { status: 'neutral', color: 'gray' };
  }

  if (rsi < 30) {
    return { status: 'oversold', color: 'green' };
  } else if (rsi > 70) {
    return { status: 'overbought', color: 'red' };
  } else {
    return { status: 'neutral', color: 'gray' };
  }
}
