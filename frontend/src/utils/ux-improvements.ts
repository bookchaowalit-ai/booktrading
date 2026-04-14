/**
 * UX Improvements - Critical Fixes
 * Addresses high-priority UX issues from audit
 */
import React, { useState, useEffect } from 'react';

// 1. Add responsive sidebar behavior
// File: /components/Sidebar.tsx - Add these styles

/*
.sidebar-container {
  @apply fixed left-0 top-0 h-screen z-30 transition-transform duration-300 lg:translate-x-0;
}

.sidebar-hidden {
  @apply -translate-x-full lg:translate-x-0;
}

.sidebar-overlay {
  @apply fixed inset-0 bg-black/50 z-20 lg:hidden;
}
*/

// 2. Add aria-labels to navigation
export const navAriaLabels = {
  dashboard: 'Navigate to dashboard',
  gridTrading: 'Navigate to grid trading',
  portfolio: 'Navigate to portfolio',
  history: 'Navigate to trade history',
  analytics: 'Navigate to analytics',
  bot: 'Navigate to bot control',
  sentiment: 'Navigate to sentiment analysis',
  settings: 'Navigate to settings',
  docs: 'Navigate to documentation',
  backtest: 'Navigate to backtesting and paper trading',
};

// 3. Add colorblind-friendly patterns
export const colorblindPatterns = {
  bullish: 'url(#bullish-pattern)', // Diagonal lines
  bearish: 'url(#bearish-pattern)', // Crosshatch
  neutral: 'url(#neutral-pattern)', // Dots
};

// 4. Add reduced motion support
export const prefersReducedMotion = () => {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
};

// 5. Add focus trap utility for modals
export const createFocusTrap = (element: HTMLElement) => {
  const focusableElements = element.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  const firstElement = focusableElements[0] as HTMLElement;
  const lastElement = focusableElements[focusableElements.length - 1] as HTMLElement;

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key !== 'Tab') return;

    if (e.shiftKey) {
      if (document.activeElement === firstElement) {
        e.preventDefault();
        lastElement.focus();
      }
    } else {
      if (document.activeElement === lastElement) {
        e.preventDefault();
        firstElement.focus();
      }
    }
  };

  element.addEventListener('keydown', handleKeyDown);
  firstElement.focus();

  return () => {
    element.removeEventListener('keydown', handleKeyDown);
  };
};

// 6. Add toast limit configuration
export const toastConfig = {
  maxToasts: 5,
  defaultDuration: 5000,
  maxDuration: 10000,
};

// 7. Add form validation helpers
export const validateGridConfig = (config: any) => {
  const errors: string[] = [];

  if (config.lowerPrice >= config.upperPrice) {
    errors.push('Lower price must be less than upper price');
  }

  if (config.gridLevels < 2 || config.gridLevels > 100) {
    errors.push('Grid levels must be between 2 and 100');
  }

  if (config.investmentAmount <= 0) {
    errors.push('Investment amount must be greater than 0');
  }

  if (config.gridLevels > 0 && config.investmentAmount / config.gridLevels < 10) {
    errors.push('Investment per grid level must be at least $10');
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
};

// 8. Add debounce utility
export const debounce = <T extends (...args: any[]) => any>(
  func: T,
  wait: number
): ((...args: Parameters<T>) => void) => {
  let timeout: NodeJS.Timeout;
  return (...args: Parameters<T>) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
};

// 9. Add accessible chart descriptions
export const generateChartDescription = (data: any[], type: string) => {
  if (!data || data.length === 0) {
    return 'No data available for chart';
  }

  if (type === 'line' || type === 'area') {
    const values = data.map(d => d.value);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const avg = values.reduce((a, b) => a + b, 0) / values.length;
    const trend = values[values.length - 1] > values[0] ? 'upward' : 'downward';

    return `Chart showing ${data.length} data points. Range from ${min.toFixed(2)} to ${max.toFixed(2)}, average ${avg.toFixed(2)}. Overall ${trend} trend.`;
  }

  if (type === 'pie' || type === 'donut') {
    const total = data.reduce((sum, item) => sum + item.value, 0);
    const largest = data.reduce((max, item) => item.value > max.value ? item : max);
    
    return `Pie chart with ${data.length} segments. Largest segment is ${largest.name} at ${((largest.value / total) * 100).toFixed(1)}%.`;
  }

  return 'Chart visualization';
};

// 10. Add contrast checker
export const checkContrast = (fg: string, bg: string): { passes: boolean; ratio: number } => {
  // Simplified contrast checker - in production, use proper WCAG formula
  const getLuminance = (hex: string) => {
    const rgb = parseInt(hex.slice(1), 16);
    const r = (rgb >> 16) & 0xff;
    const g = (rgb >> 8) & 0xff;
    const b = (rgb >> 0) & 0xff;
    
    const a = [r, g, b].map(v => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    
    return a[0] * 0.2126 + a[1] * 0.7152 + a[2] * 0.0722;
  };

  const l1 = getLuminance(fg);
  const l2 = getLuminance(bg);
  const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  
  return {
    passes: ratio >= 4.5, // WCAG AA standard for normal text
    ratio,
  };
};

// 11. Skip link component - implement in main layout
// export const SkipLink = () => (
//   <a href="#main-content" className="sr-only focus:not-sr-only">Skip to content</a>
// );

// 12. Add loading skeleton best practices
export const skeletonBestPractices = {
  // Use these skeleton variants
  variants: {
    text: 'rounded h-4',
    circular: 'rounded-full',
    rectangular: 'rounded-none',
    rounded: 'rounded-lg',
  },
  // Animation should respect reduced motion
  animation: 'animate-pulse',
  reducedMotionAnimation: 'none',
};

// 13. Error boundary for charts - implement in chart components
// export class ChartErrorBoundary extends React.Component {
//   state = { hasError: false };
//   static getDerivedStateFromError() { return { hasError: true }; }
//   render() {
//     if (this.state.hasError) {
//       return <div role="alert" className="p-4 bg-red-50 rounded-lg">Chart failed to load</div>;
//     }
//     return this.props.children;
//   }
// }

// 14. Confirmation modal for first trade - implement in trading pages
// export const FirstTradeConfirmation = ({ onConfirm, onCancel }: any) => (
//   <div role="dialog" aria-labelledby="modal-title" aria-modal="true">
//     <h2 id="modal-title" className="text-xl font-bold mb-4">Confirm Your First Trade</h2>
//     <div className="space-y-4">
//       <p className="text-gray-600">This will execute a real trade with actual funds.</p>
//       <div className="flex gap-4 mt-6">
//         <button onClick={onCancel} className="flex-1 px-4 py-2 border rounded-lg">Cancel</button>
//         <button onClick={onConfirm} className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg">I Understand</button>
//       </div>
//     </div>
//   </div>
// );

// 15. Dark mode toggle hook
export const useDarkMode = () => {
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    // Check localStorage first
    const saved = localStorage.getItem('theme');
    if (saved) {
      setIsDark(saved === 'dark');
      document.documentElement.classList.toggle('dark', saved === 'dark');
      return;
    }

    // Fall back to system preference
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    setIsDark(prefersDark);
    document.documentElement.classList.toggle('dark', prefersDark);
  }, []);

  const toggle = () => {
    setIsDark(prev => {
      const newValue = !prev;
      localStorage.setItem('theme', newValue ? 'dark' : 'light');
      document.documentElement.classList.toggle('dark', newValue);
      return newValue;
    });
  };

  return { isDark, toggle };
};

export {};
