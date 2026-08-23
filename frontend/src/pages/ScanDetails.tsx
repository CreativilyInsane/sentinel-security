// frontend/src/pages/ScanDetails.tsx
import React, { useState, useMemo, useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeftIcon,
  ArrowPathIcon,
  XCircleIcon,
  DocumentArrowDownIcon,
  EyeIcon,
  XMarkIcon,
  CheckCircleIcon,
  ClockIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import { Button } from '@/components/ui/Button';
import { Badge, scanStatusVariant, severityVariant } from '@/components/ui/Badge';
import { Spinner } from '@/components/ui/Spinner';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { useLiveScanDetail, useCancelScan } from '@/hooks/useRecon';
import { useToast } from '@/context/ToastContext';
import { apiClient } from '@/api/client';
import { reconApi } from '@/api/recon.api';
import { ROUTES } from '@/routes/paths';
import { cn } from '@/utils/cn';
import type { ReconModule, ScanResultGrouped, ScanModuleStatus, ScanModuleStatusValue } from '@/types/recon.types';

const MODULE_LABEL: Record<ReconModule, string> = {
  host_discovery: 'Host Discovery',
  port_scan: 'Port Scan',
  service_detection: 'Service Detection',
  whois: 'WHOIS',
  dns: 'DNS Lookup',
  ssl: 'SSL / TLS',
  http: 'HTTP Headers',
  screenshot: 'Website Screenshot',
};

// Maps a ReconModule identifier (used in Scan.modules JSON) to the
// ScanDetails tab ID it should appear under.
const MODULE_TO_TAB: Record<ReconModule, TabId> = {
  host_discovery: 'hosts',
  port_scan: 'ports',
  service_detection: 'services',
  whois: 'whois',
  dns: 'dns',
  ssl: 'ssl',
  http: 'http',
  screenshot: 'screenshots',
};

type TabId =
  | 'overview' | 'hosts' | 'ports' | 'services'
  | 'dns' | 'whois' | 'ssl' | 'http' | 'screenshots';

const ALL_TABS: Array<{ id: TabId; label: string }> = [
  { id: 'overview', label: 'Overview' },
  { id: 'hosts', label: 'Hosts' },
  { id: 'ports', label: 'Ports' },
  { id: 'services', label: 'Services' },
  { id: 'dns', label: 'DNS' },
  { id: 'whois', label: 'WHOIS' },
  { id: 'ssl', label: 'SSL' },
  { id: 'http', label: 'HTTP' },
  { id: 'screenshots', label: 'Screenshots' },
];

export const ScanDetails: React.FC = () => {
  const { scanId } = useParams<{ scanId: string }>();
  const id = Number(scanId);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { showToast } = useToast();
  const { scan: scanQuery, results: resultsQuery } = useLiveScanDetail(id);
  const cancelScan = useCancelScan();

  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);
  const [screenshotBlobs, setScreenshotBlobs] = useState<Record<number, string>>({});
  const [moduleStatuses, setModuleStatuses] = useState<Record<string, ScanModuleStatus>>({});
  const [scanStatus, setScanStatus] = useState<string | null>(null);
  const [scanProgress, setScanProgress] = useState<number | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);

  const scan = scanQuery.data;
  const results: ScanResultGrouped | undefined = resultsQuery.data;

  // Build the list of tabs that should be visible — always Overview,
  // plus one tab per module that was actually selected for this scan.
  // This implements the requirement: "Scan Details only shows selected
  // module tabs" (Phase 19, requirement #10).
  const visibleTabs = useMemo(() => {
    if (!scan) return ALL_TABS.filter(t => t.id === 'overview');
    const selectedModules = (scan.modules || []) as ReconModule[];
    const visibleTabIds = new Set<TabId>(['overview']);
    for (const m of selectedModules) {
      const tabId = MODULE_TO_TAB[m];
      if (tabId) visibleTabIds.add(tabId);
    }
    return ALL_TABS.filter(t => visibleTabIds.has(t.id));
  }, [scan]);

  // If the active tab is no longer visible (e.g. the user switched scans),
  // fall back to Overview.
  useEffect(() => {
    if (!visibleTabs.find(t => t.id === activeTab)) {
      setActiveTab('overview');
    }
  }, [visibleTabs, activeTab]);

  // -----------------------------------------------------------------
  // Real-time scan status via Server-Sent Events (Phase 19).
  //
  // The SSE endpoint at /api/v1/recon/scans/{id}/events pushes named
  // events: snapshot, scan_started, module_started, module_completed,
  // module_failed, scan_completed, scan_cancelled, scan_failed.
  //
  // We use it to update local React state so the UI reflects module
  // transitions immediately, without waiting for the next 3s poll.
  //
  // The 3s polling in useLiveScanDetail remains as a fallback so the
  // UI stays correct even if SSE is blocked or the Redis pub/sub
  // connection is lost.
  // -----------------------------------------------------------------
  useEffect(() => {
    if (!id || !scan) return;

    // Only open SSE for scans that are still active.
    if (scan.status !== 'QUEUED' && scan.status !== 'RUNNING') {
      // Snapshot the final module statuses for terminal scans.
      if (scan.module_statuses) {
        const map: Record<string, ScanModuleStatus> = {};
        for (const ms of scan.module_statuses) {
          map[ms.module_name] = ms;
        }
        setModuleStatuses(map);
      }
      setScanStatus(scan.status);
      setScanProgress(scan.progress);
      return;
    }

    let closed = false;
    const openSse = () => {
      if (closed) return;
      try {
        const url = reconApi.scanEventsUrl(id);
        const es = new EventSource(url);
        eventSourceRef.current = es;

        es.addEventListener('snapshot', (e: MessageEvent) => {
          try {
            const data = JSON.parse(e.data);
            if (data.scan) {
              setScanStatus(data.scan.status);
              setScanProgress(data.scan.progress);
            }
            if (data.module_statuses) {
              const map: Record<string, ScanModuleStatus> = {};
              for (const ms of data.module_statuses) {
                map[ms.module_name] = ms;
              }
              setModuleStatuses(map);
            }
            // Refresh the underlying query so results are up-to-date.
            qc.invalidateQueries({ queryKey: ['recon', 'scan', id] });
            qc.invalidateQueries({ queryKey: ['recon', 'scan-results', id] });
          } catch (err) {
            // ignore malformed payloads
          }
        });

        es.addEventListener('scan_started', () => {
          setScanStatus('RUNNING');
        });

        es.addEventListener('module_started', (e: MessageEvent) => {
          try {
            const payload = JSON.parse(e.data);
            const moduleName = payload.module;
            if (moduleName) {
              setModuleStatuses(prev => ({
                ...prev,
                [moduleName]: {
                  module_name: moduleName,
                  status: 'RUNNING' as ScanModuleStatusValue,
                  progress: 50,
                  error_message: null,
                  started_at: new Date().toISOString(),
                  completed_at: null,
                },
              }));
            }
          } catch {}
        });

        es.addEventListener('module_completed', (e: MessageEvent) => {
          try {
            const payload = JSON.parse(e.data);
            const moduleName = payload.module;
            if (moduleName) {
              setModuleStatuses(prev => ({
                ...prev,
                [moduleName]: {
                  module_name: moduleName,
                  status: 'COMPLETED' as ScanModuleStatusValue,
                  progress: 100,
                  error_message: null,
                  started_at: prev[moduleName]?.started_at || null,
                  completed_at: new Date().toISOString(),
                },
              }));
              // Refresh results so the new module's data appears.
              qc.invalidateQueries({ queryKey: ['recon', 'scan-results', id] });
            }
          } catch {}
        });

        es.addEventListener('module_failed', (e: MessageEvent) => {
          try {
            const payload = JSON.parse(e.data);
            const moduleName = payload.module;
            if (moduleName) {
              setModuleStatuses(prev => ({
                ...prev,
                [moduleName]: {
                  module_name: moduleName,
                  status: 'FAILED' as ScanModuleStatusValue,
                  progress: 100,
                  error_message: payload.error || 'Module failed',
                  started_at: prev[moduleName]?.started_at || null,
                  completed_at: new Date().toISOString(),
                },
              }));
              qc.invalidateQueries({ queryKey: ['recon', 'scan-results', id] });
            }
          } catch {}
        });

        es.addEventListener('scan_completed', () => {
          setScanStatus('COMPLETED');
          setScanProgress(100);
          qc.invalidateQueries({ queryKey: ['recon', 'scan', id] });
          qc.invalidateQueries({ queryKey: ['recon', 'scan-results', id] });
          es.close();
        });

        es.addEventListener('scan_cancelled', () => {
          setScanStatus('CANCELLED');
          qc.invalidateQueries({ queryKey: ['recon', 'scan', id] });
          es.close();
        });

        es.addEventListener('scan_failed', () => {
          setScanStatus('FAILED');
          qc.invalidateQueries({ queryKey: ['recon', 'scan', id] });
          es.close();
        });

        es.onerror = () => {
          // The browser auto-reconnects EventSource, but if it fails
          // repeatedly we close it and schedule a manual re-open.
          es.close();
          if (!closed) {
            reconnectTimerRef.current = window.setTimeout(openSse, 3000);
          }
        };
      } catch (err) {
        // EventSource not available — fall back to polling only.
      }
    };

    openSse();

    return () => {
      closed = true;
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };
  }, [id, scan?.status]);

  const duration = useMemo(() => {
    if (!scan?.started_at) return null;
    const start = new Date(scan.started_at).getTime();
    const end = scan.completed_at ? new Date(scan.completed_at).getTime() : Date.now();
    const ms = Math.max(0, end - start);
    const s = Math.floor(ms / 1000);
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60);
    return `${m}m ${s % 60}s`;
  }, [scan?.started_at, scan?.completed_at]);

  // Screenshot blob fetcher — MUST be declared before any early returns so
  // the Rules of Hooks are not violated (hooks must run in the same order
  // on every render, regardless of loading/error state).
  useEffect(() => {
    if (!results?.screenshot) return;
    const captured = results.screenshot.filter(s => s.captured);
    if (!captured.length) return;

    captured.forEach((s, i) => {
      if (s.screenshot_url && !screenshotBlobs[i]) {
        apiClient.get(s.screenshot_url, { responseType: 'blob' })
          .then(res => {
            const url = window.URL.createObjectURL(res.data);
            setScreenshotBlobs(prev => {
              if (prev[i]) return prev;  // avoid overwriting an existing blob
              return { ...prev, [i]: url };
            });
          })
          .catch(() => {});
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [results?.screenshot]);

  if (scanQuery.isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Spinner className="w-8 h-8" />
      </div>
    );
  }

  if (scanQuery.isError || !scan) {
    const err = scanQuery.error as any;
    const msg =
      err?.response?.data?.message ||
      err?.response?.data?.detail ||
      'Unable to load this scan. It may have been deleted, or you may not have access to it.';
    return (
      <div className="max-w-3xl mx-auto py-10">
        <button
          onClick={() => navigate(ROUTES.PREVIOUS_SCANS)}
          className="text-xs text-dark-400 hover:text-primary-300 transition-colors flex items-center gap-1 mb-4"
        >
          <ArrowLeftIcon className="w-3.5 h-3.5" />
          Back to scans
        </button>
        <div className="glass-panel rounded-xl p-6 border border-red-600/30">
          <ExclamationTriangleIcon className="w-8 h-8 text-red-400 mb-3" />
          <h2 className="text-lg font-display font-semibold text-dark-50 mb-2">
            Scan not available
          </h2>
          <p className="text-sm text-dark-300">{msg}</p>
          <Link
            to={ROUTES.PREVIOUS_SCANS}
            className="inline-flex items-center gap-1.5 mt-4 text-xs text-primary-300 hover:text-primary-200"
          >
            <ArrowLeftIcon className="w-3.5 h-3.5" />
            Return to Previous Scans
          </Link>
        </div>
      </div>
    );
  }

  const handleDownloadPdf = async (scanId: number) => {
    try {
      const res = await apiClient.get(`/recon/scans/${scanId}/report/pdf`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `basir-recon-scan-${scanId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      const msg = err?.response?.data?.message || 'Failed to download PDF report.';
      showToast(msg, 'error');
    }
  };

  const handleViewHtml = async (scanId: number) => {
    try {
      const res = await apiClient.get(`/recon/scans/${scanId}/report/html`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'text/html' }));
      window.open(url, '_blank');
    } catch {
      showToast('Failed to load HTML report.', 'error');
    }
  };

  const onCancel = async () => {
    try {
      await cancelScan.mutateAsync(scan.id);
      showToast('Scan cancellation requested.', 'info');
    } catch (err: any) {
      showToast(err?.response?.data?.message || 'Failed to cancel scan.', 'error');
    }
  };

  // Effective status / progress — prefer the SSE-pushed values, fall
  // back to the polled query data.
  const effectiveStatus = scanStatus || scan.status;
  const effectiveProgress = scanProgress !== null ? scanProgress : scan.progress;
  const effectiveIsRunning = effectiveStatus === 'QUEUED' || effectiveStatus === 'RUNNING';

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
        <div className="space-y-1">
          <button
            onClick={() => navigate(ROUTES.PREVIOUS_SCANS)}
            className="text-xs text-dark-400 hover:text-primary-300 transition-colors flex items-center gap-1"
          >
            <ArrowLeftIcon className="w-3.5 h-3.5" />
            Back to scans
          </button>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-display font-bold text-dark-50">Scan #{scan.id}</h1>
            <Badge variant={scanStatusVariant(effectiveStatus)}>{effectiveStatus}</Badge>
          </div>
          <p className="text-sm text-dark-400 font-mono">{scan.target}</p>
        </div>
        <div className="flex gap-2">
          {effectiveIsRunning && (
            <Button variant="secondary" size="sm" onClick={onCancel} isLoading={cancelScan.isPending}>
              <XCircleIcon className="w-4 h-4 mr-1.5" />
              Cancel
            </Button>
          )}
          {effectiveStatus === 'COMPLETED' && (
            <>
              <Button variant="secondary" size="sm" onClick={() => handleViewHtml(scan.id)}>
                <EyeIcon className="w-4 h-4 mr-1.5" />
                View HTML
              </Button>
              <Button variant="primary" size="sm" onClick={() => handleDownloadPdf(scan.id)}>
                <DocumentArrowDownIcon className="w-4 h-4 mr-1.5" />
                PDF
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Progress + meta */}
      <div className="glass-panel border-glow-top rounded-xl p-5 space-y-4">
        <ProgressBar
          value={effectiveProgress}
          label="Overall Progress"
          animated={effectiveIsRunning}
        />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 pt-2">
          <Meta label="Target" value={scan.target} mono />
          <Meta label="Type" value={scan.target_type} />
          <Meta label="Started" value={scan.started_at ? new Date(scan.started_at).toLocaleString() : '—'} />
          <Meta label="Completed" value={scan.completed_at ? new Date(scan.completed_at).toLocaleString() : '—'} />
          <Meta label="Duration" value={duration ?? '—'} />
          <Meta label="Modules" value={`${scan.modules.length} selected`} />
        </div>
        {scan.error_message && (
          <div className="flex items-start gap-2 p-3 rounded-lg bg-red-900/20 border border-red-600/40">
            <ExclamationTriangleIcon className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <p className="text-xs text-red-300">{scan.error_message}</p>
          </div>
        )}
      </div>

      {/* Module progress strip — per-module status (Phase 19 real-time UI).
          Shows one card per selected module with its current lifecycle
          state (QUEUED / RUNNING / COMPLETED / FAILED / CANCELLED).
          Module failures are shown independently — one failing module
          does NOT mark the scan as failed. */}
      <div className="glass-panel rounded-xl p-4">
        <div className="text-xs uppercase tracking-wider text-dark-500 mb-3">
          Module Status
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
          {scan.modules.map((m) => {
            const ms = moduleStatuses[m];
            const status = ms?.status || (effectiveStatus === 'COMPLETED' ? 'COMPLETED' : 'QUEUED');
            const statusColor =
              status === 'COMPLETED'
                ? 'border-primary-500/40 bg-primary-500/10 text-primary-300'
                : status === 'RUNNING'
                ? 'border-amber-500/40 bg-amber-500/10 text-amber-300'
                : status === 'FAILED'
                ? 'border-red-500/40 bg-red-500/10 text-red-300'
                : status === 'CANCELLED'
                ? 'border-dark-700 bg-dark-900/40 text-dark-500'
                : 'border-dark-700 bg-dark-900/40 text-dark-400';
            const Icon =
              status === 'COMPLETED'
                ? CheckCircleIcon
                : status === 'RUNNING'
                ? ArrowPathIcon
                : status === 'FAILED'
                ? ExclamationTriangleIcon
                : status === 'CANCELLED'
                ? XCircleIcon
                : ClockIcon;
            return (
              <div
                key={m}
                className={cn(
                  'flex flex-col items-center gap-1 p-2 rounded-lg border',
                  statusColor,
                )}
                title={ms?.error_message || status}
              >
                <Icon
                  className={cn(
                    'w-4 h-4',
                    status === 'RUNNING' && 'animate-spin',
                  )}
                />
                <span className="text-[10px] font-medium text-center leading-tight">
                  {MODULE_LABEL[m]}
                </span>
                <span className="text-[9px] uppercase tracking-wider opacity-75">
                  {status}
                </span>
              </div>
            );
          })}
        </div>
        {/* Show per-module failure errors (if any). */}
        {Object.values(moduleStatuses).some(ms => ms.status === 'FAILED' && ms.error_message) && (
          <div className="mt-3 space-y-1">
            {Object.values(moduleStatuses)
              .filter(ms => ms.status === 'FAILED' && ms.error_message)
              .map(ms => (
                <div
                  key={ms.module_name}
                  className="text-xs text-red-300 flex items-start gap-2"
                >
                  <span className="font-mono text-red-400 shrink-0">[{ms.module_name}]</span>
                  <span>{ms.error_message}</span>
                </div>
              ))}
          </div>
        )}
      </div>

      {/* Tabs — only show tabs for modules that were actually selected
          for this scan (Phase 19 requirement #10). */}
      <div className="glass-panel border-glow-top rounded-xl overflow-hidden">
        <div className="flex overflow-x-auto border-b border-dark-800">
          {visibleTabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={cn(
                'px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors border-b-2',
                activeTab === t.id
                  ? 'text-primary-300 border-primary-500 bg-primary-500/5'
                  : 'text-dark-400 border-transparent hover:text-dark-100 hover:bg-dark-800/40'
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="p-5">
          {resultsQuery.isLoading ? (
            <div className="flex justify-center py-10">
              <Spinner />
            </div>
          ) : resultsQuery.isError ? (
            <div className="flex flex-col items-center justify-center py-10 text-red-300">
              <ExclamationTriangleIcon className="w-8 h-8 mb-2 text-red-400" />
              <p className="text-sm">Failed to load results for this scan.</p>
              <button
                onClick={() => resultsQuery.refetch()}
                className="mt-3 text-xs text-primary-300 hover:text-primary-200"
              >
                Try again
              </button>
            </div>
          ) : !results ? (
            <div className="flex flex-col items-center justify-center py-10 text-dark-400">
              <ClockIcon className="w-8 h-8 mb-2 text-dark-600" />
              <p className="text-sm">
                {effectiveIsRunning
                  ? 'Scan is running — results will appear here as modules complete.'
                  : 'No results are available for this scan.'}
              </p>
              {effectiveIsRunning && (
                <button
                  onClick={() => resultsQuery.refetch()}
                  className="mt-3 text-xs text-primary-300 hover:text-primary-200"
                >
                  Refresh now
                </button>
              )}
            </div>
          ) : (
            <TabContent tab={activeTab} scan={scan} results={results} onLightbox={setLightboxUrl} screenshotBlobs={screenshotBlobs} />
          )}
        </div>
      </div>

      {/* Lightbox */}
      {lightboxUrl && (
        <div
          className="fixed inset-0 z-50 bg-dark-950/90 backdrop-blur-md flex items-center justify-center p-6"
          onClick={() => setLightboxUrl(null)}
        >
          <button
            className="absolute top-4 right-4 text-dark-400 hover:text-primary-300"
            onClick={() => setLightboxUrl(null)}
          >
            <XMarkIcon className="w-6 h-6" />
          </button>
          <img
            src={lightboxUrl}
            alt="Screenshot preview"
            className="max-w-full max-h-full rounded-lg border border-dark-700 shadow-2xl"
          />
        </div>
      )}
    </div>
  );
};

const Meta: React.FC<{ label: string; value: string | number; mono?: boolean }> = ({ label, value, mono }) => (
  <div>
    <div className="text-[10px] uppercase tracking-wider text-dark-500 mb-1">{label}</div>
    <div className={cn('text-sm text-dark-100', mono && 'font-mono text-xs')}>{value}</div>
  </div>
);

// ---------------------------------------------------------------------------
// Tab content dispatcher
// ---------------------------------------------------------------------------
const TabContent: React.FC<{
  tab: TabId;
  scan: any;
  results: ScanResultGrouped;
  onLightbox: (url: string) => void;
  screenshotBlobs: Record<number, string>;
}> = ({ tab, results, onLightbox, screenshotBlobs }) => {
  switch (tab) {
    case 'overview':  return <OverviewTab results={results} />;
    case 'hosts':     return <HostsTab results={results} />;
    case 'ports':     return <PortsTab results={results} />;
    case 'services':  return <ServicesTab results={results} />;
    case 'dns':       return <DnsTab results={results} />;
    case 'whois':     return <WhoisTab results={results} />;
    case 'ssl':       return <SslTab results={results} />;
    case 'http':      return <HttpTab results={results} />;
    case 'screenshots': return <ScreenshotsTab results={results} onLightbox={onLightbox} screenshotBlobs={screenshotBlobs} />;
    default: return null;
  }
};

// ---- Overview tab ----
const OverviewTab: React.FC<{ results: ScanResultGrouped }> = ({ results }) => {
  const hosts = results.host_discovery.flatMap(h => h.hosts || []);
  const openPorts = results.port_scan
    .flatMap(ps => ps.scans || [])
    .flatMap(s => (s.ports || []).filter(p => p.state === 'open'));
  const dnsRecords = results.dns.flatMap(d => d.records || []);
  const errors = results.errors || [];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      <Stat label="Hosts Discovered" value={hosts.length} />
      <Stat label="Open Ports" value={openPorts.length} />
      <Stat label="DNS Records" value={dnsRecords.length} />
      <Stat label="Errors" value={errors.length} />
      {errors.length > 0 && (
        <div className="sm:col-span-2 lg:col-span-4 mt-2">
          <div className="rounded-lg border border-red-600/30 bg-red-900/10 p-3">
            <div className="text-xs uppercase tracking-wider text-red-400 mb-2">Module Errors</div>
            <ul className="space-y-1">
              {errors.map((e, i) => (
                <li key={i} className="text-xs text-red-300">
                  <span className="font-mono text-red-400">[{e.module}]</span> {e.error}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};

const Stat: React.FC<{ label: string; value: number }> = ({ label, value }) => (
  <div className="rounded-lg border border-dark-700 bg-dark-900/40 p-4">
    <div className="text-2xl font-data font-bold text-primary-300">{value}</div>
    <div className="text-xs text-dark-400 mt-1">{label}</div>
  </div>
);

// ---- Hosts tab ----
const HostsTab: React.FC<{ results: ScanResultGrouped }> = ({ results }) => {
  const hosts = results.host_discovery.flatMap(h => h.hosts || []);
  if (!hosts.length) return <EmptyState label="No host discovery results yet." />;
  return (
    <Table
      headers={['Host', 'IP', 'Hostname', 'Status', 'Latency (ms)']}
      rows={hosts.map(h => [
        h.host,
        h.ip || '—',
        h.hostname || '—',
        <Badge key="s" variant={h.status === 'up' ? 'success' : 'danger'} noDot>{h.status}</Badge>,
        h.latency_ms != null ? String(h.latency_ms) : '—',
      ])}
    />
  );
};

// ---- Ports tab ----
const PortsTab: React.FC<{ results: ScanResultGrouped }> = ({ results }) => {
  const ports = results.port_scan
    .flatMap(ps => ps.scans || [])
    .flatMap(s => (s.ports || []).map(p => ({ ...p, ip: s.ip, host: s.host })));
  if (!ports.length) return <EmptyState label="No port scan results yet." />;
  return (
    <Table
      headers={['Port', 'Protocol', 'State', 'Service', 'Version', 'Host']}
      rows={ports.map(p => [
        String(p.port),
        p.protocol,
        <Badge key="st" variant={p.state === 'open' ? 'success' : 'neutral'} noDot>{p.state}</Badge>,
        p.service_guess,
        '—',
        p.ip,
      ])}
    />
  );
};

// ---- Services tab ----
const ServicesTab: React.FC<{ results: ScanResultGrouped }> = ({ results }) => {
  const services = results.service
    .flatMap(s => s.scans || [])
    .flatMap(s => (s.services || []).map(svc => ({ ...svc, ip: s.ip })));
  if (!services.length) return <EmptyState label="No service detection results yet." />;
  return (
    <Table
      headers={['Port', 'Service', 'Protocol', 'Banner', 'Version', 'Confidence']}
      rows={services.map(s => [
        String(s.port),
        s.service,
        s.protocol,
        s.banner ? <span className="font-mono text-xs">{s.banner.slice(0, 80)}</span> : '—',
        s.version || '—',
        <Badge key="c" variant={s.confidence === 'high' ? 'success' : s.confidence === 'medium' ? 'warning' : 'neutral'} noDot>{s.confidence}</Badge>,
      ])}
    />
  );
};

// ---- DNS tab ----
const DnsTab: React.FC<{ results: ScanResultGrouped }> = ({ results }) => {
  const records = results.dns.flatMap(d => d.records || []);
  if (!records.length) return <EmptyState label="No DNS records resolved." />;
  return (
    <Table
      headers={['Type', 'Name', 'Value', 'TTL']}
      rows={records.map((r, i) => [
        <Badge key={i} variant="info" noDot>{r.record_type}</Badge>,
        r.name,
        <span className="font-mono text-xs">{r.values.join(', ')}</span>,
        String(r.ttl),
      ])}
    />
  );
};

// ---- WHOIS tab ----
const WhoisTab: React.FC<{ results: ScanResultGrouped }> = ({ results }) => {
  const w = results.whois as any;
  if (!w || !w.target) return <EmptyState label="No WHOIS data available." />;
  if (w.available === false) {
    return <EmptyState label={w.error || 'WHOIS data not available.'} />;
  }
  const rows: Array<[string, React.ReactNode]> = [
    ['Domain', fmt(w.domain)],
    ['Registrar', fmt(w.registrar)],
    ['Creation Date', fmt(w.creation_date)],
    ['Expiration Date', fmt(w.expiration_date)],
    ['Updated Date', fmt(w.updated_date)],
    ['Name Servers', fmt(w.name_servers)],
    ['Status', fmt(w.status)],
  ];
  if (w.registrant) {
    rows.push(
      ['Registrant Name', fmt(w.registrant.name)],
      ['Registrant Org', fmt(w.registrant.organization)],
      ['Registrant Country', fmt(w.registrant.country)],
    );
  }
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
      {rows.map(([k, v]) => (
        <div key={k} className="flex gap-3 p-2 rounded border border-dark-700 bg-dark-900/40">
          <div className="w-1/3 text-xs text-dark-400 uppercase tracking-wider">{k}</div>
          <div className="flex-1 text-sm text-dark-100 break-all">{v}</div>
        </div>
      ))}
    </div>
  );
};

const fmt = (v: any): React.ReactNode => {
  if (v == null || v === '') return '—';
  if (Array.isArray(v)) return v.length ? v.join(', ') : '—';
  return String(v);
};

// ---- SSL tab ----
const SslTab: React.FC<{ results: ScanResultGrouped }> = ({ results }) => {
  const s = results.ssl as any;
  if (!s || !s.hostname) return <EmptyState label="No SSL / TLS data available." />;
  if (s.available === false) {
    return <EmptyState label={s.error || 'TLS handshake failed.'} />;
  }
  const statusVariant =
    s.expiration_status === 'Valid' ? 'success'
    : s.expiration_status === 'Expiring Soon' ? 'warning'
    : s.expiration_status === 'Expired' ? 'danger' : 'neutral';

  const rows: Array<[string, React.ReactNode]> = [
    ['Status', <Badge key="st" variant={statusVariant} noDot>{s.expiration_status}</Badge>],
    ['Hostname', s.hostname],
    ['Port', String(s.port)],
    ['Issuer', s.certificate_issuer],
    ['Subject', s.certificate_subject],
    ['Valid From', s.valid_from],
    ['Valid Until', s.valid_until],
    ['Days Remaining', s.days_remaining != null ? String(s.days_remaining) : '—'],
    ['Signature Algorithm', s.signature_algorithm],
    ['Public Key Algorithm', s.public_key_algorithm],
    ['Serial Number', <span className="font-mono text-xs">{s.serial_number}</span>],
    ['Chain Status', s.chain_status],
    ['SANs', Array.isArray(s.sans) && s.sans.length ? s.sans.join(', ') : '—'],
  ];
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
      {rows.map(([k, v]) => (
        <div key={k} className="flex gap-3 p-2 rounded border border-dark-700 bg-dark-900/40">
          <div className="w-1/3 text-xs text-dark-400 uppercase tracking-wider">{k}</div>
          <div className="flex-1 text-sm text-dark-100 break-all">{v}</div>
        </div>
      ))}
    </div>
  );
};

// ---- HTTP tab ----
const HttpTab: React.FC<{ results: ScanResultGrouped }> = ({ results }) => {
  const h = results.http as any;
  if (!h || !h.url) return <EmptyState label="No HTTP analysis available." />;
  if (h.available === false) {
    return <EmptyState label={h.error || 'HTTP request failed.'} />;
  }
  const secHeaders = h.security_headers || [];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Meta label="Status" value={h.status_code ?? '—'} />
        <Meta label="Server" value={h.server || '—'} />
        <Meta label="Content-Type" value={h.content_type || '—'} />
        <Meta label="Redirected" value={h.redirected ? 'Yes' : 'No'} />
      </div>
      <div>
        <h3 className="text-sm font-display font-semibold text-dark-100 mb-2">Security Headers</h3>
        <Table
          headers={['Header', 'Status', 'Value', 'Severity']}
          rows={secHeaders.map((sh: any) => [
            sh.header,
            sh.present
              ? <Badge key="p" variant="success" noDot>Present</Badge>
              : <Badge key="p" variant="danger" noDot>Missing</Badge>,
            sh.value ? <span className="font-mono text-xs break-all">{sh.value.slice(0, 80)}</span> : '—',
            <Badge key="sv" variant={severityVariant(sh.severity)} noDot>{sh.severity}</Badge>,
          ])}
        />
      </div>
    </div>
  );
};

// ---- Screenshots tab ----
const ScreenshotsTab: React.FC<{
  results: ScanResultGrouped;
  onLightbox: (url: string) => void;
  screenshotBlobs: Record<number, string>;
}> = ({ results, onLightbox, screenshotBlobs }) => {
  const shots = results.screenshot || [];
  if (!shots.length) return <EmptyState label="No screenshots captured." />;
  const capturedShots = shots.filter(s => s.captured);
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {capturedShots.map((s, i) => {
        const blobUrl = screenshotBlobs[i] || '';
        return (
          <figure
            key={i}
            className="rounded-lg overflow-hidden border border-dark-700 bg-dark-900/40 hover:border-primary-500/40 transition-colors cursor-pointer"
            onClick={() => blobUrl && onLightbox(blobUrl)}
          >
            {blobUrl ? (
              <img
                src={blobUrl}
                alt={`Screenshot of ${s.url}`}
                className="w-full h-auto"
              />
            ) : (
              <div className="flex items-center justify-center h-48 bg-dark-900/60">
                <Spinner className="w-6 h-6" />
              </div>
            )}
            <figcaption className="p-2 text-xs text-dark-400 font-mono break-all">{s.url}</figcaption>
          </figure>
        );
      })}
      {shots.filter(s => !s.captured).map((s, i) => (
        <div key={`err-${i}`} className="rounded-lg p-4 border border-red-600/30 bg-red-900/10">
          <ExclamationTriangleIcon className="w-5 h-5 text-red-400 mb-2" />
          <p className="text-xs text-red-300 break-all">{s.url}</p>
          <p className="text-xs text-red-400 mt-1">{s.error}</p>
        </div>
      ))}
    </div>
  );
};

// ---- Generic table ----
const Table: React.FC<{ headers: string[]; rows: React.ReactNode[][] }> = ({ headers, rows }) => (
  <div className="overflow-x-auto">
    <table className="w-full text-left">
      <thead className="bg-dark-950/60 border-b border-dark-800">
        <tr>
          {headers.map((h, i) => (
            <th key={i} className="px-3 py-2.5 text-xs font-semibold text-dark-400 uppercase tracking-wider">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-dark-800/70">
        {rows.map((row, ri) => (
          <tr key={ri} className="hover:bg-primary-500/[0.04] transition-colors">
            {row.map((cell, ci) => (
              <td key={ci} className="px-3 py-2.5 text-sm text-dark-200">{cell}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

const EmptyState: React.FC<{ label: string }> = ({ label }) => (
  <div className="flex flex-col items-center justify-center py-10 text-dark-400">
    <ClockIcon className="w-8 h-8 mb-2 text-dark-600" />
    <p className="text-sm">{label}</p>
  </div>
);
