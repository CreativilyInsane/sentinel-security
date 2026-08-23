// frontend/src/components/ui/ProgressBar.tsx
import React from 'react';

interface ProgressBarProps {
  value: number; // 0..100
  className?: string;
  /** When true, render an animated shimmer to indicate active progress */
  animated?: boolean;
  /** Optional label shown above the bar */
  label?: string;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  value,
  className = '',
  animated = false,
  label,
}) => {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div className={`w-full ${className}`}>
      {label && (
        <div className="flex justify-between items-center mb-1.5">
          <span className="text-xs font-medium text-dark-300">{label}</span>
          <span className="text-xs font-mono text-primary-300">{clamped}%</span>
        </div>
      )}
      <div className="w-full h-2 rounded-full bg-dark-800 border border-dark-700 overflow-hidden">
        <div
          className={`h-full rounded-full bg-gradient-cyber transition-all duration-500 ${
            animated ? 'animate-shimmer' : ''
          }`}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
};
