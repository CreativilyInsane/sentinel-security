// frontend/src/components/layout/Navbar.tsx
import React from 'react';
import { useAuth } from '@/context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { UserCircleIcon } from '@heroicons/react/24/solid';

export const Navbar: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  return (
    <header className="sticky top-0 z-30 h-16 bg-dark-950/70 backdrop-blur-xl border-b border-dark-800">
      <div className="h-full flex items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)] animate-pulse-glow" />
          <h2 className="text-lg font-display font-semibold text-dark-100">
            Security Dashboard
          </h2>
        </div>
        
        <div className="flex items-center space-x-4">
          <button 
            // onClick={() => navigate('/profile')}
            onClick={() => navigate('/settings')}
            className="flex items-center space-x-2.5 group"
          >
            <div className="hidden sm:block text-right">
              <p className="text-sm font-medium text-dark-100 group-hover:text-primary-400 transition-colors">{user?.username}</p>
              <p className="text-xs text-dark-500 font-mono">{user?.role.name}</p>
            </div>
            <div className="w-9 h-9 rounded-full bg-dark-800 border border-dark-700 flex items-center justify-center group-hover:border-primary-500 group-hover:shadow-glow-sm transition-all">
              <UserCircleIcon className="w-6 h-6 text-dark-400 group-hover:text-primary-400 transition-colors" />
            </div>
          </button>
        </div>
      </div>
    </header>
  );
};