/**
 * Stop-Loss & Take-Profit Component
 * Risk management for grid trading
 */
'use client';

import { useState, useEffect } from 'react';
import { api } from '@/services/api';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Toggle from '@/components/ui/Toggle';
import { Shield, TrendingUp, TrendingDown, AlertTriangle } from 'lucide-react';
import { useToast } from '@/components/ui/Toast';

interface StopLossTakeProfitProps {
  symbol: string;
  entryPrice: number;
  onConfigChange?: (config: StopLossTakeProfitConfig) => void;
}

interface StopLossTakeProfitConfig {
  enableStopLoss: boolean;
  stopLossPercent: number;
  stopLossPrice: number;
  enableTakeProfit: boolean;
  takeProfitPercent: number;
  takeProfitPrice: number;
  trailingStop: boolean;
  trailingPercent: number;
}

export default function StopLossTakeProfit({
  symbol,
  entryPrice,
  onConfigChange,
}: StopLossTakeProfitProps) {
  const { success, error } = useToast();
  const [isSaving, setIsSaving] = useState(false);
  const [config, setConfig] = useState<StopLossTakeProfitConfig>({
    enableStopLoss: false,
    stopLossPercent: 5,
    stopLossPrice: entryPrice * 0.95,
    enableTakeProfit: false,
    takeProfitPercent: 10,
    takeProfitPrice: entryPrice * 1.10,
    trailingStop: false,
    trailingPercent: 3,
  });

  // Load saved config from backend on mount
  useEffect(() => {
    if (!symbol) return;
    api.getSLTP(symbol).then((remote: any) => {
      if (!remote?.enabled) return;
      setConfig((prev) => ({
        ...prev,
        enableStopLoss: (remote.stopLossPercent ?? 0) > 0,
        stopLossPercent: remote.stopLossPercent ?? prev.stopLossPercent,
        stopLossPrice: remote.stopLossPrice ?? prev.stopLossPrice,
        enableTakeProfit: (remote.takeProfitPercent ?? 0) > 0,
        takeProfitPercent: remote.takeProfitPercent ?? prev.takeProfitPercent,
        takeProfitPrice: remote.takeProfitPrice ?? prev.takeProfitPrice,
        trailingStop: remote.trailingStop ?? false,
        trailingPercent: remote.trailingStopPercent ?? prev.trailingPercent,
      }));
    }).catch(() => { /* keep defaults if backend unavailable */ });
  }, [symbol]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleStopLossPercentChange = (percent: number) => {
    const price = entryPrice * (1 - percent / 100);
    setConfig((prev) => ({
      ...prev,
      stopLossPercent: percent,
      stopLossPrice: price,
    }));
  };

  const handleTakeProfitPercentChange = (percent: number) => {
    const price = entryPrice * (1 + percent / 100);
    setConfig((prev) => ({
      ...prev,
      takeProfitPercent: percent,
      takeProfitPrice: price,
    }));
  };

  const handleSave = async () => {
    if (config.enableStopLoss && config.enableTakeProfit) {
      if (config.stopLossPrice >= config.takeProfitPrice) {
        error('Stop-loss must be lower than take-profit');
        return;
      }
    }

    setIsSaving(true);
    try {
      await api.setSLTP({
        symbol,
        stopLossPercent: config.enableStopLoss ? config.stopLossPercent : 0,
        takeProfitPercent: config.enableTakeProfit ? config.takeProfitPercent : 0,
        stopLossPrice: config.stopLossPrice,
        takeProfitPrice: config.takeProfitPrice,
        trailingStop: config.trailingStop,
        trailingStopPercent: config.trailingPercent,
        enabled: config.enableStopLoss || config.enableTakeProfit,
      });
      onConfigChange?.(config);
      success('Risk management settings saved');
    } catch {
      error('Failed to save — backend unavailable');
    } finally {
      setIsSaving(false);
    }
  };

  const riskRewardRatio = config.enableStopLoss && config.enableTakeProfit
    ? (config.takeProfitPercent / config.stopLossPercent).toFixed(2)
    : 0;

  return (
    <Card variant="elevated" className="p-4">
      <div className="flex items-center gap-2 mb-4">
        <Shield className="w-4 h-4 text-blue-600" />
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
          Stop-Loss & Take-Profit
        </h3>
      </div>

      <div className="space-y-4">
        {/* Stop-Loss */}
        <div className="p-3 bg-red-50 dark:bg-red-900/10 rounded-lg">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <TrendingDown className="w-4 h-4 text-red-600" />
              <span className="text-sm font-medium text-gray-900 dark:text-white">
                Stop-Loss
              </span>
            </div>
            <Toggle
              checked={config.enableStopLoss}
              onChange={(checked) =>
                setConfig((prev) => ({ ...prev, enableStopLoss: checked }))
              }
              size="sm"
            />
          </div>

          {config.enableStopLoss && (
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
                  Stop-Loss Percentage
                </label>
                <input
                  type="number"
                  value={config.stopLossPercent}
                  onChange={(e) =>
                    handleStopLossPercentChange(parseFloat(e.target.value))
                  }
                  className="w-full px-3 py-2 text-xs bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md"
                  step="0.1"
                  min="0.1"
                  max="50"
                />
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-600 dark:text-gray-400">
                  Stop-Loss Price:
                </span>
                <span className="font-bold text-red-600">
                  ${config.stopLossPrice.toFixed(2)}
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs text-amber-600 dark:text-amber-400">
                <AlertTriangle className="w-3 h-3" />
                <span>
                  Max loss: {(config.stopLossPercent * entryPrice).toFixed(2)} per
                  unit
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Take-Profit */}
        <div className="p-3 bg-green-50 dark:bg-green-900/10 rounded-lg">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-green-600" />
              <span className="text-sm font-medium text-gray-900 dark:text-white">
                Take-Profit
              </span>
            </div>
            <Toggle
              checked={config.enableTakeProfit}
              onChange={(checked) =>
                setConfig((prev) => ({ ...prev, enableTakeProfit: checked }))
              }
              size="sm"
            />
          </div>

          {config.enableTakeProfit && (
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
                  Take-Profit Percentage
                </label>
                <input
                  type="number"
                  value={config.takeProfitPercent}
                  onChange={(e) =>
                    handleTakeProfitPercentChange(parseFloat(e.target.value))
                  }
                  className="w-full px-3 py-2 text-xs bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md"
                  step="0.1"
                  min="0.1"
                  max="200"
                />
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-600 dark:text-gray-400">
                  Take-Profit Price:
                </span>
                <span className="font-bold text-green-600">
                  ${config.takeProfitPrice.toFixed(2)}
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs text-green-600">
                <TrendingUp className="w-3 h-3" />
                <span>
                  Potential profit:{' '}
                  {(config.takeProfitPercent * entryPrice).toFixed(2)} per unit
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Risk/Reward Ratio */}
        {config.enableStopLoss && config.enableTakeProfit && (
          <div className="p-3 bg-blue-50 dark:bg-blue-900/10 rounded-lg">
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-600 dark:text-gray-400">
                Risk/Reward Ratio:
              </span>
              <span
                className={`font-bold ${parseFloat(riskRewardRatio as string) >= 2
                    ? 'text-green-600'
                    : 'text-amber-600'
                  }`}
              >
                1:{riskRewardRatio}
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              {parseFloat(riskRewardRatio as string) >= 2
                ? '✅ Good risk/reward ratio'
                : '⚠️ Consider higher take-profit or lower stop-loss'}
            </p>
          </div>
        )}

        {/* Trailing Stop */}
        <div className="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-purple-600" />
              <span className="text-sm font-medium text-gray-900 dark:text-white">
                Trailing Stop
              </span>
            </div>
            <Toggle
              checked={config.trailingStop}
              onChange={(checked) =>
                setConfig((prev) => ({ ...prev, trailingStop: checked }))
              }
              size="sm"
            />
          </div>

          {config.trailingStop && (
            <div>
              <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
                Trailing Percentage
              </label>
              <input
                type="number"
                value={config.trailingPercent}
                onChange={(e) =>
                  setConfig((prev) => ({
                    ...prev,
                    trailingPercent: parseFloat(e.target.value),
                  }))
                }
                className="w-full px-3 py-2 text-xs bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md"
                step="0.1"
                min="0.1"
                max="20"
              />
              <p className="text-xs text-gray-500 mt-1">
                Stop-loss will follow price up by {config.trailingPercent}%
              </p>
            </div>
          )}
        </div>

        {/* Save Button */}
        <Button fullWidth onClick={handleSave} size="sm" disabled={isSaving}>
          {isSaving ? 'Saving...' : 'Save Risk Management'}
        </Button>
      </div>
    </Card>
  );
}
