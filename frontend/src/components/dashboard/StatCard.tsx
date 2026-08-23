// frontend/src/components/dashboard/StatCard.tsx
import React from 'react';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  trend?: string;
}

export const StatCard: React.FC<StatCardProps> = ({ title, value, icon, trend }) => {
  return (
    <div className="group glass-panel rounded-xl p-5 transition-all duration-300 hover:border-primary-600/40 hover:shadow-glow hover:-translate-y-0.5">
      <div className="flex items-start justify-between mb-4">
        <div className="p-2.5 bg-dark-800/80 rounded-lg text-primary-400 border border-dark-700 group-hover:border-primary-500/40 group-hover:shadow-glow-sm transition-all duration-300">
          {icon}
        </div>
        {trend && (
          <span className="text-xs font-medium text-primary-300 bg-primary-500/10 border border-primary-600/30 px-2 py-1 rounded-full">
            {trend}
          </span>
        )}
      </div>
      <h3 className="text-2xl font-data font-bold text-dark-50 mb-1">{value}</h3>
      <p className="text-sm text-dark-400">{title}</p>
    </div>
  );
};