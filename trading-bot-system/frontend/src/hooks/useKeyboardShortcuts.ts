/**
 * Keyboard Shortcuts Hook
 * Global keyboard shortcut management
 */
import { useEffect } from 'react';

interface Shortcut {
  key: string;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  action: () => void;
}

export function useKeyboardShortcuts(shortcuts: Shortcut[]) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const { key, ctrlKey, shiftKey, altKey } = event;

      for (const shortcut of shortcuts) {
        const matches =
          key.toLowerCase() === shortcut.key.toLowerCase() &&
          (shortcut.ctrl === undefined || ctrlKey === shortcut.ctrl) &&
          (shortcut.shift === undefined || shiftKey === shortcut.shift) &&
          (shortcut.alt === undefined || altKey === shortcut.alt);

        if (matches) {
          event.preventDefault();
          shortcut.action();
          break;
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [shortcuts]);
}

// Common shortcuts
export const COMMON_SHORTCUTS = {
  SAVE: { key: 's', ctrl: true },
  SEARCH: { key: 'k', ctrl: true },
  NEW: { key: 'n', ctrl: true },
  REFRESH: { key: 'r', ctrl: true },
  HELP: { key: '?', shift: false },
  ESCAPE: { key: 'escape' },
};
