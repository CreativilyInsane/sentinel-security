// frontend/src/pages/Placeholders.tsx
import { WrenchScrewdriverIcon } from '@heroicons/react/24/outline';

interface PlaceholderProps {
  title: string;
  description?: string;
}

export const Placeholder = ({ title, description }: PlaceholderProps) => {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
      <div className="p-4 glass-panel rounded-2xl mb-4 shadow-glow-sm animate-float">
        <WrenchScrewdriverIcon className="w-10 h-10 text-primary-400" />
      </div>
      <h1 className="text-2xl font-display font-bold text-dark-50 mb-2">{title}</h1>
      <p className="text-dark-400 max-w-md">
        {description || `The ${title} module is under construction. Check back soon for updates.`}
      </p>
    </div>
  );
};