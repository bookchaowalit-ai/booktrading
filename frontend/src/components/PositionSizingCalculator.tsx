/**
 * Position Sizing Calculator
 * Calculate optimal position size based on risk
 */
'use client';

import { useState, useEffect } from 'react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { Calculator, DollarSign, Percent, AlertCircle } from 'lucide-react';
import { useToast } from '@/components/ui/Toast';

interface PositionSizingCalculatorProps {
  accountBalance: number;
  entryPrice: number;
  stopLossPercent: number;
}

export default function PositionSizingCalculator({
  accountBalance = 10000,
  entryPrice = 50000,
  stopLossPercent = 5,
}: PositionSizingCalculatorProps) {
  const { success } = useToast();
  const [riskPercent, setRiskPercent] = useState(2);
  const [positionSize, setPositionSize] = useState(0);
  const [units, setUnits] = useState(0);
  const [maxLoss, setMaxLoss] = useState(0);

  useEffect(() => {
    calculatePositionSize();
  }, [riskPercent, entryPrice, stopLossPercent, accountBalance]);

  const calculatePositionSize = () => {
    // Risk amount = Account Balance * Risk %
    const riskAmount = accountBalance * (riskPercent / 100);

    // Position Size = Risk Amount / Stop-Loss %
    const positionSizeValue = riskAmount / (stopLossPercent / 100);

    // Units = Position Size / Entry Price
    const unitsValue = positionSizeValue / entryPrice;

    // Max Loss = Risk Amount
    const maxLossValue = riskAmount;

    setPositionSize(positionSizeValue);
    setUnits(unitsValue);
    setMaxLoss(maxLossValue);
  };

  const kellyCriterion = () => {
    // Simplified Kelly Criterion (assuming 50% win rate for demo)
    const winRate = 0.5;
    const avgWin = stopLossPercent * 2; // Assume 2:1 reward
    const avgLoss = stopLossPercent;

    const kelly = winRate - (1 - winRate) / (avgWin / avgLoss);
    return Math.max(0, kelly * 100).toFixed(2);
  };

  return (
    <Card variant="elevated" className="p-4">
      <div className="flex items-center gap-2 mb-4">
        <Calculator className="w-4 h-4 text-purple-600" />
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
          Position Sizing Calculator
        </h3>
      </div>

      <div className="space-y-4">
        {/* Account Balance */}
        <div>
          <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
            Account Balance
          </label>
          <div className="relative">
            <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="number"
              value={accountBalance}
              readOnly
              className="w-full pl-9 pr-3 py-2 text-sm bg-gray-100 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md"
            />
          </div>
        </div>

        {/* Risk Percentage */}
        <div>
          <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
            Risk per Trade (%)
          </label>
          <div className="relative">
            <Percent className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="number"
              value={riskPercent}
              onChange={(e) => setRiskPercent(parseFloat(e.target.value))}
              className="w-full pr-9 pl-3 py-2 text-sm bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md"
              step="0.1"
              min="0.1"
              max="10"
            />
          </div>
          <div className="flex gap-2 mt-2">
            {[1, 2, 3, 5].map((pct) => (
              <button
                key={pct}
                onClick={() => setRiskPercent(pct)}
                className={`flex-1 px-2 py-1 text-xs rounded ${
                  riskPercent === pct
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300'
                }`}
              >
                {pct}%
              </button>
            ))}
          </div>
        </div>

        {/* Entry Price */}
        <div>
          <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
            Entry Price
          </label>
          <div className="relative">
            <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="number"
              value={entryPrice}
              readOnly
              className="w-full pl-9 pr-3 py-2 text-sm bg-gray-100 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md"
            />
          </div>
        </div>

        {/* Stop-Loss % */}
        <div>
          <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
            Stop-Loss %
          </label>
          <div className="relative">
            <Percent className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="number"
              value={stopLossPercent}
              readOnly
              className="w-full pr-9 pl-3 py-2 text-sm bg-gray-100 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md"
            />
          </div>
        </div>

        {/* Results */}
        <div className="p-3 bg-purple-50 dark:bg-purple-900/10 rounded-lg space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-600 dark:text-gray-400">
              Position Size:
            </span>
            <span className="font-bold text-purple-600">
              ${positionSize.toFixed(2)}
            </span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-600 dark:text-gray-400">Units:</span>
            <span className="font-bold text-purple-600">
              {units.toFixed(6)}
            </span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-600 dark:text-gray-400">Max Loss:</span>
            <span className="font-bold text-red-600">
              ${maxLoss.toFixed(2)}
            </span>
          </div>
        </div>

        {/* Kelly Criterion */}
        <div className="p-3 bg-blue-50 dark:bg-blue-900/10 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <AlertCircle className="w-3 h-3 text-blue-600" />
            <span className="text-xs font-medium text-gray-900 dark:text-white">
              Kelly Criterion
            </span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-600 dark:text-gray-400">
              Optimal Risk:
            </span>
            <span className="font-bold text-blue-600">
              {kellyCriterion()}%
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Theoretical optimal position size for maximum growth
          </p>
        </div>

        {/* Risk Level Indicator */}
        <div>
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-gray-600 dark:text-gray-400">Risk Level:</span>
            <span
              className={`font-bold ${
                riskPercent <= 2
                  ? 'text-green-600'
                  : riskPercent <= 3
                  ? 'text-amber-600'
                  : 'text-red-600'
              }`}
            >
              {riskPercent <= 2
                ? 'Conservative'
                : riskPercent <= 3
                ? 'Moderate'
                : 'Aggressive'}
            </span>
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
            <div
              className={`h-2 rounded-full ${
                riskPercent <= 2
                  ? 'bg-green-600'
                  : riskPercent <= 3
                  ? 'bg-amber-600'
                  : 'bg-red-600'
              }`}
              style={{ width: `${Math.min(riskPercent * 10, 100)}%` }}
            />
          </div>
        </div>

        {/* Info */}
        <div className="p-2 bg-gray-50 dark:bg-gray-800/50 rounded text-xs text-gray-600 dark:text-gray-400">
          <p>
            💡 Recommended risk: 1-2% per trade for conservative trading
          </p>
        </div>
      </div>
    </Card>
  );
}
