// frontend/src/context/ThemeContext.tsx
import React, { createContext, useContext, useEffect, useState } from 'react';

export interface ThemeOption {
  id: string;
  name: string;
  description: string;
  /** [primary-500, accent-500] hex, used only for the swatch preview in the UI */
  swatch: [string, string];
}

export const THEMES: ThemeOption[] = [
  { id: 'monochrome', name: 'Monochrome', description: 'Black & white', swatch: ['#000000', '#ffffff'] },
  { id: 'nebula', name: 'Nebula', description: 'Cyan & violet', swatch: ['#06b6d4', '#a855f7'] },
  { id: 'synthwave', name: 'Synthwave', description: 'Magenta & indigo', swatch: ['#d946ef', '#6366f1'] },
  { id: 'matrix', name: 'Matrix', description: 'Neon green & cyan', swatch: ['#22c55e', '#06b6d4'] },
  { id: 'solar', name: 'Solar Flare', description: 'Amber & crimson', swatch: ['#f59e0b', '#f43f5e'] },
  { id: 'quantum', name: 'Quantum', description: 'Blue & cyan', swatch: ['#3b82f6', '#06b6d4'] },
];

const DEFAULT_THEME = 'monochrome';
const STORAGE_KEY = 'sms-color-theme';

interface ThemeContextType {
  theme: string;
  setTheme: (id: string) => void;
  themes: ThemeOption[];
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProvider = ({ children }: { children: React.ReactNode }) => {
  const [theme, setThemeState] = useState<string>(() => {
    if (typeof window === 'undefined') return DEFAULT_THEME;
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored && THEMES.some((t) => t.id === stored) ? stored : DEFAULT_THEME;
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    window.localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const setTheme = (id: string) => {
    if (THEMES.some((t) => t.id === id)) {
      setThemeState(id);
    }
  };

  return (
    <ThemeContext.Provider value={{ theme, setTheme, themes: THEMES }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useTheme must be used within ThemeProvider');
  return context;
};
