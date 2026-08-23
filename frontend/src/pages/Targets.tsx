// frontend/src/pages/Targets.tsx
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import {
  BellIcon,
  BuildingOffice2Icon,
  SignalIcon,
  ArrowRightIcon,
  CheckIcon,
  ClockIcon,
  EyeIcon,
  EyeSlashIcon,
  DocumentTextIcon,
} from '@heroicons/react/24/outline';
import { Badge } from '@/components/ui/Badge';
import { Spinner } from '@/components/ui/Spinner';
import { Button } from '@/components/ui/Button';
import { useToast } from '@/context/ToastContext';
import {
  useMyClients, useMyNotifications,
  useUnreadCount, useMarkNotificationsRead,
  useActiveTargets, useToggleActiveTarget,
} from '@/hooks/useClients';
import { clientsApi } from '@/api/clients.api';
import { ROUTES } from '@/routes/paths';
import { cn } from '@/utils/cn';
import type { AssignmentNotification } from '@/types/client.types';

const fmtDate = (iso: string): string => {
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
};

const notificationTypeLabel = (t: string): string => {
  switch (t) {
    case 'CLIENT_ASSIGNED': return 'Client Assigned';
    case 'TARGET_ASSIGNED': return 'Target Assigned';
    case 'TARGET_REMOVED': return 'Target Removed';
    case 'CLIENT_REMOVED': return 'Client Removed';
    default: return t;
  }
};

const notificationTypeVariant = (t: string): 'success' | 'info' | 'danger' | 'warning' => {
  switch (t) {
    case 'CLIENT_ASSIGNED':
    case 'TARGET_ASSIGNED':
      return 'success';
    case 'CLIENT_REMOVED':
    case 'TARGET_REMOVED':
      return 'danger';
    default:
      return 'info';
  }
};

// ---------------------------------------------------------------------------
// Toggle switch component (matches UserModuleSettings)
// ---------------------------------------------------------------------------
const Toggle: React.FC<{ enabled: boolean; onClick: () => void; disabled?: boolean; busy?: boolean }> = ({ enabled, onClick, disabled, busy }) => (
  <button
    type="button"
    role="switch"
    aria-checked={enabled}
    disabled={disabled || busy}
    onClick={onClick}
    className={cn(
      'relative inline-flex items-center h-6 w-11 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500/60 focus:ring-offset-2 focus:ring-offset-dark-900',
      enabled ? 'bg-primary-500' : 'bg-dark-700',
      (disabled || busy) && 'opacity-50 cursor-not-allowed',
    )}
  >
    <span
      className={cn(
        'inline-block w-4 h-4 bg-white rounded-full shadow transform transition-transform',
        enabled ? 'translate-x-6' : 'translate-x-1',
      )}
    />
  </button>
);

export const Targets: React.FC = () => {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { showToast } = useToast();
  const myClients = useMyClients();
  const myNotifs = useMyNotifications(false);
  const unreadQuery = useUnreadCount();
  const markRead = useMarkNotificationsRead();
  const activeTargetsQ = useActiveTargets();
  const toggleTargetMut = useToggleActiveTarget();

  // Phase 19 — local in-flight toggle state to show a spinner while the
  // per-client / per-asset toggle mutation is in flight.
  const [togglingClientId, setTogglingClientId] = useState<number | null>(null);
  const [togglingAssetId, setTogglingAssetId] = useState<number | null>(null);

  // Auto-mark all unread notifications as read after a short delay when the
  // page is opened.  The user has "seen" them by visiting this page.
  useEffect(() => {
    if ((unreadQuery.data || 0) > 0) {
      const t = setTimeout(() => {
        markRead.mutate(undefined, {
          onSuccess: () => showToast('Notifications marked as read.', 'info'),
        });
      }, 1500);
      return () => clearTimeout(t);
    }
  }, [unreadQuery.data]);

  // Defensive: guarantee we always render arrays even if the cache ever
  // holds an unexpected shape (prevents "clients.map is not a function"
  // crashes that blank the whole page).
  const notifications = Array.isArray(myNotifs.data) ? myNotifs.data : [];
  const clients = Array.isArray(myClients.data) ? myClients.data : [];

  // Build a set of active target keys from the user's selections.
  // If the user has never toggled any targets (activeTargets is empty),
  // all targets are considered active by default.
  const activeKeys = new Set(
    (activeTargetsQ.data || [])
      .filter(r => r.is_active)
      .map(r => r.target_key),
  );
  const hasToggles = (activeTargetsQ.data || []).length > 0;

  const isTargetActive = (assignmentId: number | null | undefined, targetValue: string): boolean => {
    if (!assignmentId) return false;
    if (!hasToggles) return true; // default: all active
    return activeKeys.has(`${assignmentId}:${targetValue}`);
  };

  const handleToggle = async (assignmentId: number, targetValue: string, currentlyActive: boolean) => {
    try {
      await toggleTargetMut.mutateAsync({
        assignmentId, targetValue, isActive: !currentlyActive,
      });
      showToast(`Target ${!currentlyActive ? 'activated' : 'deactivated'}.`, 'success');
    } catch (err: any) {
      showToast(err?.response?.data?.message || 'Failed to toggle target.', 'error');
    }
  };

  // -----------------------------------------------------------------
  // Phase 19 — per-user client/asset permission toggles.
  //
  // These are independent of the active-target toggle above (which
  // only controls scan-dropdown visibility).  The new toggles update
  // the user_client_permissions and user_asset_permissions tables,
  // which are enforced by TargetAuthorizationService on every scan.
  //
  // IMPORTANT: the ['my-clients'] query caches a plain ARRAY.  The
  // optimistic update must write back an array of the same shape —
  // wrapping it in { data: [...] } used to corrupt the cache and crash
  // the page (clients.map is not a function).
  // -----------------------------------------------------------------
  const handleClientToggle = async (clientId: number, currentlyEnabled: boolean) => {
    setTogglingClientId(clientId);
    const prev = qc.getQueryData<any[]>(['my-clients']);

    // Optimistic update: flip the enabled flag locally before the request
    // resolves, so the UI reflects the user's intent immediately.  If the
    // request fails, we roll back via `setQueryData` using `prev`.
    if (Array.isArray(prev)) {
      qc.setQueryData(
        ['my-clients'],
        prev.map(c => (c.id === clientId ? { ...c, enabled: !currentlyEnabled } : c)),
      );
    }

    try {
      await clientsApi.toggleClientPermission(clientId, !currentlyEnabled);
      // Invalidate the my-clients + my-targets queries so they refetch
      // with the latest server state.
      await qc.invalidateQueries({ queryKey: ['my-clients'] });
      await qc.invalidateQueries({ queryKey: ['my-targets'] });
      showToast(`Client ${!currentlyEnabled ? 'enabled' : 'disabled'} for your account.`, 'success');
    } catch (err: any) {
      // Roll back the optimistic update on error.
      if (Array.isArray(prev)) qc.setQueryData(['my-clients'], prev);
      const msg = err?.response?.data?.message || 'Failed to toggle client access.';
      showToast(msg, 'error');
    } finally {
      setTogglingClientId(null);
    }
  };

  const handleAssetToggle = async (assetId: number, currentlyEnabled: boolean) => {
    setTogglingAssetId(assetId);
    const prev = qc.getQueryData<any[]>(['my-clients']);

    // Optimistic update: flip the asset's enabled flag locally
    // (array in, array out — never wrap in { data: ... }).
    if (Array.isArray(prev)) {
      qc.setQueryData(
        ['my-clients'],
        prev.map(c => ({
          ...c,
          assets: (c.assets || []).map((a: any) =>
            a.id === assetId ? { ...a, enabled: !currentlyEnabled } : a,
          ),
        })),
      );
    }

    try {
      await clientsApi.toggleAssetPermission(assetId, !currentlyEnabled);
      await qc.invalidateQueries({ queryKey: ['my-clients'] });
      await qc.invalidateQueries({ queryKey: ['my-targets'] });
      showToast(`Asset ${!currentlyEnabled ? 'enabled' : 'disabled'} for your account.`, 'success');
    } catch (err: any) {
      // Roll back the optimistic update on error.
      if (Array.isArray(prev)) qc.setQueryData(['my-clients'], prev);
      const msg = err?.response?.data?.message || 'Failed to toggle asset access.';
      showToast(msg, 'error');
    } finally {
      setTogglingAssetId(null);
    }
  };

  // -----------------------------------------------------------------
  // Phase 19 — fetch the client HTML report via axios (Bearer token
  // attached automatically) instead of window.open() with the raw URL.
  // The raw-URL approach caused a 401 "Not authenticated" error
  // because the browser cannot attach the JWT to a top-level
  // navigation request.
  // -----------------------------------------------------------------
  const handleViewClientReport = async (clientId: number) => {
    try {
      const blob = await clientsApi.fetchClientReportHtml(clientId);
      const url = window.URL.createObjectURL(new Blob([blob], { type: 'text/html' }));
      window.open(url, '_blank');
    } catch (err: any) {
      const msg = err?.response?.data?.message || 'Failed to load HTML report.';
      showToast(msg, 'error');
    }
  };

  const isLoading = myClients.isLoading || myNotifs.isLoading;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Spinner className="w-8 h-8" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-display font-bold text-dark-50">Targets</h1>
        <p className="text-dark-400 mt-1">
          Clients and direct IP/CIDR targets assigned to you by an administrator.
          Select them in Network Scan to perform authorised scans.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main column */}
        <div className="lg:col-span-2 space-y-6">
          {/* Assigned Clients — now with per-client + per-asset
              enable/disable toggles (Phase 19). */}
          <section className="glass-panel border-glow-top rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-dark-800 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-primary-400 shadow-glow-sm" />
              <h2 className="text-base font-display font-semibold text-dark-50">Assigned Clients</h2>
              <span className="text-xs text-dark-500">({clients.length})</span>
            </div>
            {clients.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-dark-400">
                <BuildingOffice2Icon className="w-10 h-10 mb-3 text-dark-600" />
                <p className="text-sm">No clients assigned to you yet.</p>
              </div>
            ) : (
              <div className="divide-y divide-dark-800/70">
                {clients.map(c => {
                  // Per-user client enabled flag (default-open: missing
                  // row is treated as enabled=true).
                  const clientEnabled = c.enabled !== false;
                  // c.id is null for the synthetic "Direct Targets"
                  // pseudo-client (orphan direct-target assignments).
                  const isPseudo = c.id === null;
                  // Defensive: assets may be missing on malformed rows.
                  const clientAssets = Array.isArray(c.assets) ? c.assets : [];
                  return (
                  <div key={c.id ?? `pseudo-${c.name}`} className="p-5 hover:bg-primary-500/[0.04] transition-colors">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="text-base font-display font-semibold text-dark-50">{c.name}</h3>
                          <Badge variant="info" noDot>{clientAssets.length} asset{clientAssets.length === 1 ? '' : 's'}</Badge>
                          {c.company_name && (
                            <span className="text-xs text-dark-500">{c.company_name}</span>
                          )}
                          {/* Phase 19 — client ON/OFF status badge */}
                          <Badge variant={clientEnabled ? 'success' : 'neutral'} noDot>
                            {clientEnabled ? 'ON' : 'OFF'}
                          </Badge>
                          {isPseudo && (
                            <Badge variant="warning" noDot>orphan</Badge>
                          )}
                        </div>
                        {c.description && (
                          <p className="text-sm text-dark-400 mt-1">{c.description}</p>
                        )}
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        {/* Phase 19 — per-client toggle.  Disabling the
                            parent client cascades to disable all of the
                            user's per-asset permissions for this client
                            (enforced server-side).  Hidden for the
                            synthetic pseudo-client (no real client_id). */}
                        {!isPseudo && (
                          <div className="flex items-center gap-2">
                            <span className={cn(
                              'text-xs font-medium',
                              clientEnabled ? 'text-primary-300' : 'text-dark-500',
                            )}>
                              {clientEnabled ? 'ON' : 'OFF'}
                            </span>
                            <Toggle
                              enabled={clientEnabled}
                              onClick={() => handleClientToggle(c.id as number, clientEnabled)}
                              busy={togglingClientId === c.id}
                            />
                          </div>
                        )}
                        {!isPseudo && (
                          <button
                            onClick={() => handleViewClientReport(c.id as number)}
                            className="text-xs text-primary-300 hover:text-primary-200 inline-flex items-center gap-1"
                          >
                            <DocumentTextIcon className="w-3.5 h-3.5" />
                            View Client Report
                          </button>
                        )}
                      </div>
                    </div>
                    {/* Asset chips — now include per-asset toggle. */}
                    <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {clientAssets.map(a => {
                        const badgeVariant = a.asset_type === 'IP' ? 'info' : a.asset_type === 'IP_RANGE' ? 'primary' : 'neutral';
                        const badgeLabel = a.asset_type === 'IP' ? 'IP' : a.asset_type === 'IP_RANGE' ? 'CIDR' : 'DOMAIN';
                        // Use the assignment_id returned directly by
                        // the merged my-clients response — no need to
                        // cross-reference the my-targets list anymore.
                        const assignmentId = a.assignment_id ?? null;
                        const isActive = isTargetActive(assignmentId, a.value);
                        // Phase 19 — per-user asset enabled flag.
                        const assetEnabled = a.enabled !== false;
                        const parentDisabled = isPseudo ? false : !clientEnabled;
                        const effectivelyEnabled = assetEnabled && (isPseudo || clientEnabled);
                        // The per-asset permission toggle requires a
                        // real ClientAsset row (asset_id).  Synthetic
                        // ad-hoc direct-target assets (id === null) cannot
                        // be toggled because no user_asset_permissions
                        // row can reference them.
                        const canToggleAssetPermission = a.id !== null;
                        return (
                        <div
                          key={`${a.id ?? 'synthetic'}-${a.value}-${assignmentId ?? 'no-asg'}`}
                          className={cn(
                            'flex items-center gap-2 rounded-lg border p-2 transition-colors',
                            effectivelyEnabled
                              ? 'border-primary-500/30 bg-primary-500/5'
                              : 'border-dark-700 bg-dark-900/40 opacity-70',
                          )}
                        >
                          <Badge variant={badgeVariant} noDot>
                            {badgeLabel}
                          </Badge>
                          <div className="flex-1 min-w-0">
                            <div className="text-xs font-mono text-dark-100 truncate">
                              {a.value}
                            </div>
                            {a.name && (
                              <div className="text-[10px] text-dark-500 truncate">{a.name}</div>
                            )}
                          </div>
                          {/* "Assigned via" badge — distinguishes a
                              full-client asset (CLIENT) from a directly
                              assigned asset (DIRECT_TARGET). */}
                          {a.assigned_via === 'DIRECT_TARGET' && (
                            <Badge variant="primary" noDot>Direct</Badge>
                          )}
                          {assignmentId !== null && assignmentId !== undefined && (
                            <button
                              onClick={() => handleToggle(assignmentId, a.value, isActive)}
                              className={cn(
                                'p-1 rounded-lg transition-all shrink-0',
                                isActive
                                  ? 'text-primary-300 hover:bg-primary-500/20'
                                  : 'text-dark-500 hover:bg-dark-800',
                              )}
                              title={isActive ? 'Hide from Network Scan dropdown' : 'Show in Network Scan dropdown'}
                            >
                              {isActive ? <EyeIcon className="w-4 h-4" /> : <EyeSlashIcon className="w-4 h-4" />}
                            </button>
                          )}
                          {/* Phase 19 — per-asset permission toggle.
                              Disabled when the parent client is OFF
                              (non-pseudo) or when the asset is synthetic
                              (no real ClientAsset row to attach the
                              permission to). */}
                          <div className="flex items-center gap-1 shrink-0">
                            <span className={cn(
                              'text-[10px] font-medium',
                              assetEnabled ? 'text-primary-300' : 'text-dark-500',
                            )}>
                              {assetEnabled ? 'ON' : 'OFF'}
                            </span>
                            <Toggle
                              enabled={assetEnabled}
                              onClick={() => canToggleAssetPermission && handleAssetToggle(a.id as number, assetEnabled)}
                              disabled={parentDisabled || !canToggleAssetPermission}
                              busy={canToggleAssetPermission && togglingAssetId === a.id}
                            />
                          </div>
                        </div>
                        );
                      })}
                    </div>
                  </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>

        {/* Sidebar column — notifications */}
        <div className="space-y-4">
          <section className="glass-panel border-glow-top rounded-xl overflow-hidden sticky top-4">
            <div className="px-5 py-4 border-b border-dark-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <BellIcon className="w-5 h-5 text-primary-300" />
                <h2 className="text-sm font-display font-semibold text-dark-50">New Assignments</h2>
              </div>
              {(unreadQuery.data || 0) > 0 && (
                <Badge variant="primary" noDot>{unreadQuery.data} new</Badge>
              )}
            </div>
            {notifications.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-10 text-dark-400">
                <CheckIcon className="w-8 h-8 mb-2 text-dark-600" />
                <p className="text-xs">You're all caught up.</p>
              </div>
            ) : (
              <div className="divide-y divide-dark-800/70 max-h-[420px] overflow-y-auto">
                {notifications.slice(0, 20).map(n => (
                  <NotificationRow key={n.id} n={n} />
                ))}
              </div>
            )}
          </section>

          {/* Quick link to Network Scan */}
          <div className="glass-panel rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <SignalIcon className="w-5 h-5 text-primary-300" />
              <h3 className="text-sm font-display font-semibold text-dark-50">Ready to scan?</h3>
            </div>
            <p className="text-xs text-dark-400 mb-3">
              Select your assigned targets from the dropdown on the Network Scan page.
            </p>
            <Button size="sm" fullWidth onClick={() => navigate(ROUTES.NETWORK_SCAN)}>
              Go to Network Scan
              <ArrowRightIcon className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

const NotificationRow: React.FC<{ n: AssignmentNotification }> = ({ n }) => (
  <div className={cn('p-3', !n.is_read && 'bg-primary-500/[0.04]')}>
    <div className="flex items-center gap-2 mb-1">
      <Badge variant={notificationTypeVariant(n.type)} noDot>
        {notificationTypeLabel(n.type)}
      </Badge>
      {!n.is_read && (
        <span className="w-1.5 h-1.5 rounded-full bg-primary-400 animate-pulse-glow" />
      )}
    </div>
    {n.message && <p className="text-xs text-dark-200">{n.message}</p>}
    <div className="text-[10px] text-dark-500 mt-1 flex items-center gap-1">
      <ClockIcon className="w-3 h-3" />
      {fmtDate(n.created_at)}
    </div>
  </div>
);