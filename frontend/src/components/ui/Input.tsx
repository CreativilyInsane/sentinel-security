// frontend/src/components/ui/Input.tsx
import React, { forwardRef } from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  icon?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, icon, className = '', id, ...props }, ref) => {
    return (
      <div className="w-full">
        {label && (
          <label htmlFor={id} className="block text-sm font-medium text-dark-300 mb-1.5 tracking-wide">
            {label}
          </label>
        )}
        <div className="relative">
          {icon && (
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-dark-400 peer-focus:text-primary-400">
              {icon}
            </div>
          )}
          <input
            ref={ref}
            id={id}
            className={`
              peer w-full bg-dark-900/70 border rounded-xl py-2.5 px-4 text-dark-100 placeholder-dark-500
              focus:outline-none focus:ring-2 focus:ring-primary-500/60 focus:border-primary-500/60 focus:shadow-glow-sm
              hover:border-dark-600 transition-all duration-200
              ${icon ? 'pl-10' : ''}
              ${error ? 'border-red-500' : 'border-dark-700'}
              ${className}
            `}
            {...props}
          />
        </div>
        {error && <p className="mt-1.5 text-xs text-red-400">{error}</p>}
      </div>
    );
  }
);

Input.displayName = 'Input';