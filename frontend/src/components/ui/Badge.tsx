// frontend/src/components/ui/Badge.tsx
import React from 'react';

type BadgeVariant =
  | 'primary'
  | 'success'
  | 'danger'
  | 'warning'
  | 'neutral'
  | 'info';

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  /** Hide the leading dot — useful when many badges sit in a tight table row */
  noDot?: boolean;
}

export const Badge: React.FC<BadgeProps> = ({ variant = 'neutral', noDot = false, children }) => {
  const variants = {
    primary: 'bg-primary-900/30 text-primary-300 border-primary-600/40 shadow-[0_0_10px_rgba(34,211,238,0.15)]',
    success: 'bg-emerald-900/30 text-emerald-300 border-emerald-600/40 shadow-[0_0_10px_rgba(16,185,129,0.15)]',
    danger: 'bg-red-900/30 text-red-300 border-red-600/40 shadow-[0_0_10px_rgba(244,63,94,0.15)]',
    warning: 'bg-amber-900/30 text-amber-300 border-amber-600/40 shadow-[0_0_10px_rgba(245,158,11,0.15)]',
    info: 'bg-sky-900/30 text-sky-300 border-sky-600/40 shadow-[0_0_10px_rgba(56,189,248,0.15)]',
    neutral: 'bg-dark-800/80 text-dark-300 border-dark-600',
  };

  const dotColor = {
    primary: 'bg-primary-400',
    success: 'bg-emerald-400',
    danger: 'bg-red-400',
    warning: 'bg-amber-400',
    info: 'bg-sky-400',
    neutral: 'bg-dark-400',
  };

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border backdrop-blur-sm ${variants[variant]}`}>
      {!noDot && <span className={`w-1.5 h-1.5 rounded-full ${dotColor[variant]}`} />}
      {children}
    </span>
  );
};

// Helper: map a recon scan status to a Badge variant
export const scanStatusVariant = (
  status: string
): BadgeVariant => {
  switch (status) {
    case 'COMPLETED':
      return 'success';
    case 'RUNNING':
      return 'primary';
    case 'QUEUED':
      return 'info';
    case 'FAILED':
      return 'danger';
    case 'CANCELLED':
      return 'warning';
    default:
      return 'neutral';
  }
};

// Helper: map a security-header severity to a Badge variant
export const severityVariant = (
  severity: string
): BadgeVariant => {
  switch (severity.toLowerCase()) {
    case 'good':
      return 'success';
    case 'info':
      return 'info';
    case 'low':
      return 'primary';
    case 'medium':
      return 'warning';
    case 'high':
      return 'danger';
    default:
      return 'neutral';
  }
};