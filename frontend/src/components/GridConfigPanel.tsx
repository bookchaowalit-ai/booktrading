/**
 * GridConfigPanel — Runtime configuration for the real grid bot.
 * Fetches / updates per-symbol grid params via the strategy API.
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Settings,
  Save,
  RotateCcw,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  CheckCircle2,
  Loader2,
} from 'lucide-react';
import { api } from '@/services/api';
import { useToast } from '@/components/ui/Toast';

// ── Types ──────────────────────────────────────────────────────────────────────

interface GridConfig {
  symbol: string;
  grid_spacing_pct: number;
  grid_levels: number;
  order_size: number;
  max_position: number;
  poll_interval_sec: number;
  max_daily_loss_usd: number;
  max_open_orders: number;
  stale_threshold_pct: number;
  // Volatility-adaptive fields
  volatility_mode: string;
  atr_period: number;
  atr_multiplier: number;
  min_spacing_pct: number;
  max_spacing_pct: number;
}

interface GridConfigPanelProps {
  symbols?: string[];
}

// ── Component ──────────────────────────────────────────────────────────────────

export default function GridConfigPanel({ symbols = ['BTCTHB', 'ETHTHB', 'BNBTHB', 'SOLTHB', 'XRPTHB'] }: GridConfigPanelProps) {
  const { success, error: toastError } = useToast();

  const [expanded, setExpanded] = useState(false);
  const [activeSymbol, setActiveSymbol] = useState(symbols[0]);
  const [configs, setConfigs] = useState<Record<string, GridConfig | null>>({});
  const [edits, setEdits] = useState<Record<string, Partial<GridConfig>>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState<Set<string>>(new Set());

  const fetchConfigs = useCallback(async () => {
    setLoading(true);
    try {
      const results = await Promise.all(
        symbols.map(async (sym) => {
          const cfg = await api.getRealGridConfig(sym);
          return [sym, cfg] as const;
        })
      );
      const map: Record<string, GridConfig | null> = {};
      results.forEach(([sym, cfg]) => { map[sym] = cfg; });
      setConfigs(map);
    } catch {
      toastError('Failed to load grid config');
    } finally {
      setLoading(false);
    }
  }, [symbols]);

  useEffect(() => {
    fetchConfigs();
  }, [fetchConfigs]);

  const handleFieldChange = (symbol: string, field: keyof GridConfig, rawValue: string) => {
    const numVal = parseFloat(rawValue);
    if (isNaN(numVal)) return;

    setEdits((prev) => ({
      ...prev,
      [symbol]: { ...(prev[symbol] || {}), [field]: numVal },
    }));

    setDirty((prev) => {
      const next = new Set(prev);
      next.add(symbol);
      return next;
    });
  };

  const handleSave = async (symbol: string) => {
    const changes = edits[symbol];
    if (!changes || Object.keys(changes).length === 0) return;

    setSaving(true);
    try {
      await api.updateRealGridConfig(symbol, changes);
      success(`${symbol} config updated`);

      // Merge edits into configs
      setConfigs((prev) => ({
        ...prev,
        [symbol]: { ...(prev[symbol] as GridConfig), ...changes },
      }));

      // Clear edits for this symbol
      setEdits((prev) => {
        const next = { ...prev };
        delete next[symbol];
        return next;
      });
      setDirty((prev) => {
        const next = new Set(prev);
        next.delete(symbol);
        return next;
      });
    } catch (e: any) {
      toastError(e.message || `Failed to update ${symbol} config`);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = (symbol: string) => {
    setEdits((prev) => {
      const next = { ...prev };
      delete next[symbol];
      return next;
    });
    setDirty((prev) => {
      const next = new Set(prev);
      next.delete(symbol);
      return next;
    });
  };

  const currentConfig = configs[activeSymbol];
  const currentEdits = edits[activeSymbol] || {};
  const isDirty = dirty.has(activeSymbol);

  const getValue = (field: keyof GridConfig): number => {
    if (field in currentEdits) return currentEdits[field] as number;
    return Number(currentConfig?.[field] ?? 0);
  };

  const fields: { key: keyof GridConfig; label: string; hint: string; step: number; min: number }[] = [
    { key: 'grid_spacing_pct', label: 'Grid Spacing (%)', hint: 'Base distance between levels (fixed mode)', step: 0.1, min: 0.1 },
    { key: 'grid_levels', label: 'Grid Levels', hint: 'Number of buy/sell levels each side', step: 1, min: 1 },
    { key: 'order_size', label: 'Order Size', hint: 'Quantity per order (base asset)', step: 0.00001, min: 0 },
    { key: 'max_position', label: 'Max Position', hint: 'Maximum allowed position size', step: 0.001, min: 0 },
    { key: 'max_daily_loss_usd', label: 'Max Daily Loss (USD)', hint: 'Kill switch threshold', step: 1, min: 1 },
    { key: 'max_open_orders', label: 'Max Open Orders', hint: 'Safety limit for concurrent orders', step: 1, min: 1 },
    { key: 'poll_interval_sec', label: 'Poll Interval (sec)', hint: 'How often to check for fills', step: 1, min: 1 },
    { key: 'stale_threshold_pct', label: 'Stale Threshold (%)', hint: 'Cancel orders if price drifts this far', step: 0.1, min: 0.1 },
  ];

  // Volatility-adaptive fields (only shown when mode is 'atr')
  const volatilityFields: { key: keyof GridConfig; label: string; hint: string; step: number; min: number }[] = [
    { key: 'atr_period', label: 'ATR Period', hint: 'Number of candles for ATR calculation', step: 1, min: 5 },
    { key: 'atr_multiplier', label: 'ATR Multiplier', hint: 'Multiplier applied to ATR for spacing', step: 0.1, min: 0.5 },
    { key: 'min_spacing_pct', label: 'Min Spacing (%)', hint: 'Floor for dynamic spacing', step: 0.1, min: 0.1 },
    { key: 'max_spacing_pct', label: 'Max Spacing (%)', hint: 'Ceiling for dynamic spacing', step: 0.1, min: 0.5 },
  ];

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
      {/* Collapsible Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Settings className="w-5 h-5 text-indigo-500" />
          <h3 className="font-semibold text-gray-900 dark:text-white">Grid Configuration</h3>
          {dirty.size > 0 && (
            <span className="text-xs px-1.5 py-0.5 rounded bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400">
              {dirty.size} unsaved
            </span>
          )}
        </div>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        )}
      </button>

      {/* Expanded Content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 border-t border-gray-100 dark:border-gray-700 pt-4">
              {loading ? (
                <div className="flex items-center justify-center py-8 gap-2 text-gray-500">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Loading config...
                </div>
              ) : (
                <>
                  {/* Symbol Tabs */}
                  <div className="flex gap-2 mb-4">
                    {symbols.map((sym) => (
                      <button
                        key={sym}
                        onClick={() => setActiveSymbol(sym)}
                        className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                          activeSymbol === sym
                            ? 'bg-indigo-600 text-white'
                            : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                        }`}
                      >
                        {sym}
                        {dirty.has(sym) && (
                          <span className="ml-1.5 w-1.5 h-1.5 rounded-full bg-yellow-400 inline-block" />
                        )}
                      </button>
                    ))}
                  </div>

                  {!currentConfig ? (
                    <p className="text-sm text-gray-500 py-4">No config available for {activeSymbol}</p>
                  ) : (
                    <>
                      {/* Warning banner */}
                      {isDirty && (
                        <div className="flex items-center gap-2 mb-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700 rounded-lg">
                          <AlertTriangle className="w-4 h-4 text-yellow-600 dark:text-yellow-400 flex-shrink-0" />
                          <p className="text-sm text-yellow-800 dark:text-yellow-200">
                            Unsaved changes for {activeSymbol}. Changes take effect on next grid tick.
                          </p>
                        </div>
                      )}

                      {/* Volatility Mode Selector */}
                      <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                          Spacing Mode
                        </label>
                        <div className="flex gap-3">
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="radio"
                              name="volatility_mode"
                              value="fixed"
                              checked={(currentEdits.volatility_mode || currentConfig.volatility_mode) === 'fixed'}
                              onChange={() => {
                                setEdits((prev) => ({
                                  ...prev,
                                  [activeSymbol]: { ...(prev[activeSymbol] || {}), volatility_mode: 'fixed' as any },
                                }));
                                setDirty((prev) => { const n = new Set(prev); n.add(activeSymbol); return n; });
                              }}
                              className="w-4 h-4 text-indigo-600"
                            />
                            <span className="text-sm text-gray-700 dark:text-gray-300">Fixed %</span>
                          </label>
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="radio"
                              name="volatility_mode"
                              value="atr"
                              checked={(currentEdits.volatility_mode || currentConfig.volatility_mode) === 'atr'}
                              onChange={() => {
                                setEdits((prev) => ({
                                  ...prev,
                                  [activeSymbol]: { ...(prev[activeSymbol] || {}), volatility_mode: 'atr' as any },
                                }));
                                setDirty((prev) => { const n = new Set(prev); n.add(activeSymbol); return n; });
                              }}
                              className="w-4 h-4 text-indigo-600"
                            />
                            <span className="text-sm text-gray-700 dark:text-gray-300">ATR Adaptive</span>
                          </label>
                        </div>
                        <p className="text-xs text-gray-500 mt-1">
                          {(currentEdits.volatility_mode || currentConfig.volatility_mode) === 'atr'
                            ? 'Dynamic spacing adjusts to market volatility using Average True Range'
                            : 'Fixed percentage spacing between grid levels'}
                        </p>
                      </div>

                      {/* Fields Grid */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                        {fields.map(({ key, label, hint, step, min }) => (
                          <div key={key}>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                              {label}
                            </label>
                            <input
                              type="number"
                              value={getValue(key)}
                              step={step}
                              min={min}
                              onChange={(e) => handleFieldChange(activeSymbol, key, e.target.value)}
                              className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                            />
                            <p className="text-xs text-gray-400 mt-0.5">{hint}</p>
                          </div>
                        ))}
                      </div>

                      {/* Volatility-Adaptive Fields (only when ATR mode) */}
                      {(currentEdits.volatility_mode || currentConfig.volatility_mode) === 'atr' && (
                        <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-green-500"></span>
                            ATR Adaptive Settings
                          </h4>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {volatilityFields.map(({ key, label, hint, step, min }) => (
                              <div key={key}>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                  {label}
                                </label>
                                <input
                                  type="number"
                                  value={getValue(key)}
                                  step={step}
                                  min={min}
                                  onChange={(e) => handleFieldChange(activeSymbol, key, e.target.value)}
                                  className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                                />
                                <p className="text-xs text-gray-400 mt-0.5">{hint}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Action Buttons */}
                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => handleSave(activeSymbol)}
                          disabled={!isDirty || saving}
                          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors"
                        >
                          {saving ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Save className="w-4 h-4" />
                          )}
                          {saving ? 'Saving...' : 'Save Changes'}
                        </button>

                        {isDirty && (
                          <button
                            onClick={() => handleReset(activeSymbol)}
                            className="flex items-center gap-2 px-4 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 rounded-lg text-sm font-medium transition-colors"
                          >
                            <RotateCcw className="w-4 h-4" />
                            Discard
                          </button>
                        )}

                        {isDirty && (
                          <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                            <CheckCircle2 className="w-3 h-3" />
                            Ready to apply
                          </span>
                        )}
                      </div>
                    </>
                  )}
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
