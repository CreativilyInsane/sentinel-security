// frontend/src/components/dashboard/RecentActivityTable.tsx
import React from 'react';
import type { ActivityItem } from '@/types/dashboard.types';

interface Props {
  activities: ActivityItem[];
}

export const RecentActivityTable: React.FC<Props> = ({ activities }) => {
  return (
    <div className="glass-panel border-glow-top rounded-xl overflow-hidden">
      <div className="p-5 border-b border-dark-800 flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-primary-400 shadow-glow-sm" />
        <h3 className="text-base font-display font-semibold text-dark-50">Recent Activity</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead className="bg-dark-950/60 border-b border-dark-800">
            <tr>
              <th className="px-5 py-3 text-xs font-semibold text-dark-400 uppercase tracking-wider">Type</th>
              <th className="px-5 py-3 text-xs font-semibold text-dark-400 uppercase tracking-wider">Description</th>
              <th className="px-5 py-3 text-xs font-semibold text-dark-400 uppercase tracking-wider hidden sm:table-cell">Timestamp</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-dark-800/70">
            {activities.map((activity) => (
              <tr key={activity.id} className="hover:bg-primary-500/[0.04] transition-colors">
                <td className="px-5 py-4">
                  <span className="px-2.5 py-1 text-xs font-medium bg-primary-900/30 text-primary-300 rounded-full border border-primary-700/40">
                    {activity.type}
                  </span>
                </td>
                <td className="px-5 py-4 text-sm text-dark-200">{activity.description}</td>
                <td className="px-5 py-4 text-sm text-dark-400 font-mono hidden sm:table-cell">
                  {new Date(activity.timestamp).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};