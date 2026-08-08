// frontend/src/pages/NotFound.tsx
import React from 'react';
import { Link } from 'react-router-dom';

export const NotFound: React.FC = () => {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
      <h1 className="text-7xl font-display font-bold text-gradient-cyber mb-4 drop-shadow-[0_0_25px_rgba(34,211,238,0.35)]">404</h1>
      <p className="text-xl text-dark-100 mb-6">Page Not Found</p>
      <Link to="/dashboard" className="px-5 py-2.5 bg-gradient-cyber text-white font-medium rounded-xl shadow-glow hover:shadow-glow-lg hover:brightness-110 transition-all">
        Go back to Dashboard
      </Link>
    </div>
  );
};