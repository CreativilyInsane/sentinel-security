// frontend/src/components/ui/Spinner.tsx
import { ArrowPathIcon } from '@heroicons/react/24/solid';

export const Spinner = ({ className = 'w-5 h-5' }: { className?: string }) => {
  return (
    <ArrowPathIcon className={`animate-spin text-primary-500 ${className}`} />
  );
};