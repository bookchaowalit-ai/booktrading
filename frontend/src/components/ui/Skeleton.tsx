/**
 * Compact Loading Skeletons
 * Shopify-style loading states
 */
import { motion } from 'framer-motion';

interface SkeletonProps {
  className?: string;
}

function Skeleton({ className = '' }: SkeletonProps) {
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

export default Skeleton;
