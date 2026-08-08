// frontend/src/components/layout/DashboardLayout.tsx
import React from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Navbar } from './Navbar';

export const DashboardLayout: React.FC = () => {
  return (
    <div className="min-h-screen bg-dark-950 relative">
      <div className="pointer-events-none fixed top-0 right-0 w-[40rem] h-[40rem] bg-primary-900/10 rounded-full blur-3xl -z-10" />
      <div className="pointer-events-none fixed bottom-0 left-1/3 w-[30rem] h-[30rem] bg-accent-900/10 rounded-full blur-3xl -z-10" />
      <Sidebar />
      <div className="sm:ml-64">
        <Navbar />
        <main className="p-4 sm:p-6 lg:p-8 animate-fade-in-up">
          <Outlet />
        </main>
      </div>
    </div>
  );
};