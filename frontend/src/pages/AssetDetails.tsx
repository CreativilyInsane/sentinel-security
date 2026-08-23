// frontend/src/pages/AssetDetails.tsx
import React, { useState, useMemo } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeftIcon,
  ServerStackIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  ArrowTopRightOnSquareIcon,
} from '@heroicons/react/24/outline';
import { Badge } from '@/components/ui/Badge';
import { Spinner } from '@/components/ui/Spinner';
import { Button } from '@/components/ui/Button';
import { useAssetsByHost, useScans } from '@/hooks/useRecon';
import { ROUTES } from '@/routes/paths';
import { cn } from '@/utils/cn';
import type { Asset } from '@/types/recon.types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const fmtDate = (iso?: string | null): string => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return String(iso);
  }
};

const Th: React.FC<{ children?: React.ReactNode; className?: string }> = ({
  children,
  className = '',
}) => (
  <th
    className={cn(
      'px-4 py-3 text-xs font-semibold text-dark-400 uppercase tracking-wider',
      className,
    )}
  >
    {children}
  </th>
);

// ---------------------------------------------------------------------------
// Main AssetDetails page
// ---------------------------------------------------------------------------
export const AssetDetails: React.FC = () => {
  const { host: rawHost } = useParams<{ host: string }>();
  const navigate = useNavigate();
  const host = useMemo(() => {
    try {
      return rawHost ? decodeURIComponent(rawHost) : '';
    } catch {
      return rawHost || '';
    }
  }, [rawHost]);

  const { data, isLoading, isError, isFetching, refetch } = useAssetsByHost(
    host || null,
  );

  // Also pull scans for this host so we can cross-link to scan details.
  const scansQuery = useScans({ limit: 50, target: host || undefined });
  const relatedScans = useMemo(() => {
    if (!scansQuery.data) return [];
    // The backend uses ilike substring match; filter exact host matches
    return scansQuery.data.filter(s => s.target.includes(host));
  }, [scansQuery.data, host]);

  const assets = data || [];

  // Compute aggregate info
  const aggregate = useMemo(() => {
    const portAssets = assets.filter(a => a.port != null);
    const openPorts = portAssets.filter(
      a => a.status === 'open' || a.status === 'up',
    );
    const uniqueIps = new Set(assets.map(a => a.ip_address).filter(Boolean));
    const uniqueServices = new Set(
      assets.map(a => a.service).filter(Boolean) as string[],
    );
    const uniqueProtocols = new Set(
      assets.map(a => a.protocol).filter(Boolean) as string[],
    );
    const lastSeen = assets
      .map(a => a.last_seen)
      .filter(Boolean)
      .sort()
      .pop();
    const firstSeen = assets
      .map(a => a.first_seen)
      .filter(Boolean)
      .sort()
      .shift();
    return {
      total: assets.length,
      portCount: portAssets.length,
      openCount: openPorts.length,
      ipCount: uniqueIps.size,
      serviceCount: uniqueServices.size,
      protocols: Array.from(uniqueProtocols),
      lastSeen,
      firstSeen,
      openPorts,
    };
  }, [assets]);

  if (!host) {
    return (
      <div className="max-w-3xl mx-auto py-10">
        <div className="glass-panel rounded-xl p-6 border border-red-600/30">
          <ExclamationTriangleIcon className="w-8 h-8 text-red-400 mb-3" />
          <h2 className="text-lg font-display font-semibold text-dark-50 mb-2">
            No host specified
          </h2>
          <p className="text-sm text-dark-300">
            The URL is missing the host parameter.
          </p>
          <Link
            to={ROUTES.ASSETS}
            className="inline-flex items-center gap-1.5 mt-4 text-xs text-primary-300 hover:text-primary-200"
          >
            <ArrowLeftIcon className="w-3.5 h-3.5" />
            Back to Assets
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="space-y-1">
        <button
          onClick={() => navigate(ROUTES.ASSETS)}
          className="text-xs text-dark-400 hover:text-primary-300 transition-colors flex items-center gap-1"
        >
          <ArrowLeftIcon className="w-3.5 h-3.5" />
          Back to Assets
        </button>
        <div className="flex items-center gap-3 flex-wrap">
          <ServerStackIcon className="w-7 h-7 text-primary-300" />
          <h1 className="text-2xl font-display font-bold text-dark-50 break-all">
            {host}
          </h1>
          <Badge variant="info" noDot>
            Asset Detail
          </Badge>
        </div>
        <p className="text-sm text-dark-400">
          Full inventory of ports, services, and metadata discovered for this
          host across all of its scans.
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <SummaryCard
          label="Open Ports"
          value={String(aggregate.openCount)}
          variant={aggregate.openCount > 0 ? 'success' : 'neutral'}
        />
        <SummaryCard
          label="Total Records"
          value={String(aggregate.total)}
        />
        <SummaryCard
          label="Unique Services"
          value={String(aggregate.serviceCount)}
          variant={aggregate.serviceCount > 0 ? 'info' : 'neutral'}
        />
        <SummaryCard
          label="Unique IPs"
          value={String(aggregate.ipCount)}
        />
        <SummaryCard
          label="Protocols"
          value={aggregate.protocols.join(', ') || '—'}
        />
        <SummaryCard
          label="Last Seen"
          value={fmtDate(aggregate.lastSeen)}
        />
      </div>

      {/* Ports & services table */}
      <div className="glass-panel border-glow-top rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-dark-800">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-primary-400 shadow-glow-sm" />
            <h2 className="text-base font-display font-semibold text-dark-50">
              Ports &amp; Services
            </h2>
            <span className="text-xs text-dark-500">
              ({assets.length} record{assets.length === 1 ? '' : 's'})
            </span>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => refetch()}
            isLoading={isFetching && !isLoading}
          >
            <ArrowPathIcon className="w-4 h-4 mr-1.5" />
            Refresh
          </Button>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-12">
            <Spinner className="w-7 h-7" />
          </div>
        ) : isError ? (
          <div className="flex flex-col items-center justify-center py-12 text-red-300">
            <ExclamationTriangleIcon className="w-8 h-8 mb-2 text-red-400" />
            <p className="text-sm">Failed to load assets for this host.</p>
            <button
              onClick={() => refetch()}
              className="mt-3 text-xs text-primary-300 hover:text-primary-200"
            >
              Try again
            </button>
          </div>
        ) : assets.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-dark-400">
            <ClockIcon className="w-10 h-10 mb-3 text-dark-600" />
            <p className="text-sm">No assets recorded for this host yet.</p>
            <Link to={ROUTES.NETWORK_SCAN} className="mt-3">
              <Button variant="secondary" size="sm">
                Run a new scan
              </Button>
            </Link>
          </div>
        ) : (
          <AssetsTable assets={assets} />
        )}
      </div>

      {/* Related scans */}
      {relatedScans.length > 0 && (
        <div className="glass-panel rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-dark-800 flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-primary-400 shadow-glow-sm" />
            <h2 className="text-base font-display font-semibold text-dark-50">
              Related Scans
            </h2>
            <span className="text-xs text-dark-500">
              ({relatedScans.length})
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-dark-950/60 border-b border-dark-800">
                <tr>
                  <Th>Scan ID</Th>
                  <Th>Target</Th>
                  <Th>Status</Th>
                  <Th>Started</Th>
                  <Th>Completed</Th>
                  <Th className="text-right">Actions</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-800/70">
                {relatedScans.map(s => (
                  <tr
                    key={s.id}
                    className="hover:bg-primary-500/[0.04] transition-colors"
                  >
                    <td className="px-4 py-3 text-sm text-dark-400 font-mono">
                      #{s.id}
                    </td>
                    <td className="px-4 py-3 text-sm font-mono text-dark-100">
                      {s.target}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={scanStatusVariantLocal(s.status)} noDot>
                        {s.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-xs text-dark-300">
                      {s.started_at ? new Date(s.started_at).toLocaleString() : '—'}
                    </td>
                    <td className="px-4 py-3 text-xs text-dark-300">
                      {s.completed_at ? new Date(s.completed_at).toLocaleString() : '—'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        to={ROUTES.SCAN_DETAILS_BY_ID(s.id)}
                        className="inline-flex items-center gap-1 text-xs text-primary-300 hover:text-primary-200"
                      >
                        View scan
                        <ArrowTopRightOnSquareIcon className="w-3.5 h-3.5" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Local helpers
// ---------------------------------------------------------------------------
const scanStatusVariantLocal = (status: string) => {
  switch (status) {
    case 'COMPLETED':
      return 'success' as const;
    case 'RUNNING':
    case 'QUEUED':
      return 'info' as const;
    case 'FAILED':
      return 'danger' as const;
    case 'CANCELLED':
      return 'neutral' as const;
    default:
      return 'neutral' as const;
  }
};

// ---------------------------------------------------------------------------
// Assets table with expandable metadata
// ---------------------------------------------------------------------------
const AssetsTable: React.FC<{ assets: Asset[] }> = ({ assets }) => {
  const [expandedId, setExpandedId] = useState<number | null>(null);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left">
        <thead className="bg-dark-950/60 border-b border-dark-800">
          <tr>
            <Th>Port</Th>
            <Th>Protocol</Th>
            <Th>Service</Th>
            <Th>Status</Th>
            <Th>IP Address</Th>
            <Th>First Seen</Th>
            <Th>Last Seen</Th>
            <Th>Scan</Th>
            <Th></Th>
          </tr>
        </thead>
        <tbody className="divide-y divide-dark-800/70">
          {assets.map(a => {
            const expanded = expandedId === a.id;
            const hasMetadata =
              a.metadata && Object.keys(a.metadata).length > 0;
            return (
              <React.Fragment key={a.id}>
                <tr className="hover:bg-primary-500/[0.04] transition-colors">
                  <td className="px-4 py-3 text-sm text-dark-100 font-mono">
                    {a.port != null ? a.port : '—'}
                  </td>
                  <td className="px-4 py-3 text-sm text-dark-300">
                    {a.protocol || '—'}
                  </td>
                  <td className="px-4 py-3">
                    {a.service ? (
                      <Badge variant="info" noDot>
                        {a.service}
                      </Badge>
                    ) : (
                      <span className="text-dark-500 text-sm">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {a.status ? (
                      <Badge
                        variant={
                          a.status === 'open' || a.status === 'up'
                            ? 'success'
                            : 'neutral'
                        }
                        noDot
                      >
                        {a.status}
                      </Badge>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-dark-300 font-mono">
                    {a.ip_address || '—'}
                  </td>
                  <td className="px-4 py-3 text-xs text-dark-400">
                    {fmtDate(a.first_seen)}
                  </td>
                  <td className="px-4 py-3 text-xs text-dark-400">
                    {fmtDate(a.last_seen)}
                  </td>
                  <td className="px-4 py-3 text-xs text-dark-400 font-mono">
                    {a.scan_id ? (
                      <Link
                        to={ROUTES.SCAN_DETAILS_BY_ID(a.scan_id)}
                        className="text-primary-300 hover:text-primary-200"
                      >
                        #{a.scan_id}
                      </Link>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {hasMetadata && (
                      <button
                        onClick={() =>
                          setExpandedId(expanded ? null : a.id)
                        }
                        className="p-1 text-dark-400 hover:text-primary-300 hover:bg-dark-800 rounded-lg transition-all"
                        title="Toggle metadata"
                      >
                        {expanded ? (
                          <ChevronUpIcon className="w-4 h-4" />
                        ) : (
                          <ChevronDownIcon className="w-4 h-4" />
                        )}
                      </button>
                    )}
                  </td>
                </tr>
                {expanded && hasMetadata && (
                  <tr>
                    <td colSpan={9} className="px-4 py-3 bg-dark-900/40">
                      <div className="rounded-lg border border-dark-700 bg-dark-900/60 p-3">
                        <div className="text-[10px] uppercase tracking-wider text-dark-500 mb-2">
                          Metadata — Port {a.port ?? '—'} · {a.service || 'unknown service'}
                        </div>
                        <pre className="whitespace-pre-wrap break-all font-mono text-xs text-dark-300">
                          {JSON.stringify(a.metadata, null, 2)}
                        </pre>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Summary card
// ---------------------------------------------------------------------------
const SummaryCard: React.FC<{
  label: string;
  value: string;
  variant?: 'success' | 'info' | 'neutral';
}> = ({ label, value, variant = 'neutral' }) => {
  const colorMap: Record<string, string> = {
    success: 'text-green-400 border-green-500/20 bg-green-500/5',
    info: 'text-cyan-400 border-cyan-500/20 bg-cyan-500/5',
    neutral: 'text-dark-100 border-dark-700 bg-dark-900/40',
  };
  return (
    <div className={cn('rounded-lg border p-3', colorMap[variant])}>
      <div className="text-[10px] uppercase tracking-wider text-dark-500 mb-1">
        {label}
      </div>
      <div className="text-sm break-all">{value}</div>
    </div>
  );
};
