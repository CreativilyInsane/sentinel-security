// frontend/src/pages/Assets.tsx
import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  MagnifyingGlassIcon,
  ServerStackIcon,
  ArrowRightIcon,
  EyeIcon,
} from '@heroicons/react/24/outline';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Spinner } from '@/components/ui/Spinner';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { useAssets, useDeleteAsset } from '@/hooks/useRecon';
import { useToast } from '@/context/ToastContext';
import { ROUTES } from '@/routes/paths';
import { cn } from '@/utils/cn';
import type { Asset } from '@/types/recon.types';

// ---------------------------------------------------------------------------
// Grouped host type
// ---------------------------------------------------------------------------
interface HostGroup {
  host: string;
  ip: string;
  hostname: string;
  assets: Asset[];
  lastSeen: string;
  firstSeen: string;
  ownershipTypes: Set<string>;
  clientNames: Set<string>;
  canDeleteAny: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const fmtDate = (iso: string): string => {
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
};

const ownershipLabel = (t?: string): string => {
  switch (t) {
    case 'CLIENT': return 'Client';
    case 'ASSIGNED_TARGET': return 'Assigned Target';
    case 'USER_MANUAL':
    default:
      return 'My Scan';
  }
};

const ownershipVariant = (t?: string): 'info' | 'primary' | 'neutral' => {
  switch (t) {
    case 'CLIENT': return 'info';
    case 'ASSIGNED_TARGET': return 'primary';
    default: return 'neutral';
  }
};

const Th: React.FC<{ children?: React.ReactNode; className?: string }> = ({
  children,
  className = '',
}) => (
  <th className={cn('px-4 py-3 text-xs font-semibold text-dark-400 uppercase tracking-wider', className)}>
    {children}
  </th>
);

// ---------------------------------------------------------------------------
// Main Assets page
// ---------------------------------------------------------------------------
export const Assets: React.FC = () => {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [search, setSearch] = useState('');
  const [deleteAsset, setDeleteAsset] = useState<Asset | null>(null);
  const deleteAssetMut = useDeleteAsset();

  const { data, isLoading, isFetching } = useAssets({
    skip: 0,
    limit: 500,
    host: search || undefined,
  });

  // Group assets by host+ip
  const groupedAssets = useMemo(() => {
    if (!data) return [];
    const map = new Map<string, HostGroup>();
    for (const a of data) {
      const key = `${a.host}|${a.ip_address || ''}`;
      const existing = map.get(key);
      if (existing) {
        existing.assets.push(a);
        if (a.last_seen > existing.lastSeen) existing.lastSeen = a.last_seen;
        if (a.first_seen < existing.firstSeen) existing.firstSeen = a.first_seen;
        if (a.ownership_type) existing.ownershipTypes.add(a.ownership_type);
        if (a.client_name) existing.clientNames.add(a.client_name);
        if (a.can_delete) existing.canDeleteAny = true;
      } else {
        map.set(key, {
          host: a.host,
          ip: a.ip_address || '—',
          hostname: a.hostname || '',
          assets: [a],
          lastSeen: a.last_seen,
          firstSeen: a.first_seen,
          ownershipTypes: new Set(a.ownership_type ? [a.ownership_type] : []),
          clientNames: new Set(a.client_name ? [a.client_name] : []),
          canDeleteAny: !!a.can_delete,
        });
      }
    }
    return Array.from(map.values()).sort((a, b) => b.lastSeen.localeCompare(a.lastSeen));
  }, [data]);

  const filteredGroups = useMemo(() => {
    if (!search) return groupedAssets;
    const q = search.toLowerCase();
    return groupedGroups_filter(groupedAssets, q);
  }, [groupedAssets, search]);

  const onOpenHost = (g: HostGroup) => {
    navigate(ROUTES.ASSETS_BY_HOST_VALUE(g.host));
  };

  const onDeleteAsset = async () => {
    if (!deleteAsset) return;
    try {
      await deleteAssetMut.mutateAsync(deleteAsset.id);
      showToast('Asset deleted.', 'success');
    } catch (err: any) {
      showToast(err?.response?.data?.message || 'Failed to delete asset.', 'error');
    } finally {
      setDeleteAsset(null);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-display font-bold text-dark-50">Assets</h1>
        <p className="text-dark-400 mt-1">
          Persistent inventory of hosts discovered across all your scans. The Source column shows
          where each asset came from — Client / Assigned Target assets cannot be deleted by users;
          only My Scan assets can.
        </p>
      </div>

      <div className="glass-panel rounded-xl p-4">
        <Input
          id="search"
          placeholder="Search by host, IP, or hostname..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          icon={<MagnifyingGlassIcon className="w-4 h-4" />}
        />
      </div>

      <div className="glass-panel border-glow-top rounded-xl overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center py-12"><Spinner className="w-7 h-7" /></div>
        ) : filteredGroups.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-dark-400">
            <ServerStackIcon className="w-10 h-10 mb-3 text-dark-600" />
            <p className="text-sm">No assets discovered yet.</p>
            <p className="text-xs mt-1">Run a scan to populate the inventory.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-dark-950/60 border-b border-dark-800">
                <tr>
                  <Th>Host</Th>
                  <Th>IP Address</Th>
                  <Th>Ports</Th>
                  <Th>Top Open Ports</Th>
                  <Th>Source</Th>
                  <Th>Client</Th>
                  <Th>Status</Th>
                  <Th>Last Seen</Th>
                  <Th className="text-right">Actions</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-800/70">
                {filteredGroups.map(g => {
                  const portAssets = g.assets.filter(a => a.port != null);
                  const openPortAssets = g.assets.filter(
                    a => a.port != null && (a.status === 'open' || a.status === 'up'),
                  );
                  const topOpenPorts = openPortAssets.map(a => a.port as number).sort((a, b) => a - b).slice(0, 8);
                  const hiddenPortsCount = Math.max(0, openPortAssets.length - topOpenPorts.length);
                  const statuses = new Set(g.assets.map(a => a.status).filter(Boolean));
                  const hasOpen = statuses.has('open') || statuses.has('up');
                  return (
                    <tr
                      key={`${g.host}|${g.ip}`}
                      className="hover:bg-primary-500/[0.04] transition-colors cursor-pointer"
                      onClick={() => onOpenHost(g)}
                    >
                      <td className="px-4 py-3">
                        <div className="flex flex-col">
                          <span className="text-sm text-dark-100 font-mono">{g.host}</span>
                          {g.hostname && <span className="text-xs text-dark-500">{g.hostname}</span>}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-dark-300 font-mono">{g.ip}</td>
                      <td className="px-4 py-3">
                        <Badge variant="info" noDot>{portAssets.length}</Badge>
                        <span className="text-xs text-dark-500 ml-1">({openPortAssets.length} open)</span>
                      </td>
                      <td className="px-4 py-3">
                        {topOpenPorts.length > 0 ? (
                          <div className="flex flex-wrap gap-1 max-w-md">
                            {topOpenPorts.map(p => (
                              <span key={p} className="inline-flex items-center justify-center min-w-[2.25rem] px-1.5 py-0.5 text-[10px] font-mono rounded border border-green-500/30 bg-green-500/10 text-green-300">
                                {p}
                              </span>
                            ))}
                            {hiddenPortsCount > 0 && (
                              <span className="text-[10px] text-dark-500 self-center">+{hiddenPortsCount} more</span>
                            )}
                          </div>
                        ) : (
                          <span className="text-dark-500 text-xs">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1">
                          {Array.from(g.ownershipTypes).map(t => (
                            <Badge key={t} variant={ownershipVariant(t)} noDot>
                              {ownershipLabel(t)}
                            </Badge>
                          ))}
                          {g.ownershipTypes.size === 0 && (
                            <Badge variant="neutral" noDot>My Scan</Badge>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs text-dark-300">
                        {g.clientNames.size > 0 ? Array.from(g.clientNames).join(', ') : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={hasOpen ? 'success' : 'neutral'} noDot>
                          {hasOpen ? 'Open' : 'Closed'}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-xs text-dark-400">{fmtDate(g.lastSeen)}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            type="button"
                            onClick={e => { e.stopPropagation(); onOpenHost(g); }}
                            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-dark-800 border border-dark-700 hover:border-primary-500/50 text-xs text-dark-100 hover:text-primary-300 transition-all"
                            title="View asset details"
                          >
                            <EyeIcon className="w-3.5 h-3.5" />
                            View
                            <ArrowRightIcon className="w-3 h-3" />
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

      {filteredGroups.length > 0 && (
        <p className="text-xs text-dark-500">
          Showing {filteredGroups.length} host(s). Click any row to view all ports and services.
        </p>
      )}

      <ConfirmDialog
        isOpen={!!deleteAsset}
        title="Delete Asset"
        message={`Delete asset '${deleteAsset?.host}:${deleteAsset?.port ?? '—'}'? This cannot be undone.`}
        confirmLabel="Delete"
        cancelLabel="Cancel"
        isLoading={deleteAssetMut.isPending}
        onConfirm={onDeleteAsset}
        onCancel={() => setDeleteAsset(null)}
      />
    </div>
  );
};

// Separated filter helper to keep the main component body tidy.
function groupedGroups_filter(groups: HostGroup[], q: string): HostGroup[] {
  return groups.filter(
    g =>
      g.host.toLowerCase().includes(q) ||
      g.ip.toLowerCase().includes(q) ||
      g.hostname.toLowerCase().includes(q),
  );
}
