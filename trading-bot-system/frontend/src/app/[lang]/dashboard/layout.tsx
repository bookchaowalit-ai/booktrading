/**
 * Dashboard Layout
 * Provides consistent sidebar navigation across all dashboard pages
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import Sidebar from '@/components/Sidebar';
import { ToastProvider } from '@/components/ui/Toast';
import { ThemeProvider } from '@/contexts/ThemeProvider';
import { Bell, Menu, LogOut, Command, Globe } from 'lucide-react';
import { isAuthenticated, logout } from '@/services/auth';
import CommandPalette from '@/components/CommandPalette';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';
import { WSStatusIndicator } from '@/components/WSStatusIndicator';
import { Dropdown } from '@/components/ui';
import NotificationCenter from '@/components/NotificationCenter';
import MobileBottomNav from '@/components/MobileBottomNav';
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

  useEffect(() => {
    setMounted(true);
    fetchUnreadCount();
    const interval = setInterval(fetchUnreadCount, 15000);
    return () => clearInterval(interval);
  }, [fetchUnreadCount]);

  useEffect(() => {
    // Check if user is authenticated
    if (!isAuthenticated()) {
      // For demo, we'll allow access but in production redirect to login
    }
  }, [pathname]);

  const handleLogout = async () => {
    await logout();
    router.push(`/${locale}`);
  };

  const handleLanguageChange = (newLocale: string) => {
    // Replace current locale in pathname with new locale
    const newPathname = pathname.replace(`/${locale}`, `/${newLocale}`);
    router.push(newPathname);
  };

  // Keyboard shortcuts
  useKeyboardShortcuts([
    {
      key: 'k',
      ctrl: true,
      action: () => setIsCommandPaletteOpen(true),
    },
    {
      key: 'b',
      ctrl: true,
      action: () => setIsSidebarCollapsed(!isSidebarCollapsed),
    },
  ]);

  // Define available commands
  const commands = [
    {
      id: 'dashboard',
      label: 'Go to Dashboard',
      action: () => router.push(`/${locale}/dashboard`),
      shortcut: 'G D',
    },
    {
      id: 'trading',
      label: 'Go to Trading',
      action: () => router.push(`/${locale}/dashboard/trading`),
      shortcut: 'G T',
    },
    {
      id: 'portfolio',
      label: 'Go to Portfolio',
      action: () => router.push(`/${locale}/dashboard/portfolio`),
      shortcut: 'G P',
    },
    {
      id: 'settings',
      label: 'Go to Settings',
      action: () => router.push(`/${locale}/dashboard/settings`),
      shortcut: 'G S',
    },
    {
      id: 'toggle-theme',
      label: 'Toggle Dark Mode',
      action: () => document.documentElement.classList.toggle('dark'),
      shortcut: 'D',
    },
    {
      id: 'logout',
      label: 'Logout',
      action: handleLogout,
      shortcut: 'L',
    },
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
              {children}
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
