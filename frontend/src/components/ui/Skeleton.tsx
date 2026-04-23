/**
 * Compact Loading Skeletons
 * Shopify-style loading states
 */
import { motion } from 'framer-motion';

interface SkeletonProps {
  className?: string;
  style?: React.CSSProperties;
}

function Skeleton({ className = '', style }: SkeletonProps) {
  return (
    <motion.div
      animate={{
        background: [
          'rgb(229 231 235)',
          'rgb(243 244 246)',
          'rgb(229 231 235)',
        ],
      }}
      transition={{
        duration: 1.5,
        repeat: Infinity,
        ease: 'linear',
      }}
      className={`bg-gray-200 dark:bg-gray-700 ${className}`}
      style={style}
    />
  );
}

// Compact Card Skeleton
export function CompactCardSkeleton() {
  return (
    <div className="p-4 space-y-3">
      <div className="flex items-center gap-3">
        <Skeleton className="w-8 h-8 rounded-lg" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-2 w-16" />
        </div>
      </div>
      <Skeleton className="h-8 w-full" />
    </div>
  );
}

// Compact Stats Grid Skeleton
export function CompactStatsGridSkeleton() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="p-3 space-y-2">
          <Skeleton className="h-2 w-16" />
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-2 w-12" />
        </div>
      ))}
    </div>
  );
}

// Compact Table Skeleton
export function CompactTableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2 p-3">
      <div className="flex gap-3">
        <Skeleton className="h-3 w-20 flex-1" />
        <Skeleton className="h-3 w-20 flex-1" />
        <Skeleton className="h-3 w-20 flex-1" />
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-3">
          <Skeleton className="h-3 w-20 flex-1" />
          <Skeleton className="h-3 w-20 flex-1" />
          <Skeleton className="h-3 w-20 flex-1" />
        </div>
      ))}
    </div>
  );
}

// Compact List Skeleton
export function CompactListSkeleton({ items = 5 }: { items?: number }) {
  return (
    <div className="space-y-2 p-3">
      {Array.from({ length: items }).map((_, i) => (
        <div key={i} className="flex items-center gap-3">
          <Skeleton className="w-8 h-8 rounded" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-2.5 w-3/4" />
            <Skeleton className="h-2 w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
}

// Backwards compatibility aliases
export const CardSkeleton = CompactCardSkeleton;
export const TableSkeleton = CompactTableSkeleton;
export const StatsGridSkeleton = CompactStatsGridSkeleton;

// Chart Skeleton - for price charts and analytics
export function ChartSkeleton({ height = 300 }: { height?: number }) {
  return (
    <div className="p-4 space-y-3">
      <div className="flex justify-between items-center">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-6 w-20" />
      </div>
      <Skeleton className="w-full" style={{ height }} />
      <div className="flex gap-2">
        {[1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} className="h-6 w-12 rounded" />
        ))}
      </div>
    </div>
  );
}

// Text Skeleton - for paragraphs and descriptions
export function TextSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={`h-3 w-full ${i === lines - 1 ? 'w-2/3' : ''}`}
        />
      ))}
    </div>
  );
}

// Circle Avatar Skeleton
export function AvatarSkeleton({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const sizes = { sm: 'w-8 h-8', md: 'w-10 h-10', lg: 'w-12 h-12' };
  return <Skeleton className={`${sizes[size]} rounded-full`} />;
}

// Button Skeleton
export function ButtonSkeleton({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const sizes = { sm: 'h-8', md: 'h-10', lg: 'h-12' };
  return <Skeleton className={`w-24 ${sizes[size]} rounded-lg`} />;
}

// Trading Config Skeleton - specific for grid config form
export function TradingConfigSkeleton() {
  return (
    <div className="space-y-4 p-4">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="space-y-2">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-9 w-full rounded-lg" />
        </div>
      ))}
      <div className="flex gap-2 pt-4">
        <Skeleton className="h-9 w-20 rounded-lg" />
        <Skeleton className="h-9 w-20 rounded-lg" />
      </div>
    </div>
  );
}

// Portfolio Item Skeleton
export function PortfolioItemSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="space-y-2 p-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-center justify-between p-3">
          <div className="flex items-center gap-3">
            <Skeleton className="w-10 h-10 rounded-full" />
            <div className="space-y-2">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-2 w-16" />
            </div>
          </div>
          <div className="text-right space-y-2">
            <Skeleton className="h-3 w-16 ml-auto" />
            <Skeleton className="h-2 w-12 ml-auto" />
          </div>
        </div>
      ))}
    </div>
  );
}

export default Skeleton;
