// frontend/src/components/protected/AdminRoute.tsx
import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Spinner } from '@/components/ui/Spinner';

export const AdminRoute: React.FC = () => {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-dark-950">
        <Spinner className="w-8 h-8" />
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;

  return user.role.name === 'Administrator' ? <Outlet /> : <Navigate to="/dashboard" replace />;
};