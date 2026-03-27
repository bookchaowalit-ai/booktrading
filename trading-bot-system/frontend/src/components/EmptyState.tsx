/**
 * Empty State Components
 * Shopify-style empty states with illustrations
 */
import { motion } from 'framer-motion';
import { Inbox, TrendingUp, Wallet, BarChart3, Settings, Zap } from 'lucide-react';
import Button from './ui/Button';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  size?: 'sm' | 'md' | 'lg';
}

const icons = {
  inbox: Inbox,
  trades: TrendingUp,
  portfolio: Wallet,
  analytics: BarChart3,
  settings: Settings,
  trading: Zap,
};

export default function EmptyState({
  icon = <Inbox className="w-12 h-12" />,
  title,
  description,
  action,
  size = 'md',
}: EmptyStateProps) {
  const sizes = {
    sm: 'p-6',
    md: 'p-8',
    lg: 'p-12',
  };

  const iconSizes = {
    sm: 'w-8 h-8',
    md: 'w-12 h-12',
    lg: 'w-16 h-16',
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={`text-center ${sizes[size]}`}
    >
      <div className="inline-flex items-center justify-center w-16 h-16 bg-gray-100 dark:bg-gray-800 rounded-full mb-4">
        {icon}
      </div>
      <h3 className={`font-semibold text-gray-900 dark:text-white mb-2 ${size === 'sm' ? 'text-sm' : 'text-base'}`}>
        {title}
      </h3>
      {description && (
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-4 max-w-sm mx-auto">
          {description}
        </p>
      )}
      {action && (
        <Button onClick={action.onClick} size={size === 'lg' ? 'md' : 'sm'}>
          {action.label}
        </Button>
      )}
    </motion.div>
  );
}

// Pre-built empty states
export function NoTradesEmptyState() {
  return (
    <EmptyState
      icon={<TrendingUp className="w-10 h-10 text-gray-400" />}
      title="No trades yet"
      description="Start trading to see your trade history here"
      action={{
        label: 'Start Trading',
        onClick: () => (window.location.href = '/dashboard/trading'),
      }}
    />
  );
}

export function NoPortfolioEmptyState() {
  return (
    <EmptyState
      icon={<Wallet className="w-10 h-10 text-gray-400" />}
      title="Portfolio is empty"
      description="Your portfolio will appear here once you start trading"
      action={{
        label: 'View Markets',
        onClick: () => (window.location.href = '/dashboard/trading'),
      }}
    />
  );
}

export function NoHoldingsEmptyState({ onAction }: { onAction?: () => void }) {
  return (
    <EmptyState
      icon={<Wallet className="w-10 h-10 text-gray-400" />}
      title="No holdings yet"
      description="Start trading to build your portfolio"
      action={onAction ? {
        label: 'Start Trading',
        onClick: onAction,
      } : undefined}
    />
  );
}

export function NoAnalyticsEmptyState() {
  return (
    <EmptyState
      icon={<BarChart3 className="w-10 h-10 text-gray-400" />}
      title="No analytics yet"
      description="Trading data will appear here after you start trading"
    />
  );
}

export function NoSettingsEmptyState() {
  return (
    <EmptyState
      icon={<Settings className="w-10 h-10 text-gray-400" />}
      title="No settings configured"
      description="Configure your preferences to get started"
    />
  );
}
