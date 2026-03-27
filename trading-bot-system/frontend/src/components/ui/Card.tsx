/**
 * Card Component
 * Reusable card with various styles and effects
 */
'use client';

import { motion } from 'framer-motion';
import { ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
  variant?: 'default' | 'elevated' | 'outlined' | 'glass';
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
  const baseStyles = 'rounded-xl transition-all duration-300';
  
  const variantStyles = {
    default: 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700',
    elevated: 'bg-white dark:bg-gray-800 shadow-lg border border-gray-100 dark:border-gray-700',
    outlined: 'bg-transparent border-2 border-gray-200 dark:border-gray-700',
    glass: 'bg-white/10 dark:bg-gray-800/50 backdrop-blur-lg border border-white/20 dark:border-gray-700/50',
  };

  const paddingStyles = {
    none: '',
    sm: 'p-3',
    md: 'p-6',
    lg: 'p-8',
  };

  const hoverStyles = hover
    ? 'hover:shadow-xl hover:-translate-y-1 cursor-pointer'
    : '';

  const gradientStyles = gradient
    ? 'bg-gradient-to-br from-purple-500/10 via-blue-500/10 to-pink-500/10 dark:from-purple-500/20 dark:via-blue-500/20 dark:to-pink-500/20'
    : '';

  return (
    <motion.div
      whileHover={hover ? { scale: 1.02 } : {}}
      whileTap={onClick ? { scale: 0.98 } : {}}
      onClick={onClick}
      className={`${baseStyles} ${variantStyles[variant]} ${paddingStyles[padding]} ${hoverStyles} ${gradientStyles} ${className}`}
    >
      {children}
    </motion.div>
  );
}
