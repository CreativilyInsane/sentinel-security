// frontend/src/pages/Reports.tsx
import React, { useState, useMemo, useCallback } from 'react';
import {
  MagnifyingGlassIcon,
  DocumentChartBarIcon,
  DocumentArrowDownIcon,
  EyeIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Spinner } from '@/components/ui/Spinner';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Link } from 'react-router-dom';
import { useScans, useDeleteScan } from '@/hooks/useRecon';
import { useMyClients } from '@/hooks/useClients';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { apiClient } from '@/api/client';
import { ROUTES } from '@/routes/paths';
import { cn } from '@/utils/cn';
import type { ScanSummary } from '@/types/recon.types';

const ownershipLabel = (t?: string): string => {
  switch (t) {
    case 'CLIENT': return 'Client';
    case 'ASSIGNED_TARGET': return 'Assigned Target';
    default: return 'My Scan';
  }
};

const ownershipVariant = (t?: string): 'info' | 'primary' | 'neutral' => {
  switch (t) {
    case 'CLIENT': return 'info';
    case 'ASSIGNED_TARGET': return 'primary';
    default: return 'neutral';
  }
};

export const Reports: React.FC = () => {
  const { showToast } = useToast();
  const { user } = useAuth();
  const isAdmin = user?.role.name === 'Administrator';
  const [search, setSearch] = useState('');
  const [busyId, setBusyId] = useState<number | null>(null);
  const [deleteScan, setDeleteScan] = useState<ScanSummary | null>(null);

  const deleteScanMut = useDeleteScan();
  const { data, isLoading } = useScans({ limit: 200 });
  const myClientsQ = useMyClients();

  // Only completed scans can have reports
  const completed = useMemo(
    () => (data || []).filter(s => s.status === 'COMPLETED'),
    [data],
  );

  // Group by ownership
  const grouped = useMemo(() => {
    const clientReports: ScanSummary[] = [];
    const assignedReports: ScanSummary[] = [];
    const myReports: ScanSummary[] = [];
    for (const s of completed) {
      if (s.ownership_type === 'CLIENT') clientReports.push(s);
      else if (s.ownership_type === 'ASSIGNED_TARGET') assignedReports.push(s);
      else myReports.push(s);
    }
    return { clientReports, assignedReports, myReports };
  }, [completed]);

  const filterFn = useCallback((list: ScanSummary[]) => {
    if (!search.trim()) return list;
    const q = search.toLowerCase();
    return list.filter(s => s.target.toLowerCase().includes(q) || String(s.id).includes(q));
  }, [search]);

  const filteredClient = filterFn(grouped.clientReports);
  const filteredAssigned = filterFn(grouped.assignedReports);
  const filteredMy = filterFn(grouped.myReports);

  // ---- Authenticated HTML view (opens in new tab via blob URL) ----
  const handleViewHtml = useCallback(async (scanId: number) => {
    setBusyId(scanId);
    try {
      const res = await apiClient.get(`/recon/scans/${scanId}/report/html`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'text/html' }));
      window.open(url, '_blank');
      setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
    } catch (err: any) {
      showToast(err?.response?.data?.message || 'Failed to load HTML report.', 'error');
    } finally {
      setBusyId(null);
    }
  }, [showToast]);

  const handleDownloadHtml = useCallback(async (scanId: number) => {
    setBusyId(scanId);
    try {
      const res = await apiClient.get(`/recon/scans/${scanId}/report/html`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'text/html' }));
      const a = document.createElement('a');
      a.href = url; a.download = `basir-recon-scan-${scanId}.html`;
      document.body.appendChild(a); a.click(); a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      showToast(err?.response?.data?.message || 'Failed to download HTML report.', 'error');
    } finally {
      setBusyId(null);
    }
  }, [showToast]);

  const handleDownloadPdf = useCallback(async (scanId: number) => {
    setBusyId(scanId);
    try {
      const res = await apiClient.get(`/recon/scans/${scanId}/report/pdf`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url; a.download = `basir-recon-scan-${scanId}.pdf`;
      document.body.appendChild(a); a.click(); a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      showToast(err?.response?.data?.message || 'Failed to download PDF report.', 'error');
    } finally {
      setBusyId(null);
    }
  }, [showToast]);

  const handleViewClientReport = useCallback(async (clientId: number) => {
    setBusyId(-clientId); // negative to distinguish
    try {
      const res = await apiClient.get(`/recon/clients/${clientId}/report/html`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'text/html' }));
      window.open(url, '_blank');
      setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
    } catch (err: any) {
      showToast(err?.response?.data?.message || 'Failed to load client report.', 'error');
    } finally {
      setBusyId(null);
    }
  }, [showToast]);

  // (delete handler reserved for future use — Reports page wires it through
  // the per-row delete button in ScanReportTable)

  const onDeleteScanConfirm = async () => {
    if (!deleteScan) return;
    try {
      await deleteScanMut.mutateAsync(deleteScan.id);
      showToast(`Scan #${deleteScan.id} deleted.`, 'success');
    } catch (err: any) {
      showToast(err?.response?.data?.message || 'Failed to delete scan.', 'error');
    } finally {
      setDeleteScan(null);
    }
  };

  const isLoadingAll = isLoading || myClientsQ.isLoading;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-display font-bold text-dark-50">Reports</h1>
        <p className="text-dark-400 mt-1">
          Generate and download HTML / PDF reports. Client and Assigned-Target reports are
          protected — only My Scan reports can be deleted by users.
        </p>
      </div>

      <div className="glass-panel rounded-xl p-4">
        <Input
          id="search"
          placeholder="Search by target or scan ID..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          icon={<MagnifyingGlassIcon className="w-4 h-4" />}
        />
      </div>

      {isLoadingAll ? (
        <div className="flex justify-center py-12"><Spinner className="w-7 h-7" /></div>
      ) : completed.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-dark-400">
          <DocumentChartBarIcon className="w-10 h-10 mb-3 text-dark-600" />
          <p className="text-sm">No completed scans available for report generation.</p>
          <Link to={ROUTES.NETWORK_SCAN} className="mt-3">
            <button className="text-xs text-primary-300 hover:text-primary-200 transition-colors">
              Start a new scan →
            </button>
          </Link>
        </div>
      ) : (
        <>
          {/* Client reports section (merged view per client) */}
          {(myClientsQ.data || []).length > 0 && (
            <ReportSection title="Client Reports" subtitle="Merged report covering all completed scans for each assigned client.">
              {(myClientsQ.data || []).map(c => (
                <div
                  key={c.id}
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 py-3 border-b border-dark-800/70 last:border-b-0 hover:bg-primary-500/[0.04] transition-colors"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-display font-semibold text-dark-100">{c.name}</span>
                      <Badge variant="info" noDot>Client</Badge>
                      <Badge variant="neutral" noDot>{c.assets.length} asset(s)</Badge>
                    </div>
                    {c.company_name && (
                      <div className="text-xs text-dark-500 mt-0.5">{c.company_name}</div>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => c.id !== null && handleViewClientReport(c.id)}
                      disabled={c.id === null || busyId === -(c.id ?? 0)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-cyber text-white text-xs hover:brightness-110 transition-all disabled:opacity-60"
                      title={c.id === null ? 'Orphan pseudo-client — no merged report' : 'View merged report'}
                    >
                      {busyId === -(c.id ?? 0) ? <Spinner className="w-3.5 h-3.5" /> : <EyeIcon className="w-3.5 h-3.5" />}
                      View Merged Report
                    </button>
                  </div>
                </div>
              ))}
            </ReportSection>
          )}

          {/* Per-scan reports grouped by ownership */}
          <ReportSection
            title="Per-Scan Reports"
            subtitle="Individual completed scans grouped by source."
          >
            <ScanReportTable
              label="Client Scans"
              labelVariant="info"
              rows={filteredClient}
              busyId={busyId}
              onViewHtml={handleViewHtml}
              onDownloadHtml={handleDownloadHtml}
              onDownloadPdf={handleDownloadPdf}
              onDelete={(s) => setDeleteScan(s)}
              canDelete={isAdmin}
            />
            <ScanReportTable
              label="Assigned Target Scans"
              labelVariant="primary"
              rows={filteredAssigned}
              busyId={busyId}
              onViewHtml={handleViewHtml}
              onDownloadHtml={handleDownloadHtml}
              onDownloadPdf={handleDownloadPdf}
              onDelete={(s) => setDeleteScan(s)}
              canDelete={isAdmin}
            />
            <ScanReportTable
              label="My Scans"
              labelVariant="neutral"
              rows={filteredMy}
              busyId={busyId}
              onViewHtml={handleViewHtml}
              onDownloadHtml={handleDownloadHtml}
              onDownloadPdf={handleDownloadPdf}
              onDelete={(s) => setDeleteScan(s)}
              canDelete={true}
            />
          </ReportSection>
        </>
      )}

      <ConfirmDialog
        isOpen={!!deleteScan}
        title="Delete Scan Report"
        message={`Delete scan #${deleteScan?.id} on ${deleteScan?.target}? This will also delete all associated results.`}
        confirmLabel="Delete"
        cancelLabel="Cancel"
        isLoading={deleteScanMut.isPending}
        onConfirm={onDeleteScanConfirm}
        onCancel={() => setDeleteScan(null)}
      />
    </div>
  );
};

// ---------------------------------------------------------------------------
// Section wrapper
// ---------------------------------------------------------------------------
const ReportSection: React.FC<{
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}> = ({ title, subtitle, children }) => (
  <div className="glass-panel border-glow-top rounded-xl overflow-hidden">
    <div className="px-5 py-4 border-b border-dark-800">
      <h2 className="text-base font-display font-semibold text-dark-50">{title}</h2>
      {subtitle && <p className="text-xs text-dark-400 mt-1">{subtitle}</p>}
    </div>
    {children}
  </div>
);

// ---------------------------------------------------------------------------
// Per-scan table
// ---------------------------------------------------------------------------
const Th: React.FC<{ children?: React.ReactNode; className?: string }> = ({ children, className = '' }) => (
  <th className={cn('px-4 py-3 text-xs font-semibold text-dark-400 uppercase tracking-wider', className)}>{children}</th>
);

const ScanReportTable: React.FC<{
  label: string;
  labelVariant: 'info' | 'primary' | 'neutral';
  rows: ScanSummary[];
  busyId: number | null;
  onViewHtml: (id: number) => void;
  onDownloadHtml: (id: number) => void;
  onDownloadPdf: (id: number) => void;
  onDelete: (s: ScanSummary) => void;
  canDelete: boolean;
}> = ({ label, labelVariant, rows, busyId, onViewHtml, onDownloadHtml, onDownloadPdf, onDelete, canDelete }) => {
  if (rows.length === 0) return null;
  return (
    <div>
      <div className="px-4 py-2 bg-dark-900/40 border-b border-dark-800/50">
        <Badge variant={labelVariant} noDot>{label}</Badge>
        <span className="text-xs text-dark-500 ml-2">({rows.length})</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead className="bg-dark-950/60 border-b border-dark-800">
            <tr>
              <Th>Report ID</Th>
              <Th>Target</Th>
              <Th>Scan</Th>
              <Th>Source</Th>
              <Th>Generated By</Th>
              <Th>Created</Th>
              <Th className="text-right">Actions</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-dark-800/70">
            {rows.map(s => (
              <tr key={s.id} className="hover:bg-primary-500/[0.04] transition-colors">
                <td className="px-4 py-3 text-sm text-dark-300 font-mono">RPT-{String(s.id).padStart(5, '0')}</td>
                <td className="px-4 py-3 text-sm font-mono text-dark-100">{s.target}</td>
                <td className="px-4 py-3 text-sm">
                  <Link to={ROUTES.SCAN_DETAILS_BY_ID(s.id)} className="text-primary-300 hover:text-primary-200">
                    #{s.id}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <Badge variant={ownershipVariant(s.ownership_type)} noDot>
                    {ownershipLabel(s.ownership_type)}
                  </Badge>
                  {s.client_name && (
                    <div className="text-[10px] text-dark-500 mt-0.5">{s.client_name}</div>
                  )}
                </td>
                <td className="px-4 py-3 text-xs text-dark-300">
                  {s.user_username || `User #${s.user_id || '?'}`}
                </td>
                <td className="px-4 py-3 text-xs text-dark-400">
                  {s.completed_at ? new Date(s.completed_at).toLocaleString() : '—'}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => onViewHtml(s.id)}
                      disabled={busyId === s.id}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-dark-800 border border-dark-700 hover:border-primary-500/50 text-xs text-dark-100 hover:text-primary-300 transition-all disabled:opacity-60"
                    >
                      {busyId === s.id ? <Spinner className="w-3.5 h-3.5" /> : <EyeIcon className="w-3.5 h-3.5" />}
                      View
                    </button>
                    <button
                      type="button"
                      onClick={() => onDownloadHtml(s.id)}
                      disabled={busyId === s.id}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-dark-800 border border-dark-700 hover:border-primary-500/50 text-xs text-dark-100 hover:text-primary-300 transition-all disabled:opacity-60"
                    >
                      <DocumentArrowDownIcon className="w-3.5 h-3.5" />
                      HTML
                    </button>
                    <button
                      type="button"
                      onClick={() => onDownloadPdf(s.id)}
                      disabled={busyId === s.id}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-gradient-cyber text-white text-xs hover:brightness-110 transition-all disabled:opacity-60"
                    >
                      <DocumentArrowDownIcon className="w-3.5 h-3.5" />
                      PDF
                    </button>
                    {canDelete && (
                      <button
                        type="button"
                        onClick={() => onDelete(s)}
                        className="p-1.5 text-dark-400 hover:text-red-400 hover:bg-dark-800 rounded-lg transition-all"
                        title="Delete report"
                      >
                        <TrashIcon className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
