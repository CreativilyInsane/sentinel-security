// frontend/src/components/ui/ConfirmDialog.tsx
import React, { useEffect } from 'react';
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline';
import { Button } from './Button';

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  isLoading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  title,
  message,
  confirmLabel = 'Delete',
  cancelLabel = 'Cancel',
  isLoading = false,
  onConfirm,
  onCancel,
}) => {
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isLoading) onCancel();
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, isLoading, onCancel]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-dark-950/85 backdrop-blur-sm transition-opacity"
        onClick={() => !isLoading && onCancel()}
      />

      {/* Dialog */}
      <div className="relative glass-panel rounded-2xl shadow-2xl shadow-black/50 w-full max-w-sm p-6 animate-fade-in-up border border-red-500/20">
        <div className="flex items-start gap-4">
          <div className="shrink-0 w-11 h-11 rounded-xl bg-red-500/10 border border-red-500/30 flex items-center justify-center shadow-[0_0_15px_rgba(244,63,94,0.25)]">
            <ExclamationTriangleIcon className="w-6 h-6 text-red-400" />
          </div>
          <div className="flex-1 pt-1">
            <h3 className="text-lg font-display font-semibold text-dark-50">{title}</h3>
            <p className="text-sm text-dark-400 mt-1.5 leading-relaxed">{message}</p>
          </div>
        </div>

        <div className="flex gap-3 mt-6">
          <Button variant="secondary" fullWidth onClick={onCancel} disabled={isLoading}>
            {cancelLabel}
          </Button>
          <Button variant="danger" fullWidth onClick={onConfirm} isLoading={isLoading}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
};
