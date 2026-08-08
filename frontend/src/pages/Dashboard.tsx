// frontend/src/pages/Dashboard.tsx
import React from 'react';
import { useDashboardData } from '@/hooks/useDashboard';
import { StatCard } from '@/components/dashboard/StatCard';
import { RecentActivityTable } from '@/components/dashboard/RecentActivityTable';
import { Spinner } from '@/components/ui/Spinner';
import { ServerStackIcon, ClockIcon, DocumentChartBarIcon, SignalIcon } from '@heroicons/react/24/outline';

export const Dashboard: React.FC = () => {
  const { data, isLoading } = useDashboardData();

  if (isLoading || !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner className="w-8 h-8" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-display font-bold text-dark-50">Overview</h1>
        <p className="text-dark-400 mt-1">Welcome to your security operations center.</p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Total Assets" value={data.stats.total_assets} icon={<ServerStackIcon className="w-6 h-6" />} trend="Monitored" />
        <StatCard title="Last Scan" value={data.stats.last_scan} icon={<ClockIcon className="w-6 h-6" />} />
        <StatCard title="Reports Generated" value={data.stats.reports_generated} icon={<DocumentChartBarIcon className="w-6 h-6" />} />
        <StatCard title="System Status" value={data.stats.system_status} icon={<SignalIcon className="w-6 h-6" />} trend="Active" />
      </div>

      {/* Recent Activity */}
      <RecentActivityTable activities={data.recent_activity} />
    </div>
  );
};