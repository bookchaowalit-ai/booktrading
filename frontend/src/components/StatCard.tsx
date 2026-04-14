/**
 * Stat Card Component
 * Enhanced statistics card with trend indicator
 */
'use client';

import { motion } from 'framer-motion';
import { ReactNode } from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import Card from './ui/Card';

interface StatCardProps {
  title: string;
  value: string | number;
  icon?: ReactNode;
  trend?: number;
  trendLabel?: string;
  color?: string;
  delay?: number;
  onClick?: () => void;
  subtitle?: string;
}

export default function StatCard({
  title,
  value,
  icon,
  trend,
  trendLabel,
  color = '#8B5CF6',
  delay = 0,
  onClick,
  subtitle,
}: StatCardProps) {
  const isPositive = trend && trend >= 0;
  const isNeutral = trend === 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.3 }}
    >
      <Card
        variant="elevated"
        hover
        onClick={onClick}
        className="relative overflow-hidden group"
      >
        {/* Background Gradient */}
        <div
          className="absolute inset-0 opacity-0 group-hover:opacity-10 transition-opacity duration-300"
          style={{
            background: `radial-gradient(circle at top right, ${color}40, transparent)`,
          }}
        />

        <div className="relative">
          {/* Header */}
          <div className="flex items-start justify-between mb-4">
            <div>
              <p className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">
                {title}
              </p>
              <p className="text-2xl font-bold text-gray-900 dark:text-white">
                {typeof value === 'number' ? value.toLocaleString() : value}
              </p>
              {subtitle && (
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {subtitle}
                </p>
              )}
            </div>

            {icon && (
              <div
                className="p-2.5 rounded-lg"
                style={{
                  backgroundColor: `${color}20`,
                  color: color,
                }}
              >
                {icon}
              </div>
            )}
          </div>

          {/* Trend */}
          {trend !== undefined && (
            <div className="flex items-center gap-2">
              {isPositive ? (
                <TrendingUp className="w-4 h-4 text-green-500" />
              ) : isNeutral ? (
                <Minus className="w-4 h-4 text-gray-400" />
              ) : (
                <TrendingDown className="w-4 h-4 text-red-500" />
              )}
              <span
                className={`text-sm font-medium ${isNeutral
                    ? 'text-gray-500'
                    : isPositive
                      ? 'text-green-600'
                      : 'text-red-600'
                  }`}
              >
                {isPositive ? '+' : ''}{trend.toFixed(2)}%
              </span>
              {trendLabel && (
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {trendLabel}
                </span>
              )}
            </div>
          )}
        </div>
      </Card>
    </motion.div>
  );
}
