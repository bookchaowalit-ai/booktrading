/**
 * Bot Control Component - Enhanced with Leverage and Position Direction
 * Provides Start/Stop button with leverage and long/short options
 */
'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useBotControl } from '@/hooks';
import { useToast } from './ui/Toast';
import Card from './ui/Card';
import Button from './ui/Button';
import {
  Zap,
  TrendingUp,
  TrendingDown,
  Settings,
  Activity,
  Shield,
  AlertTriangle,
  CheckCircle,
} from 'lucide-react';

interface BotControlProps {
  onPositionChange?: (direction: 'LONG' | 'SHORT', leverage: number) => void;
}

export default function BotControl({ onPositionChange }: BotControlProps) {
  const { success, warning } = useToast();
  const { isActive, isLoading, startBot, stopBot, totalTrades, totalProfit } = useBotControl();

  const [leverage, setLeverage] = useState(3);
  const [positionMode, setPositionMode] = useState<'LONG' | 'SHORT' | 'AUTO'>('AUTO');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showStartConfirm, setShowStartConfirm] = useState(false);

  const handleStartBot = () => {
    if (leverage > 5) {
      warning('High leverage detected. Please trade responsibly.');
    }
    startBot();
    success(`Bot started in ${positionMode} mode with ${leverage}x leverage`);
    setShowStartConfirm(false);
  };

  const handleStopBot = () => {
    stopBot();
    success('Bot stopped');
  };

  const handlePositionChange = (direction: 'LONG' | 'SHORT' | 'AUTO') => {
    setPositionMode(direction);
    if (direction !== 'AUTO' && onPositionChange) {
      onPositionChange(direction, leverage);
    }
    success(`Position mode set to ${direction}`);
  };

  const leverageOptions = [1, 2, 3, 5, 10, 20];

  return (
    <Card variant="elevated" className="p-6" gradient>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Zap className="w-6 h-6 text-purple-600" />
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            Bot Control
          </h2>
        </div>

        <motion.div
          animate={{ rotate: isActive ? 360 : 0 }}
          transition={{ duration: 2, repeat: isActive ? Infinity : 0, ease: 'linear' }}
        >
          <Activity className={`w-5 h-5 ${isActive ? 'text-green-500' : 'text-gray-400'}`} />
        </motion.div>
      </div>

      {/* Status Indicator */}
      <div className="flex items-center justify-between mb-6 p-4 bg-white/50 dark:bg-gray-800/50 rounded-lg">
        <div className="flex items-center gap-3">
          <motion.div
            animate={{ scale: isActive ? [1, 1.2, 1] : 1 }}
            transition={{ duration: 1, repeat: isActive ? Infinity : 0 }}
            className={`w-3 h-3 rounded-full ${isActive ? 'bg-green-500' : 'bg-gray-400'}`}
          />
          <span className="text-lg font-medium text-gray-700 dark:text-gray-300">
            {isActive ? 'Running' : 'Stopped'}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {positionMode !== 'AUTO' && (
            <span
              className={`px-3 py-1 rounded-full text-xs font-bold ${positionMode === 'LONG'
                  ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                  : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                }`}
            >
              {positionMode} {leverage}x
            </span>
          )}
          {positionMode === 'AUTO' && (
            <span className="px-3 py-1 rounded-full text-xs font-bold bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">
              AI Auto
            </span>
          )}
        </div>
      </div>

      {/* Start Confirmation Panel */}
      <AnimatePresence>
        {showStartConfirm && !isActive && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700 rounded-lg"
          >
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="w-4 h-4 text-yellow-600 dark:text-yellow-400 flex-shrink-0" />
              <p className="text-sm font-medium text-yellow-800 dark:text-yellow-200">
                Start bot in {positionMode} mode with {leverage}x leverage?
              </p>
            </div>
            <div className="flex gap-2">
              <Button size="sm" gradient onClick={handleStartBot}>
                Confirm Start
              </Button>
              <Button size="sm" variant="secondary" onClick={() => setShowStartConfirm(false)}>
                Cancel
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Start/Stop Button */}
      <Button
        fullWidth
        size="lg"
        gradient
        onClick={isActive ? handleStopBot : () => setShowStartConfirm(true)}
        isLoading={isLoading}
        leftIcon={isActive ? <Shield className="w-5 h-5" /> : <Zap className="w-5 h-5" />}
        className="mb-6"
      >
        {isLoading ? 'Processing...' : isActive ? 'Stop Bot' : 'Start Bot'}
      </Button>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-white/50 dark:bg-gray-800/50 rounded-lg p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">Total Trades</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">{totalTrades}</p>
        </div>

        <div className="bg-white/50 dark:bg-gray-800/50 rounded-lg p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">Total P&L</p>
          <p className={`text-2xl font-bold ${totalProfit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {totalProfit >= 0 ? '+' : ''}${totalProfit.toFixed(2)}
          </p>
        </div>
      </div>

      {/* Advanced Settings Toggle */}
      <button
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 hover:text-purple-600 dark:hover:text-purple-400 transition-colors mb-4"
      >
        <Settings className={`w-4 h-4 transition-transform ${showAdvanced ? 'rotate-90' : ''}`} />
        {showAdvanced ? 'Hide' : 'Show'} Advanced Settings
      </button>

      {/* Advanced Settings */}
      <AnimatePresence>
        {showAdvanced && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden space-y-4"
          >
            {/* Position Mode */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Position Mode
              </label>
              <div className="grid grid-cols-3 gap-2">
                {(['AUTO', 'LONG', 'SHORT'] as const).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => handlePositionChange(mode)}
                    className={`px-3 py-2 rounded-lg text-sm font-medium transition-all flex items-center justify-center gap-2 ${positionMode === mode
                        ? mode === 'LONG'
                          ? 'bg-green-600 text-white'
                          : mode === 'SHORT'
                            ? 'bg-red-600 text-white'
                            : 'bg-purple-600 text-white'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                      }`}
                  >
                    {mode === 'LONG' && <TrendingUp className="w-4 h-4" />}
                    {mode === 'SHORT' && <TrendingDown className="w-4 h-4" />}
                    {mode === 'AUTO' && <Zap className="w-4 h-4" />}
                    {mode}
                  </button>
                ))}
              </div>
              {positionMode === 'AUTO' && (
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 flex items-center gap-1">
                  <CheckCircle className="w-3 h-3 text-green-500" />
                  AI will decide position based on sentiment analysis
                </p>
              )}
            </div>

            {/* Leverage Selector */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Leverage
              </label>
              <div className="grid grid-cols-6 gap-2">
                {leverageOptions.map((lev) => (
                  <button
                    key={lev}
                    onClick={() => setLeverage(lev)}
                    className={`px-2 py-2 rounded-lg text-sm font-medium transition-all ${leverage === lev
                        ? 'bg-purple-600 text-white'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                      }`}
                  >
                    {lev}x
                  </button>
                ))}
              </div>

              {/* Leverage Warning */}
              {leverage >= 10 && (
                <div className="mt-2 flex items-center gap-2 text-xs text-orange-600 dark:text-orange-400">
                  <AlertTriangle className="w-3 h-3" />
                  High leverage increases risk significantly
                </div>
              )}
            </div>

            {/* Position Change Handler */}
            {positionMode !== 'AUTO' && (
              <Button
                fullWidth
                variant={positionMode === 'LONG' ? 'success' : 'danger'}
                onClick={() => onPositionChange?.(positionMode, leverage)}
                leftIcon={positionMode === 'LONG' ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
              >
                Update Position: {positionMode} {leverage}x
              </Button>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
}
