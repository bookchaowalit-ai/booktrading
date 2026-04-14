/**
 * Compact Toggle/Switch Component
 * Shopify-style small toggle
 */
interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  size?: 'sm' | 'md';
}

export default function Toggle({ checked, onChange, disabled = false, size = 'sm' }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`
        relative inline-flex items-center rounded-full transition-colors
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        ${size === 'sm' ? 'h-4 w-7' : 'h-5 w-9'}
        ${checked ? 'bg-purple-600' : 'bg-gray-300 dark:bg-gray-600'}
      `}
    >
      <span
        className={`
          inline-block transform rounded-full bg-white transition-transform
          ${size === 'sm' ? 'h-3 w-3' : 'h-4 w-4'}
          ${checked ? (size === 'sm' ? 'translate-x-3.5' : 'translate-x-4.5') : 'translate-x-0.5'}
        `}
      />
    </button>
  );
}
