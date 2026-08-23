// frontend/src/components/ui/Button.tsx
import React from 'react';
import { Spinner } from './Spinner';

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost';
type Size = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  isLoading?: boolean;
  fullWidth?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  fullWidth = false,
  className = '',
  disabled,
  ...props
}) => {
  const baseClasses = 'inline-flex items-center justify-center font-semibold tracking-tight rounded-xl transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-dark-950 disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98]';

  const variantClasses = {
    primary: 'bg-gradient-cyber text-white hover:brightness-110 focus:ring-primary-500 shadow-glow hover:shadow-glow-lg',
    secondary: 'bg-dark-800/80 text-dark-100 hover:bg-dark-700 border border-dark-600 hover:border-primary-500/50 focus:ring-dark-500',
    danger: 'bg-gradient-to-r from-red-600 to-rose-600 text-white hover:brightness-110 focus:ring-red-500 shadow-[0_0_20px_rgba(244,63,94,0.3)]',
    ghost: 'text-dark-300 hover:bg-dark-800 hover:text-primary-300',
  };

  const sizeClasses = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-5 py-2.5 text-sm',
    lg: 'px-6 py-3 text-base',
  };

  return (
    <button
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${fullWidth ? 'w-full' : ''} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading && <Spinner className="w-4 h-4 mr-2" />}
      {children}
    </button>
  );
};