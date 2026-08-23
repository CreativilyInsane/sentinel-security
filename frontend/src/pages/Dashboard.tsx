// frontend/src/pages/Dashboard.tsx
import React from 'react';
import { Link } from 'react-router-dom';
import { useDashboardData } from '@/hooks/useDashboard';
import { useReconStats } from '@/hooks/useRecon';
import { StatCard } from '@/components/dashboard/StatCard';
import { RecentActivityTable } from '@/components/dashboard/RecentActivityTable';
import { Spinner } from '@/components/ui/Spinner';
import { Badge, scanStatusVariant } from '@/components/ui/Badge';
import {
  ServerStackIcon,
  ClockIcon,
  SignalIcon,
  CheckCircleIcon,
  EyeIcon,
} from '@heroicons/react/24/outline';
import { ROUTES } from '@/routes/paths';

export const Dashboard: React.FC = () => {
  const { data: dashboard, isLoading } = useDashboardData();
  const { data: stats } = useReconStats();

  if (isLoading || !dashboard) {
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
        <StatCard
          title="Total Scans"
          value={stats?.total_scans ?? 0}
          icon={<SignalIcon className="w-6 h-6" />}
          trend={stats && stats.running_scans > 0 ? `${stats.running_scans} active` : undefined}
        />
        <StatCard
          title="Completed Scans"
          value={stats?.completed_scans ?? 0}
          icon={<CheckCircleIcon className="w-6 h-6" />}
        />
        <StatCard
          title="Discovered Assets"
          value={stats?.total_assets ?? dashboard.stats.total_assets}
          icon={<ServerStackIcon className="w-6 h-6" />}
        />
        <StatCard
          title="Open Ports"
          value={stats?.open_ports ?? 0}
          icon={<ClockIcon className="w-6 h-6" />}
          trend={dashboard.stats.system_status === 'Operational' ? 'Operational' : undefined}
        />
      </div>

      {/* Recent Scans (recon) */}
      {stats && stats.recent_scans.length > 0 && (
        <div className="glass-panel border-glow-top rounded-xl overflow-hidden">
          <div className="p-5 border-b border-dark-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-primary-400 shadow-glow-sm" />
              <h3 className="text-base font-display font-semibold text-dark-50">Recent Scans</h3>
            </div>
            <Link to={ROUTES.PREVIOUS_SCANS} className="text-xs text-primary-300 hover:text-primary-200 transition-colors">
              View all →
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-dark-950/60 border-b border-dark-800">
                <tr>
                  <th className="px-5 py-2.5 text-xs font-semibold text-dark-400 uppercase tracking-wider">Scan</th>
                  <th className="px-5 py-2.5 text-xs font-semibold text-dark-400 uppercase tracking-wider">Target</th>
                  <th className="px-5 py-2.5 text-xs font-semibold text-dark-400 uppercase tracking-wider">Status</th>
                  <th className="px-5 py-2.5 text-xs font-semibold text-dark-400 uppercase tracking-wider">Progress</th>
                  <th className="px-5 py-2.5 text-xs font-semibold text-dark-400 uppercase tracking-wider text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-800/70">
                {stats.recent_scans.map(s => (
                  <tr key={s.id} className="hover:bg-primary-500/[0.04] transition-colors">
                    <td className="px-5 py-3 text-sm text-dark-400 font-mono">#{s.id}</td>
                    <td className="px-5 py-3 text-sm text-dark-100 font-mono">{s.target}</td>
                    <td className="px-5 py-3">
                      <Badge variant={scanStatusVariant(s.status)} noDot>{s.status}</Badge>
                    </td>
                    <td className="px-5 py-3 text-xs text-dark-400 font-mono">{s.progress}%</td>
                    <td className="px-5 py-3 text-right">
                      <Link to={ROUTES.SCAN_DETAILS_BY_ID(s.id)} className="inline-flex items-center gap-1 text-xs text-primary-300 hover:text-primary-200">
                        <EyeIcon className="w-3.5 h-3.5" /> View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Recent Assets (recon) */}
      {stats && stats.recent_assets.length > 0 && (
        <div className="glass-panel border-glow-top rounded-xl overflow-hidden">
          <div className="p-5 border-b border-dark-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-glow-sm" />
              <h3 className="text-base font-display font-semibold text-dark-50">Recent Assets</h3>
            </div>
            <Link to={ROUTES.ASSETS} className="text-xs text-primary-300 hover:text-primary-200 transition-colors">
              View all →
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-dark-950/60 border-b border-dark-800">
                <tr>
                  <th className="px-5 py-2.5 text-xs font-semibold text-dark-400 uppercase tracking-wider">Host</th>
                  <th className="px-5 py-2.5 text-xs font-semibold text-dark-400 uppercase tracking-wider">IP</th>
                  <th className="px-5 py-2.5 text-xs font-semibold text-dark-400 uppercase tracking-wider">Port</th>
                  <th className="px-5 py-2.5 text-xs font-semibold text-dark-400 uppercase tracking-wider">Service</th>
                  <th className="px-5 py-2.5 text-xs font-semibold text-dark-400 uppercase tracking-wider">Last Seen</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-800/70">
                {stats.recent_assets.map(a => (
                  <tr key={a.id} className="hover:bg-primary-500/[0.04] transition-colors">
                    <td className="px-5 py-3 text-sm text-dark-100 font-mono">{a.host}</td>
                    <td className="px-5 py-3 text-sm text-dark-300 font-mono">{a.ip_address || '—'}</td>
                    <td className="px-5 py-3 text-sm text-dark-300 font-mono">{a.port ?? '—'}</td>
                    <td className="px-5 py-3">
                      {a.service ? <Badge variant="info" noDot>{a.service}</Badge> : <span className="text-dark-500 text-sm">—</span>}
                    </td>
                    <td className="px-5 py-3 text-xs text-dark-400">
                      {a.last_seen ? new Date(a.last_seen).toLocaleString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Recent Activity (audit log driven) */}
      <RecentActivityTable activities={dashboard.recent_activity} />

      {/* Quick action */}
      <div className="flex justify-center pt-2">
        <Link to={ROUTES.NETWORK_SCAN}>
          <button className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-cyber text-white font-semibold shadow-glow hover:shadow-glow-lg hover:brightness-110 transition-all">
            <SignalIcon className="w-5 h-5" />
            Start New Reconnaissance
          </button>
        </Link>
      </div>
    </div>
  );
};
