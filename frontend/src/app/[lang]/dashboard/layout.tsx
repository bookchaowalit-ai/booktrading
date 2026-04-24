/**
 * Dashboard Layout
 * Provides consistent sidebar navigation across all dashboard pages
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import Sidebar from '@/components/Sidebar';
import { ToastProvider } from '@/components/ui/Toast';
import ErrorBoundary from '@/components/ErrorBoundary';
import { ThemeProvider } from '@/contexts/ThemeProvider';
import { Bell, Menu, LogOut, Command, Globe, Sun, Moon } from 'lucide-react';
import { isAuthenticated, logout, clearSession } from '@/services/auth';
import CommandPalette from '@/components/CommandPalette';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';
import { WSStatusIndicator } from '@/components/WSStatusIndicator';
import ThemeToggle from '@/components/ThemeToggle';
import { Dropdown } from '@/components/ui';
import NotificationCenter from '@/components/NotificationCenter';
import MobileBottomNav from '@/components/MobileBottomNav';
import KeyboardShortcutsHelp from '@/components/KeyboardShortcutsHelp';
import { api } from '@/services/api';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  // Extract locale from pathname, e.g. /en/dashboard → "en"
  const locale = pathname.split('/')[1] || 'th';

  const fetchUnreadCount = useCallback(async () => {
    try {
      const notifs = await api.getNotifications();
      setUnreadCount(notifs.filter((n: { read: boolean }) => !n.read).length);
    } catch {
      // ignore
    }
  }, []);

  // Validate session against backend every 2 minutes — catches token invalidated by server restart
  const validateSession = useCallback(async () => {
    if (!isAuthenticated()) return;
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch('/api/auth/me', {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.status === 401) {
        clearSession();
        router.push(`/${locale}`);
      }
    } catch {
      // network error — don't force logout, just wait for next check
    }
  }, [locale, router]);

  useEffect(() => {
    setMounted(true);
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 15000);

    // Validate token every 2 minutes to detect server-side invalidation (e.g. restart)
    const sessionInterval = setInterval(validateSession, 2 * 60 * 1000);
    return () => {
      clearInterval(interval);
      clearInterval(sessionInterval);
    };
  }, [fetchUnreadCount, validateSession]);

  useEffect(() => {
    // Only run auth check after component is mounted (client-side only)
    if (!mounted) return;

    // Check authentication after a small delay to ensure localStorage is ready
    const timer = setTimeout(() => {
      const authenticated = isAuthenticated();
      if (!authenticated) {
        console.log('[DashboardLayout] Not authenticated, redirecting to landing');
        router.push(`/${locale}`);
      } else {
        console.log('[DashboardLayout] Authenticated, staying on dashboard');
      }
    }, 50); // 50ms delay to ensure localStorage is ready

    return () => clearTimeout(timer);
  }, [mounted]); // Only depend on mounted to run once

  const handleLogout = async () => {
    await logout();
    router.push(`/${locale}`);
  };

  const handleLanguageChange = (newLocale: string) => {
    // Replace current locale in pathname with new locale
    const newPathname = pathname.replace(`/${locale}`, `/${newLocale}`);
    router.push(newPathname);
  };

  // Keyboard shortcuts - comprehensive set
  useKeyboardShortcuts([
    { key: 'k', ctrl: true, action: () => setIsCommandPaletteOpen(true) },
    { key: 'b', ctrl: true, action: () => setIsSidebarCollapsed(!isSidebarCollapsed) },
    // Navigation shortcuts
    { key: 'g', ctrl: true, alt: true, action: () => router.push(`/${locale}/dashboard`) },
    { key: 't', ctrl: true, alt: true, action: () => router.push(`/${locale}/dashboard/trading`) },
    { key: 'p', ctrl: true, alt: true, action: () => router.push(`/${locale}/dashboard/portfolio`) },
    { key: 'w', ctrl: true, alt: true, action: () => router.push(`/${locale}/dashboard/wallet`) },
    { key: 'f', ctrl: true, alt: true, action: () => router.push(`/${locale}/dashboard/finance`) },
    { key: 's', ctrl: true, alt: true, action: () => router.push(`/${locale}/dashboard/settings`) },
    // Bot control
    {
      key: ' ', ctrl: true, action: () => {
        // Space + Ctrl to start/stop bot (navigate to trading page)
        router.push(`/${locale}/dashboard/trading`);
      }
    },
  ]);

  // Define available commands
  const commands = [
    { id: 'dashboard', label: 'Go to Dashboard', action: () => router.push(`/${locale}/dashboard`), shortcut: 'G D' },
    { id: 'trading', label: 'Go to Trading', action: () => router.push(`/${locale}/dashboard/trading`), shortcut: 'G T' },
    { id: 'portfolio', label: 'Go to Portfolio', action: () => router.push(`/${locale}/dashboard/portfolio`), shortcut: 'G P' },
    { id: 'wallet', label: 'Go to Wallet', action: () => router.push(`/${locale}/dashboard/wallet`), shortcut: 'G W' },
    { id: 'strategy', label: 'Go to Strategy', action: () => router.push(`/${locale}/dashboard/strategy`), shortcut: 'G S' },
    { id: 'dex', label: 'Go to DEX Trading', action: () => router.push(`/${locale}/dashboard/dex`) },
    { id: 'grid-trading', label: 'Go to Grid Trading', action: () => router.push(`/${locale}/dashboard/grid-trading`) },
    { id: 'dca', label: 'Go to DCA Bot', action: () => router.push(`/${locale}/dashboard/dca`) },
    { id: 'copy-trading', label: 'Go to Copy Trading', action: () => router.push(`/${locale}/dashboard/copy-trading`) },
    { id: 'analytics', label: 'Go to Analytics', action: () => router.push(`/${locale}/dashboard/analytics`) },
    { id: 'sentiment', label: 'Go to Sentiment', action: () => router.push(`/${locale}/dashboard/sentiment`) },
    { id: 'backtest', label: 'Go to Backtest', action: () => router.push(`/${locale}/dashboard/backtest`) },
    { id: 'risk-management', label: 'Go to Risk Management', action: () => router.push(`/${locale}/dashboard/risk-management`) },
    { id: 'finance', label: 'Go to Finance', action: () => router.push(`/${locale}/dashboard/finance`) },
    { id: 'finance-budgets', label: 'Go to Budgets', action: () => router.push(`/${locale}/dashboard/finance/budgets`) },
    { id: 'finance-diary', label: 'Go to Financial Diary', action: () => router.push(`/${locale}/dashboard/finance/diary`) },
    { id: 'history', label: 'Go to History', action: () => router.push(`/${locale}/dashboard/history`) },
    { id: 'alerts', label: 'Go to Alerts', action: () => router.push(`/${locale}/dashboard/alerts`) },
    { id: 'paper-trading', label: 'Go to Paper Trading', action: () => router.push(`/${locale}/dashboard/paper-trading`) },
    { id: 'news', label: 'Go to News', action: () => router.push(`/${locale}/dashboard/news`) },
    { id: 'settings', label: 'Go to Settings', action: () => router.push(`/${locale}/dashboard/settings`), shortcut: 'G S' },
    { id: 'toggle-theme', label: 'Toggle Dark Mode', action: () => document.documentElement.classList.toggle('dark'), shortcut: 'D' },
    { id: 'logout', label: 'Logout', action: handleLogout, shortcut: 'L' },
  ];

  if (!mounted) {
    return null;
  }

  return (
    <ThemeProvider>
      <ToastProvider>
        <div className="min-h-screen bg-gray-100 dark:bg-gray-900">
          {/* Sidebar */}
          <Sidebar
            isCollapsed={isSidebarCollapsed}
            onToggle={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
            isMobileOpen={isMobileSidebarOpen}
            onMobileClose={() => setIsMobileSidebarOpen(false)}
          />

          {/* Main Content */}
          <main
            className={`transition-all duration-300 ${isSidebarCollapsed ? 'ml-20' : 'ml-72'
              }`}
          >
            {/* Top Navigation */}
            <nav className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700 sticky top-0 z-40">
              <div className="flex justify-between items-center h-16 px-6">
                {/* Mobile menu button */}
                <button
                  onClick={() => setIsMobileSidebarOpen(true)}
                  className="lg:hidden text-gray-500 hover:text-gray-700 dark:text-gray-400"
                  aria-label="Open menu"
                >
                  <Menu className="w-6 h-6" />
                </button>

                {/* Page Title */}
                <div className="hidden lg:block">
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                    Trading Bot Pro
                  </h2>
                </div>

                <div className="flex-1"></div>

                <div className="flex items-center gap-4">
                  {/* WebSocket Status */}
                  <WSStatusIndicator />

                  {/* Theme Toggle */}
                  <ThemeToggle />

                  {/* Language Switcher */}
                  <div className="flex items-center gap-2">
                    <Globe className="w-4 h-4 text-gray-500" />
                    <Dropdown
                      options={[
                        { value: 'en', label: '🇬🇧 English' },
                        { value: 'th', label: '🇹🇭 ไทย' },
                      ]}
                      value={locale}
                      onChange={handleLanguageChange}
                      size="sm"
                    />
                  </div>

                  {/* Command Palette Trigger */}
                  <KeyboardShortcutsHelp />
                  <button
                    onClick={() => setIsCommandPaletteOpen(true)}
                    className="flex items-center gap-2 px-3 py-1.5 text-xs text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md"
                    title="Search commands (Ctrl+K)"
                  >
                    <Command className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline">Search</span>
                    <kbd className="px-1.5 py-0.5 text-xs bg-gray-200 dark:bg-gray-600 rounded">
                      Ctrl+K
                    </kbd>
                  </button>

                  {/* Notifications */}
                  <button
                    className="text-gray-500 hover:text-gray-700 dark:text-gray-400 relative"
                    aria-label={`Notifications${unreadCount > 0 ? `, ${unreadCount} unread` : ''}`}
                  >
                    <Bell className="w-5 h-5" />
                    {unreadCount > 0 && (
                      <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full text-xs text-white flex items-center justify-center">
                        {unreadCount > 9 ? '9+' : unreadCount}
                      </span>
                    )}
                  </button>

                  {/* User Profile */}
                  <div className="flex items-center gap-3 pl-4 border-l border-gray-200 dark:border-gray-700">
                    <div className="w-8 h-8 bg-purple-600 rounded-full flex items-center justify-center text-white font-semibold">
                      U
                    </div>
                    <button
                      onClick={handleLogout}
                      className="flex items-center gap-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 text-sm font-medium"
                    >
                      <span className="hidden sm:inline">Logout</span>
                      <LogOut className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            </nav>

            {/* Page Content - Scrollable */}
            <div className="p-4 overflow-y-auto">
              <ErrorBoundary>
                {children}
              </ErrorBoundary>
            </div>

            {/* Mobile Bottom Navigation */}
            <MobileBottomNav />
          </main>

          {/* Command Palette */}
          <CommandPalette
            isOpen={isCommandPaletteOpen}
            onClose={() => setIsCommandPaletteOpen(false)}
            commands={commands}
          />
        </div>
      </ToastProvider>
    </ThemeProvider>
  );
}
