/**
 * Card Component
 * Reusable card with various styles and effects
 */
'use client';

import { ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
  variant?: 'default' | 'elevated' | 'outlined';
  hover?: boolean;
  onClick?: () => void;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  gradient?: boolean;
}

export default function Card({
  children,
  className = '',
  variant = 'default',
  hover = false,
  onClick,
  padding = 'md',
  gradient = false,
}: CardProps) {
  const baseStyles = 'rounded-lg transition-colors duration-200';
  
  const variantStyles = {
    default: 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700',
    elevated: 'bg-white dark:bg-gray-800 border-2 border-gray-200 dark:border-gray-700',
    outlined: 'bg-transparent border-2 border-gray-200 dark:border-gray-700',
  };

  const paddingStyles = {
    none: '',
    sm: 'p-3',
    md: 'p-6',
    lg: 'p-8',
  };

  const hoverStyles = hover
    ? 'hover:border-gray-300 dark:hover:border-gray-600 cursor-pointer'
    : '';

  const gradientStyles = gradient
    ? 'bg-gradient-to-br from-purple-500/10 via-blue-500/10 to-pink-500/10 dark:from-purple-500/20 dark:via-blue-500/20 dark:to-pink-500/20'
    : '';

  return (
    <div
      onClick={onClick}
      className={`${baseStyles} ${variantStyles[variant]} ${paddingStyles[padding]} ${hoverStyles} ${gradientStyles} ${className}`}
    >
      {children}
    </div>
  );
}
