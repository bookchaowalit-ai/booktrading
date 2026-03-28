/**
 * Mobile Bottom Navigation
 * Mobile-friendly navigation bar
 */
'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  LayoutDashboard,
  Zap,
  Wallet,
  BarChart3,
  Settings,
} from 'lucide-react';

const navItems = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    href: '/dashboard',
    icon: LayoutDashboard,
  },
  {
    id: 'trading',
    label: 'Trading',
    href: '/dashboard/trading',
    icon: Zap,
  },
  {
    id: 'portfolio',
    label: 'Portfolio',
    href: '/dashboard/portfolio',
    icon: Wallet,
  },
  {
    id: 'analytics',
    label: 'Analytics',
    href: '/dashboard/analytics',
    icon: BarChart3,
  },
  {
    id: 'settings',
    label: 'Settings',
    href: '/dashboard/settings',
    icon: Settings,
  },
];

export default function MobileBottomNav() {
  const pathname = usePathname();

  // Extract locale from pathname
  const locale = pathname.split('/')[1] || 'th';

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 md:hidden z-50"
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
    >
      <div className="grid grid-cols-5 gap-1">
        {navItems.map((item) => {
          const isActive = pathname.includes(item.href);
          const Icon = item.icon;
          const href = `/${locale}${item.href}`;

          return (
            <Link
              key={item.id}
              href={href}
              className={`flex flex-col items-center justify-center py-3 px-2 transition-colors ${isActive
                  ? 'text-purple-600'
                  : 'text-gray-500 dark:text-gray-400'
                }`}
              aria-current={isActive ? 'page' : undefined}
            >
              <div className="relative">
                <Icon className="w-5 h-5" />
                {isActive && (
                  <motion.div
                    layoutId="mobile-nav-indicator"
                    className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-1 h-1 bg-purple-600 rounded-full"
                  />
                )}
              </div>
              <span className="text-xs mt-1">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
