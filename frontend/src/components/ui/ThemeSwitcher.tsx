// frontend/src/components/ui/ThemeSwitcher.tsx
import React, { useEffect, useRef, useState } from 'react';
import { SwatchIcon } from '@heroicons/react/24/outline';
import { useTheme } from '@/context/ThemeContext';

export const ThemeSwitcher: React.FC = () => {
  const { theme, setTheme, themes } = useTheme();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, []);

  return (
    <div ref={containerRef} className="fixed bottom-5 right-5 z-50">
      {open && (
        <div className="absolute bottom-16 right-0 w-64 glass-panel border-glow-top rounded-2xl shadow-2xl shadow-black/50 p-3 animate-fade-in-up">
          <p className="text-xs font-semibold text-dark-400 uppercase tracking-wider px-2 pb-2">
            Color Scheme
          </p>
          <div className="space-y-1">
            {themes.map((option) => {
              const isActive = theme === option.id;
              return (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => setTheme(option.id)}
                  className={`w-full flex items-center gap-3 px-2.5 py-2 rounded-xl text-sm text-left transition-all duration-150 border ${
                    isActive
                      ? 'bg-primary-500/10 border-primary-500/30 text-primary-200'
                      : 'border-transparent text-dark-300 hover:bg-dark-800 hover:border-dark-700'
                  }`}
                >
                  <span className="flex -space-x-1.5 shrink-0">
                    <span
                      className="w-4 h-4 rounded-full border border-dark-950"
                      style={{ backgroundColor: option.swatch[0] }}
                    />
                    <span
                      className="w-4 h-4 rounded-full border border-dark-950"
                      style={{ backgroundColor: option.swatch[1] }}
                    />
                  </span>
                  <span className="flex flex-col leading-tight">
                    <span className="font-medium">{option.name}</span>
                    <span className="text-xs text-dark-500">{option.description}</span>
                  </span>
                  {isActive && (
                    <span className="ml-auto w-1.5 h-1.5 rounded-full bg-primary-400 shadow-glow-sm shrink-0" />
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-12 h-12 rounded-full glass-panel border-glow-top flex items-center justify-center text-primary-400 shadow-glow hover:shadow-glow-lg hover:scale-105 active:scale-95 transition-all duration-200"
        aria-label="Change color scheme"
        title="Change color scheme"
      >
        <SwatchIcon className="w-5 h-5" />
      </button>
    </div>
  );
};
