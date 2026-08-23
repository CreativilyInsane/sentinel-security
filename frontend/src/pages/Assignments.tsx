// frontend/src/pages/Assignments.tsx
//
// Dedicated Admin-only Assignments page.
//
// This is the single source of truth for managing target assignments
// (full-Client assignments AND direct-target assignments).  The page
// exposes two assignment modes plus a table of existing assignments
// with the ability to enable / disable / remove each row.
//
// IMPORTANT distinction (per the Sentinel Security change request):
//
//   * ENABLED/DISABLED  →  The assignment still exists, but the user
//                          cannot currently use it.  Toggleable from
//                          the user's Targets page too.
//
//   * REMOVED           →  The assignment is deleted from the DB.  Only
//                          Admin can remove assignments, and only from
//                          this page.
//
// Both assignment modes require an Admin to also pick a Client as the
// organising context — this guarantees every direct target is grouped
// under its owning Client in the user's Targets view, never under a
// separate "Direct Targets" top-level section.
import React, { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  UserPlusIcon,
  PlusIcon,
  TrashIcon,
  CheckIcon,
  XMarkIcon,
  ArrowPathIcon,
  ClipboardDocumentCheckIcon,
} from '@heroicons/react/24/outline';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { Input } from '@/components/ui/Input';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { useToast } from '@/context/ToastContext';
import { useUsers } from '@/hooks/useUsers';
import {
  useClients, useClientAssets,
  useAssignments, useAssignClient, useAssignDirectTarget,
  useUpdateAssignment, useDeleteAssignment,
} from '@/hooks/useClients';
import { cn } from '@/utils/cn';
import type {
  TargetAssignment, AssignClientPayload, AssignDirectTargetPayload,
  AssignmentUpdatePayload, ClientAssetType,
} from '@/types/client.types';

type AssignMode = 'CLIENT' | 'DIRECT_TARGET';

const fmtDate = (iso?: string | null): string => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return String(iso); }
};

const Th: React.FC<{ children?: React.ReactNode; className?: string }> = ({ children, className = '' }) => (
  <th className={cn('px-4 py-3 text-xs font-semibold text-dark-400 uppercase tracking-wider', className)}>{children}</th>
);

export const Assignments: React.FC = () => {
  const { showToast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  // Deep-link filter: ?client_id=N narrows the existing-assignments table
  // to one client and pre-selects that client in the new-assignment form.
  // Used by the "Manage in Assignments" button on the Client Detail page.
  const initialClientId = searchParams.get('client_id');

  // ---- Data queries ----
  const { data: users, isLoading: usersLoading } = useUsers();
  const { data: clients, isLoading: clientsLoading } = useClients({ limit: 500 });
  const { data: assignments, isLoading: assignmentsLoading, refetch: refetchAssignments } = useAssignments(
    initialClientId ? { client_id: Number(initialClientId), limit: 500 } : { limit: 500 },
  );

  // Mutations
  const assignClientMut = useAssignClient();
  const assignDirectMut = useAssignDirectTarget();
  const updateMut = useUpdateAssignment();
  const deleteMut = useDeleteAssignment();

  // Regular users only (admins cannot be assigned targets)
  const regularUsers = useMemo(
    () => (users || []).filter(u => u.role?.name !== 'Administrator' && u.is_active),
    [users],
  );

  // ---- Form state ----
  const [mode, setMode] = useState<AssignMode>('CLIENT');
  const [selUserId, setSelUserId] = useState<number | ''>('');
  const [selClientId, setSelClientId] = useState<number | ''>(
    initialClientId ? Number(initialClientId) : '',
  );
  const [selAssetId, setSelAssetId] = useState<number | ''>('');
  const [targetType, setTargetType] = useState<ClientAssetType>('IP');
  const [targetValue, setTargetValue] = useState('');
  const [targetLabel, setTargetLabel] = useState('');
  const [showConfirmRemove, setShowConfirmRemove] = useState<TargetAssignment | null>(null);
  // Per-row "saving" indicator for enable/disable/remove actions so the
  // user gets immediate feedback when they click an action button.
  const [busyRowId, setBusyRowId] = useState<number | null>(null);

  // ---- Validation rules for Direct Target mode ----
  const hasUser = !!selUserId;
  const hasClientAndAsset = !!selClientId && !!selAssetId;
  const hasTypeAndValue = !!targetType && !!targetValue.trim();
  // User is required, PLUS either (Client + Asset) OR (Type + Value)
  const isValidDirectTarget = hasUser && (hasClientAndAsset || hasTypeAndValue);

  // When the deep-link ?client_id= changes (e.g. user navigates here from
  // the Client Detail page), pre-select that client in the form and
  // refresh the assignments query.  This is a no-op if the param is
  // already set to the same value.
  useEffect(() => {
    if (initialClientId) {
      setSelClientId(Number(initialClientId));
    }
  }, [initialClientId]);

  // Clear the deep-link filter so subsequent manual client changes
  // aren't pinned to the deep-link value.
  const handleClientSelect = (v: number | '') => {
    setSelClientId(v);
    setSelAssetId('');
    setTargetValue('');
    if (initialClientId) {
      // Drop ?client_id= from the URL so the assignments list returns to
      // unfiltered mode the next time the user resets the form.
      setSearchParams({});
    }
  };

  // Fetch the selected client's assets (for the direct-target mode's
  // asset dropdown).
  const { data: selectedClientAssets, isLoading: assetsLoading } = useClientAssets(
    selClientId ? Number(selClientId) : null,
  );

  const handleModeSwitch = (m: AssignMode) => {
    setMode(m);
    setSelAssetId('');
    setTargetValue('');
    setTargetLabel('');
  };

  const resetForm = () => {
    setSelUserId('');
    setSelClientId('');
    setSelAssetId('');
    setTargetValue('');
    setTargetLabel('');
    setTargetType('IP');
  };

  // ---- Submit handlers ----
  const handleAssignClient = async () => {
    if (!selUserId || !selClientId) {
      showToast('Please select both a user and a client.', 'info');
      return;
    }
    const payload: AssignClientPayload = {
      user_id: Number(selUserId),
      client_id: Number(selClientId),
    };
    try {
      await assignClientMut.mutateAsync(payload);
      showToast('Client assigned to user.', 'success');
      resetForm();
    } catch (err: any) {
      showToast(err?.response?.data?.message || 'Failed to assign client.', 'error');
    }
  };

  const handleAssignDirectTarget = async () => {
    if (!selUserId) {
    showToast('Please select a user.', 'info');
    return;
    }

    let finalType: 'IP' | 'IP_RANGE' | 'DOMAIN' = targetType;
    let finalValue = targetValue.trim();
    let finalAssetId: number | null = selAssetId ? Number(selAssetId) : null;
    let finalClientId: number | null = selClientId ? Number(selClientId) : null;

    // COMBO 1: Client + Existing Asset
    if (selAssetId) {
      const asset = (selectedClientAssets || []).find(a => a.id === Number(selAssetId));
      if (!asset) {
        showToast('Selected asset no longer exists.', 'error');
        return;
      }
      finalType = asset.asset_type as 'IP' | 'IP_RANGE' | 'DOMAIN';
      finalValue = asset.ip_address || asset.cidr || asset.domain || '';
    }
    // COMBO 2: Direct Target Type + Value (Manual)
    else if (finalValue) {
      // If no client is selected, finalClientId will be null or optional based on your API spec
    }
    else {
      showToast('Please select an existing asset OR enter a target type and value.', 'info');
      return;
    }

    const payload: AssignDirectTargetPayload = {
      user_id: Number(selUserId),
      client_id: finalClientId,
      client_asset_id: finalAssetId,
      target_type: finalType,
      target_value: finalValue,
      target_label: targetLabel.trim() || null,
    };

    try {
      await assignDirectMut.mutateAsync(payload);
      showToast('Direct target assigned to user.', 'success');
      resetForm();
    } catch (err: any) {
      showToast(err?.response?.data?.message || 'Failed to assign direct target.', 'error');
    }
  };

  // ---- Row actions (enable / disable / remove) ----
  const handleToggleRow = async (a: TargetAssignment) => {
    setBusyRowId(a.id);
    const payload: AssignmentUpdatePayload = { is_active: !a.is_active };
    try {
      await updateMut.mutateAsync({ assignmentId: a.id, payload });
      showToast(`Assignment ${!a.is_active ? 'enabled' : 'disabled'}.`, 'success');
    } catch (err: any) {
      showToast(err?.response?.data?.message || 'Failed to update assignment.', 'error');
    } finally {
      setBusyRowId(null);
    }
  };

  const handleRemoveRow = async (a: TargetAssignment) => {
    setBusyRowId(a.id);
    try {
      await deleteMut.mutateAsync(a.id);
      showToast('Assignment removed.', 'info');
      setShowConfirmRemove(null);
    } catch (err: any) {
      showToast(err?.response?.data?.message || 'Failed to remove assignment.', 'error');
    } finally {
      setBusyRowId(null);
    }
  };

  const isLoading = usersLoading || clientsLoading || assignmentsLoading;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Spinner className="w-8 h-8" />
      </div>
    );
  }

  const assignmentList = assignments || [];

  // Header subtitle reflects the deep-link filter when present.
  const filteredClientName = initialClientId
    ? (clients || []).find(c => c.id === Number(initialClientId))?.name
    : null;
  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-display font-bold text-dark-50">Assignments</h1>
        {filteredClientName ? (
          <p className="text-dark-400 mt-1">
            Filtered to client <span className="text-primary-300 font-medium">{filteredClientName}</span>.{' '}
            <button
              onClick={() => setSearchParams({})}
              className="text-primary-300 hover:text-primary-200 underline"
            >
              Show all assignments
            </button>
          </p>
        ) : (
          <p className="text-dark-400 mt-1">
            Admin-only management of full-Client assignments and direct-target assignments.
            A direct target always appears under its owning Client in the user's Targets view.
          </p>
        )}
      </div>

      {/* Mode switcher + assignment form */}
      <section className="glass-panel border-glow-top rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-dark-800 flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-primary-400 shadow-glow-sm" />
          <h2 className="text-base font-display font-semibold text-dark-50">New Assignment</h2>
        </div>
        <div className="p-5 space-y-5">
          {/* Mode tabs */}
          <div className="flex gap-2 border-b border-dark-800">
            <button
              type="button"
              onClick={() => handleModeSwitch('CLIENT')}
              className={cn(
                'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
                mode === 'CLIENT'
                  ? 'border-primary-400 text-primary-300'
                  : 'border-transparent text-dark-400 hover:text-dark-100',
              )}
            >
              <UserPlusIcon className="w-4 h-4 inline mr-1" />
              Assign Client
            </button>
            <button
              type="button"
              onClick={() => handleModeSwitch('DIRECT_TARGET')}
              className={cn(
                'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
                mode === 'DIRECT_TARGET'
                  ? 'border-primary-400 text-primary-300'
                  : 'border-transparent text-dark-400 hover:text-dark-100',
              )}
            >
              <PlusIcon className="w-4 h-4 inline mr-1" />
              Assign Direct Target
            </button>
          </div>

          {/* Common fields: user + client */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-dark-400 mb-1">User</label>
              <select
                value={selUserId}
                onChange={e => setSelUserId(e.target.value ? Number(e.target.value) : '')}
                className="w-full bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-sm text-dark-100 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
              >
                <option value="">— Select a user —</option>
                {regularUsers.map(u => (
                  <option key={u.id} value={u.id}>
                    {u.username} ({u.email})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-dark-400 mb-1">Client</label>
              <select
                value={selClientId}
                onChange={e => handleClientSelect(e.target.value ? Number(e.target.value) : '')}
                className="w-full bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-sm text-dark-100 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
              >
                <option value="">— Select a client —</option>
                {(clients || []).filter(c => c.is_active).map(c => (
                  <option key={c.id} value={c.id}>
                    {c.name}{c.company_name ? ` — ${c.company_name}` : ''}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Mode-specific fields */}
          {mode === 'CLIENT' ? (
            <div className="rounded-lg border border-dark-700 bg-dark-900/40 p-4 text-sm text-dark-300">
              Assigning the entire Client gives the user access to all of its active assets.
              The user can selectively enable/disable individual assets from their Targets page.
            </div>
          ) : (
            <div className="space-y-4">
              <div className="rounded-lg border border-dark-700 bg-dark-900/40 p-4 space-y-3">
                <p className="text-xs text-dark-400">
                  Pick an existing asset from this Client, OR type a target value manually
                  (an ad-hoc IP / CIDR / Domain).  The target will appear under the selected
                  Client in the user's Targets view.
                </p>
                <div>
                  <label className="block text-xs font-semibold text-dark-400 mb-1">
                    Pick existing asset (optional)
                  </label>
                  <select
                    value={selAssetId}
                    onChange={e => {
                      const v = e.target.value ? Number(e.target.value) : '';
                      setSelAssetId(v);
                      // If user picks an asset, clear the manual value (asset takes precedence)
                      if (v) {
                        setTargetValue('');
                        setTargetLabel('');
                      }
                    }}
                    disabled={!selClientId || assetsLoading}
                    className="w-full bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-sm text-dark-100 focus:outline-none focus:ring-2 focus:ring-primary-500/50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <option value="">— Pick an existing asset (or use manual value below) —</option>
                    {(selectedClientAssets || []).filter(a => a.is_active).map(a => (
                      <option key={a.id} value={a.id}>
                        [{a.asset_type}] {a.ip_address || a.cidr || a.domain}
                        {a.name ? ` — ${a.name}` : ''}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-dark-400 mb-1">Target type</label>
                  <select
                    value={targetType}
                    onChange={e => setTargetType(e.target.value as ClientAssetType)}
                    disabled={!!selAssetId}
                    className="w-full bg-dark-900 border border-dark-700 rounded-lg px-3 py-2 text-sm text-dark-100 focus:outline-none focus:ring-2 focus:ring-primary-500/50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <option value="IP">IP</option>
                    <option value="IP_RANGE">CIDR / IP Range</option>
                    <option value="DOMAIN">Domain</option>
                  </select>
                </div>
                <div className="md:col-span-2">
                  <label className="block text-xs font-semibold text-dark-400 mb-1">
                    Target value {selAssetId ? '(disabled — asset picked above)' : '(manual)'}
                  </label>
                  <Input
                    type="text"
                    value={targetValue}
                    onChange={e => setTargetValue(e.target.value)}
                    placeholder={targetType === 'IP' ? 'e.g. 192.168.1.10' : targetType === 'IP_RANGE' ? 'e.g. 192.168.1.0/24' : 'e.g. example.com'}
                    disabled={!!selAssetId}
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-dark-400 mb-1">Label (optional)</label>
                <Input
                  type="text"
                  value={targetLabel}
                  onChange={e => setTargetLabel(e.target.value)}
                  placeholder="Human-friendly label e.g. 'Web Server'"
                />
              </div>
            </div>
          )}

          {/* Submit button */}
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={resetForm} disabled={assignClientMut.isPending || assignDirectMut.isPending}>
              Reset
            </Button>
            {mode === 'CLIENT' ? (
              <Button
                onClick={handleAssignClient}
                disabled={assignClientMut.isPending || !selUserId || !selClientId}
              >
                {assignClientMut.isPending ? (
                  <><ArrowPathIcon className="w-4 h-4 mr-1 animate-spin" /> Assigning…</>
                ) : (
                  <><UserPlusIcon className="w-4 h-4 mr-1" /> Assign Client</>
                )}
              </Button>
            ) : (
              <Button
                onClick={handleAssignDirectTarget}
                disabled={assignDirectMut.isPending || !isValidDirectTarget}
              >
                {assignDirectMut.isPending ? (
                  <><ArrowPathIcon className="w-4 h-4 mr-1 animate-spin" /> Assigning…</>
                ) : (
                  <><PlusIcon className="w-4 h-4 mr-1" /> Assign Target</>
                )}
              </Button>
            )}
          </div>
        </div>
      </section>

      {/* Existing assignments table */}
      <section className="glass-panel border-glow-top rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-dark-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-primary-400 shadow-glow-sm" />
            <h2 className="text-base font-display font-semibold text-dark-50">Existing Assignments</h2>
            <span className="text-xs text-dark-500">({assignmentList.length})</span>
          </div>
          <button
            onClick={() => refetchAssignments()}
            className="text-xs text-primary-300 hover:text-primary-200 inline-flex items-center gap-1"
            title="Refresh"
          >
            <ArrowPathIcon className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>
        {assignmentList.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-dark-400">
            <ClipboardDocumentCheckIcon className="w-10 h-10 mb-3 text-dark-600" />
            <p className="text-sm">No assignments yet. Use the form above to create one.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-dark-950/60 border-b border-dark-800">
                <tr>
                  <Th>User</Th>
                  <Th>Client</Th>
                  <Th>Asset / Target</Th>
                  <Th>Type</Th>
                  <Th>Status</Th>
                  <Th>Assigned By</Th>
                  <Th>Created</Th>
                  <Th className="text-right">Actions</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-800/70">
                {assignmentList.map(a => {
                  const isBusy = busyRowId === a.id;
                  const targetDisplay = a.assignment_type === 'CLIENT'
                    ? `(entire client) ${a.target_value}`
                    : (a.client_asset_name || a.target_value);
                  return (
                    <tr key={a.id} className={cn('hover:bg-primary-500/[0.04] transition-colors', !a.is_active && 'opacity-60')}>
                      <td className="px-4 py-3 text-sm text-dark-100">{a.user_username || `#${a.user_id}`}</td>
                      <td className="px-4 py-3 text-sm text-dark-300">{a.client_name || '—'}</td>
                      <td className="px-4 py-3 text-sm font-mono text-dark-100">{targetDisplay}</td>
                      <td className="px-4 py-3">
                        <Badge variant={a.assignment_type === 'CLIENT' ? 'info' : 'primary'} noDot>
                          {a.assignment_type === 'CLIENT' ? 'Full Client' : 'Direct Target'}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        {a.is_active ? (
                          <Badge variant="success" noDot><CheckIcon className="w-3 h-3 inline mr-0.5" />ON</Badge>
                        ) : (
                          <Badge variant="neutral" noDot><XMarkIcon className="w-3 h-3 inline mr-0.5" />OFF</Badge>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-dark-300">{a.assigner_username || '—'}</td>
                      <td className="px-4 py-3 text-xs text-dark-400">{fmtDate(a.created_at)}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="inline-flex gap-1">
                          <button
                            onClick={() => handleToggleRow(a)}
                            disabled={isBusy}
                            className={cn(
                              'px-2 py-1 rounded-md text-xs border transition-colors',
                              a.is_active
                                ? 'border-dark-700 text-dark-300 hover:bg-dark-800'
                                : 'border-primary-500/40 text-primary-300 hover:bg-primary-500/10',
                              isBusy && 'opacity-50 cursor-not-allowed',
                            )}
                            title={a.is_active ? 'Disable (keep assignment)' : 'Enable assignment'}
                          >
                            {isBusy ? <ArrowPathIcon className="w-3.5 h-3.5 animate-spin" /> : (a.is_active ? 'Disable' : 'Enable')}
                          </button>
                          <button
                            onClick={() => setShowConfirmRemove(a)}
                            disabled={isBusy}
                            className={cn(
                              'px-2 py-1 rounded-md text-xs border border-red-500/40 text-red-300 hover:bg-red-500/10 transition-colors',
                              isBusy && 'opacity-50 cursor-not-allowed',
                            )}
                            title="Permanently remove assignment"
                          >
                            <TrashIcon className="w-3.5 h-3.5" />
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
      </section>

      {/* Remove confirm dialog */}
      <ConfirmDialog
        isOpen={showConfirmRemove !== null}
        title="Remove assignment?"
        message={
          showConfirmRemove
            ? `This will permanently remove the ${showConfirmRemove.assignment_type === 'CLIENT' ? 'full-Client' : 'direct-target'} assignment for user "${showConfirmRemove.user_username || `#${showConfirmRemove.user_id}`}"`
              + (showConfirmRemove.client_name ? ` on client "${showConfirmRemove.client_name}"` : '')
              + '. The user will lose access immediately.  This is distinct from "disabled" — the assignment is fully deleted.'
            : ''
        }
        confirmLabel="Remove"
        cancelLabel="Keep"
        onConfirm={() => showConfirmRemove && handleRemoveRow(showConfirmRemove)}
        onCancel={() => setShowConfirmRemove(null)}
      />
    </div>
  );
};
