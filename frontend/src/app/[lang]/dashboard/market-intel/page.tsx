/**
 * Market Intelligence Dashboard Page
 * Cross-market opportunity scanner with alerts
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Crosshair,
  RefreshCw,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Globe,
  Activity,
  Zap,
  Clock,
  Filter,
} from 'lucide-react';
import { marketIntelService } from '@/services/market-intel';
import type {
  ScannerResult,
  MarketQuote,
  MarketSource,
  MarketAlert,
  MarketOverview,
  Severity,
} from '@/types/market-intel';
import Card from '@/components/ui/Card';

const SEVERITY_COLORS: Record<Severity, string> = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-yellow-500',
  low: 'bg-blue-500',
};

const SEVERITY_TEXT: Record<Severity, string> = {
  critical: 'text-red-600 dark:text-red-400',
  high: 'text-orange-600 dark:text-orange-400',
  medium: 'text-yellow-600 dark:text-yellow-400',
  low: 'text-blue-600 dark:text-blue-400',
};

const MARKET_ICONS: Record<string, any> = {
  crypto: DollarSign,
  stock: TrendingUp,
  forex: Globe,
  commodity: Activity,
  prediction: Zap,
};

export default function MarketIntelPage() {
  const [overview, setOverview] = useState<MarketOverview | null>(null);
  const [quotes, setQuotes] = useState<MarketQuote[]>([]);
  const [alerts, setAlerts] = useState<MarketAlert[]>([]);
  const [sources, setSources] = useState<MarketSource[]>([]);
  const [lastScan, setLastScan] = useState<ScannerResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isScanning, setIsScanning] = useState(false);
  const [selectedMarket, setSelectedMarket] = useState<string>('all');
  const [selectedSeverity, setSelectedSeverity] = useState<string>('all');

  const loadData = useCallback(async () => {
    try {
      const [overviewData, quotesData, alertsData, sourcesData, lastScanData] = await Promise.all([
        marketIntelService.getOverview(),
        marketIntelService.getQuotes(),
        marketIntelService.getAlerts(20),
        marketIntelService.getSources(),
        marketIntelService.getLastScan(),
      ]);

      setOverview(overviewData);
      setQuotes(quotesData.quotes || []);
      setAlerts(alertsData.alerts || []);
      setSources(sourcesData.sources || []);
      if ('scan_id' in lastScanData) {
        setLastScan(lastScanData as ScannerResult);
      }
    } catch (err) {
      console.error('Failed to load market intel:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    // Auto-refresh every 60 seconds
    const interval = setInterval(loadData, 60000);
    return () => clearInterval(interval);
  }, [loadData]);

  const handleScan = async () => {
    setIsScanning(true);
    try {
      const result = await marketIntelService.scan(0.4);
      setLastScan(result);
      // Refresh alerts after scan
      const alertsData = await marketIntelService.getAlerts(20);
      setAlerts(alertsData.alerts || []);
    } catch (err) {
      console.error('Scan failed:', err);
    } finally {
      setIsScanning(false);
    }
  };

  const filteredQuotes = selectedMarket === 'all'
    ? quotes
    : quotes.filter(q => q.market_type === selectedMarket);

  const filteredAlerts = selectedSeverity === 'all'
    ? alerts
    : alerts.filter(a => a.severity === selectedSeverity);

  if (isLoading) {
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
          <div className="space-y-2">
            <div className="h-7 w-48 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
            <div className="h-4 w-64 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="h-24 bg-gray-200 dark:bg-gray-700 rounded-xl animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-100 dark:bg-indigo-900/30 rounded-lg">
            <Crosshair className="w-8 h-8 text-indigo-600" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
              Market Intelligence
            </h1>
            <p className="text-gray-600 dark:text-gray-400">
              Cross-market opportunity scanner • {sources.length} sources active
            </p>
          </div>
        </div>
        <button
          onClick={handleScan}
          disabled={isScanning}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${isScanning ? 'animate-spin' : ''}`} />
          {isScanning ? 'Scanning...' : 'Scan Now'}
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {sources.map(source => {
          const Icon = MARKET_ICONS[source.market_type] || Activity;
          const marketData = overview?.[source.name];
          return (
            <motion.div
              key={source.name}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <Card className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <Icon className="w-5 h-5 text-gray-500" />
                  <span className="text-xs px-2 py-0.5 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 rounded-full">
                    Active
                  </span>
                </div>
                <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 capitalize">
                  {source.market_type}
                </h3>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {marketData?.instruments || 0}
                </p>
                <p className="text-xs text-gray-500">
                  {marketData?.opportunities || 0} opportunities
                </p>
              </Card>
            </motion.div>
          );
        })}
      </div>

      {/* Alerts Section */}
      {filteredAlerts.length > 0 && (
        <Card className="p-4">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-orange-500" />
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                High-Severity Alerts
              </h2>
              <span className="px-2 py-0.5 bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400 text-xs rounded-full">
                {filteredAlerts.length}
              </span>
            </div>
            <select
              value={selectedSeverity}
              onChange={e => setSelectedSeverity(e.target.value)}
              className="text-sm border border-gray-200 dark:border-gray-700 rounded-lg px-2 py-1 bg-white dark:bg-gray-800"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
            </select>
          </div>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            <AnimatePresence>
              {filteredAlerts.map(alert => (
                <motion.div
                  key={alert.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  className="flex items-start gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg"
                >
                  <div className={`w-2 h-2 rounded-full mt-2 ${SEVERITY_COLORS[alert.severity]}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-medium uppercase ${SEVERITY_TEXT[alert.severity]}`}>
                        {alert.severity}
                      </span>
                      <span className="text-xs text-gray-500">{alert.market}</span>
                      <span className="text-xs text-gray-400">•</span>
                      <span className="text-xs text-gray-500">{alert.source}</span>
                    </div>
                    <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                      {alert.title}
                    </p>
                    <p className="text-xs text-gray-500 truncate">{alert.description}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-mono text-gray-900 dark:text-white">
                      ${alert.price?.toLocaleString()}
                    </p>
                    <p className="text-xs text-gray-500">
                      {(alert.confidence * 100).toFixed(0)}% conf
                    </p>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </Card>
      )}

      {/* Live Quotes */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-green-500" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Live Quotes
            </h2>
          </div>
          <select
            value={selectedMarket}
            onChange={e => setSelectedMarket(e.target.value)}
            className="text-sm border border-gray-200 dark:border-gray-700 rounded-lg px-2 py-1 bg-white dark:bg-gray-800"
          >
            <option value="all">All Markets</option>
            <option value="crypto">Crypto</option>
            <option value="stock">Stocks</option>
            <option value="forex">Forex</option>
            <option value="commodity">Commodities</option>
          </select>
        </div>
        {filteredQuotes.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {filteredQuotes.map(quote => (
              <div
                key={quote.symbol}
                className="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-gray-900 dark:text-white">
                    {quote.symbol}
                  </span>
                  <span className="text-xs px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">
                    {quote.market_type}
                  </span>
                </div>
                <p className="text-lg font-mono font-bold text-gray-900 dark:text-white">
                  ${quote.price?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </p>
                {quote.change_pct_24h !== null && (
                  <div className={`flex items-center gap-1 text-xs ${quote.change_pct_24h >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {quote.change_pct_24h >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                    {quote.change_pct_24h >= 0 ? '+' : ''}{quote.change_pct_24h?.toFixed(2)}%
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-center text-gray-500 py-8">No quotes available for selected market</p>
        )}
      </Card>

      {/* Last Scan Info */}
      {lastScan && 'scan_id' in lastScan && (
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <Clock className="w-5 h-5 text-gray-500" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Last Scan Summary
            </h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {lastScan.total_opportunities}
              </p>
              <p className="text-xs text-gray-500">Total Opportunities</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-orange-600">
                {lastScan.by_severity?.high || 0}
              </p>
              <p className="text-xs text-gray-500">High Severity</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {lastScan.markets_scanned?.length || 0}
              </p>
              <p className="text-xs text-gray-500">Markets Scanned</p>
            </div>
            <div>
              <p className="text-xs text-gray-500 truncate">
                {new Date(lastScan.timestamp).toLocaleString()}
              </p>
              <p className="text-xs text-gray-500">Scan Time</p>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
