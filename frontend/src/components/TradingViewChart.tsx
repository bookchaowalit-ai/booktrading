/**
 * TradingView Chart Component
 * Real-time price charts with indicators
 */
'use client';

import { useEffect, useRef } from 'react';

interface TradingViewChartProps {
  symbol: string;
  interval?: string;
  theme?: 'light' | 'dark';
  height?: number;
}

export default function TradingViewChart({
  symbol = 'BINANCE:BTCUSDT',
  interval = '60',
  theme = 'dark',
  height = 400,
}: TradingViewChartProps) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;

    // Clean up previous widget
    container.current.innerHTML = '';

    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
    script.type = 'text/javascript';
    script.async = true;
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol: symbol,
      interval: interval,
      timezone: 'Asia/Bangkok',
      theme: theme,
      style: '1',
      locale: 'en',
      enable_publishing: false,
      allow_symbol_change: true,
      calendar: false,
      support_host: 'https://www.tradingview.com',
      hide_top_toolbar: false,
      save_image: false,
      include_in_homepage: false,
    });

    container.current.appendChild(script);

    return () => {
      if (container.current) {
        container.current.innerHTML = '';
      }
    };
  }, [symbol, interval, theme]);

  return (
    <div
      ref={container}
      className="tradingview-widget-container"
      style={{ height: `${height}px`, width: '100%' }}
    >
      <div
        id="tradingview_chart"
        style={{ height: 'calc(100% - 32px)', width: '100%' }}
      />
    </div>
  );
}
