// frontend/src/pages/PreviousScans.tsx
import React, { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  EyeIcon,
  TrashIcon,
  DocumentChartBarIcon,
  MagnifyingGlassIcon,
  ClockIcon,
  ArrowRightIcon,
} from '@heroicons/react/24/outline';
import { Button } from '@/components/ui/Button';
import { Badge, scanStatusVariant } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { Spinner } from '@/components/ui/Spinner';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { useScans, useDeleteScan } from '@/hooks/useRecon';
import { useToast } from '@/context/ToastContext';
import { ROUTES } from '@/routes/paths';
import type { ScanStatus, ScanSummary } from '@/types/recon.types';

const STATUS_OPTIONS: Array<{ value: '' | ScanStatus; label: string }> = [
  { value: '', label: 'All Statuses' },
  { value: 'QUEUED', label: 'Queued' },
  { value: 'RUNNING', label: 'Running' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'FAILED', label: 'Failed' },
  { value: 'CANCELLED', label: 'Cancelled' },
];

const MODULE_LABELS: Record<string, string> = {
  host_discovery: 'Hosts',
  port_scan: 'Ports',
  service_detection: 'Services',
  whois: 'WHOIS',
  dns: 'DNS',
  ssl: 'SSL',
  http: 'HTTP',
  screenshot: 'Screenshot',
};

export const PreviousScans: React.FC = () => {
  const { showToast } = useToast();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'' | ScanStatus>('');
  const [dateFilter, setDateFilter] = useState(''); // YYYY-MM-DD
  const [deleteTarget, setDeleteTarget] = useState<ScanSummary | null>(null);

  const deleteScan = useDeleteScan();

  // Debounce search by reading state into the query key directly
  const { data, isLoading, isFetching } = useScans({
    skip: 0,
    limit: 100,
    status: statusFilter || undefined,
    target: search || undefined,
  });

  const filtered = useMemo(() => {
    if (!data) return [];
    if (!dateFilter) return data;
    return data.filter(s => (s.created_at || '').startsWith(dateFilter));
  }, [data, dateFilter]);

  const onDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await deleteScan.mutateAsync(deleteTarget.id);
      showToast(`Scan #${deleteTarget.id} deleted.`, 'success');
    } catch (err: any) {
      showToast(err?.response?.data?.message || 'Failed to delete scan.', 'error');
    } finally {
      setDeleteTarget(null);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-display font-bold text-dark-50">Previous Scans</h1>
        <p className="text-dark-400 mt-1">
          Review historical scan data, drill into results, and download reports.
        </p>
      </div>

      {/* Filters */}
      <div className="glass-panel rounded-xl p-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Input
            id="search"
            placeholder="Search by target..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            icon={<MagnifyingGlassIcon className="w-4 h-4" />}
          />
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value as any)}
            className="bg-dark-900/70 border border-dark-700 rounded-xl py-2.5 px-4 text-dark-100 focus:outline-none focus:ring-2 focus:ring-primary-500/60"
          >
            {STATUS_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value} className="bg-dark-900">
                {opt.label}
              </option>
            ))}
          </select>
          <Input
            id="date"
            type="date"
            value={dateFilter}
            onChange={e => setDateFilter(e.target.value)}
          />
        </div>
      </div>

      {/* Summary tiles */}
      {!isLoading && filtered.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <SummaryTile
            label="Total"
            value={String(filtered.length)}
          />
          <SummaryTile
            label="Completed"
            value={String(filtered.filter(s => s.status === 'COMPLETED').length)}
            variant="success"
          />
          <SummaryTile
            label="Running / Queued"
            value={String(
              filtered.filter(s => s.status === 'RUNNING' || s.status === 'QUEUED')
                .length,
            )}
            variant="info"
          />
          <SummaryTile
            label="Failed / Cancelled"
            value={String(
              filtered.filter(s => s.status === 'FAILED' || s.status === 'CANCELLED')
                .length,
            )}
            variant="danger"
          />
        </div>
      )}

      {/* Table */}
      <div className="glass-panel border-glow-top rounded-xl overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Spinner className="w-7 h-7" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-dark-400">
            <ClockIcon className="w-10 h-10 mb-3 text-dark-600" />
            <p className="text-sm">No scans match your filters.</p>
            <Link to={ROUTES.NETWORK_SCAN} className="mt-3">
              <Button variant="secondary" size="sm">
                Start a new scan
              </Button>
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-dark-950/60 border-b border-dark-800">
                <tr>
                  <Th>ID</Th>
                  <Th>Target</Th>
                  <Th>Status</Th>
                  <Th>Source</Th>
                  <Th>Modules</Th>
                  <Th>Started</Th>
                  <Th>Completed</Th>
                  <Th>Duration</Th>
                  <Th className="text-right">Actions</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-800/70">
                {filtered.map(s => {
                  const duration = computeDuration(s.started_at, s.completed_at);
                  const ownershipVariantLocal = (t?: string): 'info' | 'primary' | 'neutral' => {
                    if (t === 'CLIENT') return 'info';
                    if (t === 'ASSIGNED_TARGET') return 'primary';
                    return 'neutral';
                  };
                  const ownershipLabel = (t?: string): string => {
                    if (t === 'CLIENT') return 'Client';
                    if (t === 'ASSIGNED_TARGET') return 'Assigned';
                    return 'My Scan';
                  };
                  return (
                    <tr
                      key={s.id}
                      className="hover:bg-primary-500/[0.04] transition-colors"
                    >
                      <td className="px-4 py-3 text-sm text-dark-400 font-mono">
                        #{s.id}
                      </td>
                      <td className="px-4 py-3">
                        <Link
                          to={ROUTES.SCAN_DETAILS_BY_ID(s.id)}
                          className="text-sm font-medium text-dark-100 font-mono hover:text-primary-300 transition-colors"
                        >
                          {s.target}
                        </Link>
                        <div className="text-xs text-dark-500">{s.target_type}</div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={scanStatusVariant(s.status)} noDot>
                          {s.status}
                        </Badge>
                        <div className="text-[10px] text-dark-500 mt-0.5">
                          {s.progress}%
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={ownershipVariantLocal(s.ownership_type)} noDot>
                          {ownershipLabel(s.ownership_type)}
                        </Badge>
                        {s.client_name && (
                          <div className="text-[10px] text-dark-500 mt-0.5">{s.client_name}</div>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1 max-w-xs">
                          {s.modules.slice(0, 4).map(m => (
                            <span
                              key={m}
                              className="inline-flex items-center px-1.5 py-0.5 text-[10px] rounded border border-dark-700 bg-dark-900/60 text-dark-300"
                            >
                              {MODULE_LABELS[m] || m}
                            </span>
                          ))}
                          {s.modules.length > 4 && (
                            <span className="text-[10px] text-dark-500 self-center">
                              +{s.modules.length - 4}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs text-dark-300">
                        {s.started_at ? new Date(s.started_at).toLocaleString() : '—'}
                      </td>
                      <td className="px-4 py-3 text-xs text-dark-300">
                        {s.completed_at ? new Date(s.completed_at).toLocaleString() : '—'}
                      </td>
                      <td className="px-4 py-3 text-xs text-dark-300 font-mono">
                        {duration}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1.5">
                          <Link
                            to={ROUTES.SCAN_DETAILS_BY_ID(s.id)}
                            title="View scan details"
                          >
                            <Button variant="ghost" size="sm">
                              <EyeIcon className="w-4 h-4" />
                              <span className="ml-1 hidden sm:inline">View</span>
                              <ArrowRightIcon className="w-3 h-3 ml-1" />
                            </Button>
                          </Link>
                          {s.status === 'COMPLETED' && (
                            <Link to={ROUTES.REPORTS} title="Reports">
                              <Button variant="ghost" size="sm">
                                <DocumentChartBarIcon className="w-4 h-4" />
                              </Button>
                            </Link>
                          )}
                          <button
                            onClick={() => setDeleteTarget(s)}
                            className="p-1.5 text-dark-400 hover:text-red-400 hover:bg-dark-800 rounded-lg transition-all"
                            title="Delete"
                          >
                            <TrashIcon className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {isFetching && !isLoading && (
          <div className="text-center py-2 text-xs text-dark-500">Syncing…</div>
        )}
      </div>

      <ConfirmDialog
        isOpen={!!deleteTarget}
        title="Delete Scan"
        message={`This will permanently delete scan #${deleteTarget?.id} on ${deleteTarget?.target} and all associated results, assets, and reports.`}
        confirmLabel="Delete"
        cancelLabel="Cancel"
        isLoading={deleteScan.isPending}
        onConfirm={onDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
};

const Th: React.FC<{ children?: React.ReactNode; className?: string }> = ({
  children,
  className = '',
}) => (
  <th
    className={`px-4 py-3 text-xs font-semibold text-dark-400 uppercase tracking-wider ${className}`}
  >
    {children}
  </th>
);

const SummaryTile: React.FC<{
  label: string;
  value: string;
  variant?: 'success' | 'info' | 'danger' | 'neutral';
}> = ({ label, value, variant = 'neutral' }) => {
  const colorMap: Record<string, string> = {
    success: 'border-green-500/30 bg-green-500/5 text-green-300',
    info: 'border-cyan-500/30 bg-cyan-500/5 text-cyan-300',
    danger: 'border-red-500/30 bg-red-500/5 text-red-300',
    neutral: 'border-dark-700 bg-dark-900/40 text-dark-100',
  };
  return (
    <div className={`rounded-lg border p-3 ${colorMap[variant]}`}>
      <div className="text-2xl font-data font-bold">{value}</div>
      <div className="text-xs text-dark-400 mt-1">{label}</div>
    </div>
  );
};

const computeDuration = (start: string | null, end: string | null): string => {
  if (!start) return '—';
  const s = new Date(start).getTime();
  const e = end ? new Date(end).getTime() : Date.now();
  const ms = Math.max(0, e - s);
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  return `${m}m ${seconds % 60}s`;
};
