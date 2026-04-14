/**
 * Compact Search Input Component
 * Shopify-style search with icon
 */
import { useState, useEffect } from 'react';
import { Search, X } from 'lucide-react';

interface SearchProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  size?: 'sm' | 'md';
  onClear?: () => void;
}

export default function SearchInput({
  value,
  onChange,
  placeholder = 'Search...',
  size = 'sm',
  onClear,
}: SearchProps) {
  const [isFocused, setIsFocused] = useState(false);

  return (
    <div
      className={`
        relative flex items-center
        bg-white dark:bg-gray-700
        border rounded-md
        transition-all
        ${size === 'sm' ? 'h-8' : 'h-10'}
        ${isFocused
          ? 'border-purple-500 ring-2 ring-purple-200 dark:ring-purple-900'
          : 'border-gray-300 dark:border-gray-600'
        }
      `}
    >
      <Search className={`ml-2 text-gray-400 ${size === 'sm' ? 'w-3.5 h-3.5' : 'w-4 h-4'}`} />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        placeholder={placeholder}
        className={`
          flex-1 bg-transparent border-none outline-none px-2
          text-gray-900 dark:text-white
          placeholder-gray-400
          ${size === 'sm' ? 'text-xs' : 'text-sm'}
        `}
      />
      {value && (
        <button
          onClick={() => {
            onChange('');
            onClear?.();
          }}
          className="mr-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
        >
          <X className={size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5'} />
        </button>
      )}
    </div>
  );
}
