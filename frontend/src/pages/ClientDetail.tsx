// frontend/src/pages/ClientDetail.tsx
import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  BuildingOffice2Icon,
  PlusIcon,
  TrashIcon,
  ServerStackIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { Modal } from '@/components/ui/Modal';
import { Input } from '@/components/ui/Input';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { useToast } from '@/context/ToastContext';
import {
  useClient, useClientAssets, useCreateClientAsset, useDeleteClientAsset,
  useAssignments,
} from '@/hooks/useClients';
import { clientsApi } from '@/api/clients.api';
import { ROUTES } from '@/routes/paths';
import { cn } from '@/utils/cn';
import type { ClientAsset, ClientAssetType, ClientAssetCreatePayload } from '@/types/client.types';

const fmtDate = (iso?: string | null): string => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return String(iso); }
};

const Th: React.FC<{ children?: React.ReactNode; className?: string }> = ({ children, className = '' }) => (
  <th className={cn('px-4 py-3 text-xs font-semibold text-dark-400 uppercase tracking-wider', className)}>{children}</th>
);

export const ClientDetail: React.FC = () => {
  const { clientId } = useParams<{ clientId: string }>();
  const id = Number(clientId);
  const navigate = useNavigate();
  const { showToast } = useToast();

  const { data: client, isLoading } = useClient(id);
  const { data: assets, isLoading: assetsLoading } = useClientAssets(id);
  // Read-only list of assignments for context.  Management actions
  // (assign / remove) live on the dedicated /admin/assignments page
  // per the Sentinel Security change request (section #20).
  const { data: assignments } = useAssignments({ client_id: id, limit: 100 });

  const [showAddAsset, setShowAddAsset] = useState(false);
  const [deleteAsset, setDeleteAsset] = useState<ClientAsset | null>(null);

  const createAsset = useCreateClientAsset();
  const deleteAssetMut = useDeleteClientAsset();

  if (isLoading || !client) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Spinner className="w-8 h-8" />
      </div>
    );
  }

  const assetList = assets || [];
  const assignmentList = (assignments || []).filter(a => a.is_active);
  const clientAssignments = assignmentList.filter(a => a.assignment_type === 'CLIENT');

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="space-y-1">
        <button
          onClick={() => navigate(ROUTES.CLIENTS)}
          className="text-xs text-dark-400 hover:text-primary-300 transition-colors flex items-center gap-1"
        >
          <ArrowLeftIcon className="w-3.5 h-3.5" />
          Back to Clients
        </button>
        <div className="flex items-center gap-3 flex-wrap">
          <BuildingOffice2Icon className="w-7 h-7 text-primary-300" />
          <h1 className="text-2xl font-display font-bold text-dark-50">{client.name}</h1>
          <Badge variant={client.is_active ? 'success' : 'neutral'} noDot>
            {client.is_active ? 'Active' : 'Inactive'}
          </Badge>
        </div>
        {client.company_name && (
          <p className="text-sm text-dark-400">Company: {client.company_name}</p>
        )}
        {client.description && (
          <p className="text-sm text-dark-400">{client.description}</p>
        )}
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <SummaryCard label="Assets" value={String(assetList.length)} />
        <SummaryCard label="Assigned Users" value={String(clientAssignments.length)} />
        <SummaryCard label="Created" value={fmtDate(client.created_at)} />
        <SummaryCard
          label="Client Report"
          value="View"
          action
          onClick={async () => {
            try {
              // Phase 19 — fetch the report via axios (Bearer token
              // attached automatically) and open the resulting Blob
              // as an object URL.  This avoids the 401 "Not authenticated"
              // error that occurred when using window.open() with the
              // raw URL (which cannot send the JWT header).
              const blob = await clientsApi.fetchClientReportHtml(client.id);
              const url = window.URL.createObjectURL(new Blob([blob], { type: 'text/html' }));
              window.open(url, '_blank');
            } catch (err: any) {
              const msg = err?.response?.data?.message || 'Failed to load HTML report.';
              showToast(msg, 'error');
            }
          }}
        />
      </div>

      {/* Tabs / sections */}
      {/* Assets section */}
      <div className="glass-panel border-glow-top rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-dark-800">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-primary-400 shadow-glow-sm" />
            <h2 className="text-base font-display font-semibold text-dark-50">Assets</h2>
            <span className="text-xs text-dark-500">({assetList.length})</span>
          </div>
          <Button size="sm" onClick={() => setShowAddAsset(true)}>
            <PlusIcon className="w-4 h-4 mr-1" />
            Add Asset
          </Button>
        </div>
        {assetsLoading ? (
          <div className="flex justify-center py-12">
            <Spinner />
          </div>
        ) : assetList.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-dark-400">
            <ServerStackIcon className="w-10 h-10 mb-3 text-dark-600" />
            <p className="text-sm">No assets added yet.</p>
            <Button variant="secondary" size="sm" className="mt-3" onClick={() => setShowAddAsset(true)}>
              <PlusIcon className="w-4 h-4 mr-1" /> Add the first asset
            </Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-dark-950/60 border-b border-dark-800">
                <tr>
                  <Th>Type</Th>
                  <Th>Value</Th>
                  <Th>Name</Th>
                  <Th>Network / VLAN</Th>
                  <Th>Status</Th>
                  <Th>Created</Th>
                  <Th className="text-right">Actions</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-800/70">
                {assetList.map(a => {
                  const badgeVariant = a.asset_type === 'IP' ? 'info' : a.asset_type === 'IP_RANGE' ? 'primary' : 'neutral';
                  const badgeLabel = a.asset_type === 'IP' ? 'IP' : a.asset_type === 'IP_RANGE' ? 'IP RANGE' : 'DOMAIN';
                  return (
                  <tr key={a.id} className="hover:bg-primary-500/[0.04] transition-colors">
                    <td className="px-4 py-3">
                      <Badge variant={badgeVariant} noDot>
                        {badgeLabel}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-sm font-mono text-dark-100">
                      {a.ip_address || a.cidr || a.domain || '—'}
                    </td>
                    <td className="px-4 py-3 text-sm text-dark-200">{a.name || '—'}</td>
                    <td className="px-4 py-3 text-sm text-dark-300">
                      {a.network_name && <div>{a.network_name}</div>}
                      {a.vlan_name && <div className="text-xs text-dark-500">{a.vlan_name}</div>}
                      {!a.network_name && !a.vlan_name && '—'}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={a.is_active ? 'success' : 'neutral'} noDot>
                        {a.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-xs text-dark-400">{fmtDate(a.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => setDeleteAsset(a)}
                          className="p-1.5 text-dark-400 hover:text-red-400 hover:bg-dark-800 rounded-lg transition-all"
                          title="Delete asset"
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
      </div>

      {/* Assigned users section — read-only.  Management actions
          (assign client, assign direct target, remove) live on the
          dedicated /admin/assignments page.  A deep-link to that page
          filtered to this client is provided for convenience. */}
      <div className="glass-panel border-glow-top rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-dark-800">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-primary-400 shadow-glow-sm" />
            <h2 className="text-base font-display font-semibold text-dark-50">Assigned Users</h2>
            <span className="text-xs text-dark-500">({assignmentList.length})</span>
          </div>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => navigate(`${ROUTES.ASSIGNMENTS}?client_id=${id}`)}
          >
            Manage in Assignments
            <ArrowRightIcon className="w-4 h-4 ml-1" />
          </Button>
        </div>
        {assignmentList.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-dark-400">
            <ServerStackIcon className="w-10 h-10 mb-3 text-dark-600" />
            <p className="text-sm">No active assignments for this client yet.</p>
            <Button
              variant="secondary"
              size="sm"
              className="mt-3"
              onClick={() => navigate(`${ROUTES.ASSIGNMENTS}?client_id=${id}`)}
            >
              Open the Assignments page to create one
              <ArrowRightIcon className="w-4 h-4 ml-1" />
            </Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-dark-950/60 border-b border-dark-800">
                <tr>
                  <Th>User</Th>
                  <Th>Type</Th>
                  <Th>Target</Th>
                  <Th>Assigned By</Th>
                  <Th>Created</Th>
                  <Th>Status</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-800/70">
                {assignmentList.map(a => (
                  <tr key={a.id} className={cn('hover:bg-primary-500/[0.04] transition-colors', !a.is_active && 'opacity-60')}>
                    <td className="px-4 py-3 text-sm text-dark-100">{a.user_username || `User #${a.user_id}`}</td>
                    <td className="px-4 py-3">
                      <Badge variant={a.assignment_type === 'CLIENT' ? 'info' : 'primary'} noDot>
                        {a.assignment_type === 'CLIENT' ? 'Full Client' : 'Direct Target'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-sm font-mono text-dark-200">{a.target_value}</td>
                    <td className="px-4 py-3 text-sm text-dark-300">{a.assigner_username || '—'}</td>
                    <td className="px-4 py-3 text-xs text-dark-400">{fmtDate(a.created_at)}</td>
                    <td className="px-4 py-3">
                      <Badge variant={a.is_active ? 'success' : 'neutral'} noDot>
                        {a.is_active ? 'ON' : 'OFF'}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modals */}
      <AddAssetModal
        isOpen={showAddAsset}
        onClose={() => setShowAddAsset(false)}
        onSubmit={async (payload) => {
          try {
            await createAsset.mutateAsync({ clientId: id, payload });
            showToast('Asset added.', 'success');
            setShowAddAsset(false);
          } catch (err: any) {
            showToast(err?.response?.data?.message || 'Failed to add asset.', 'error');
          }
        }}
        isLoading={createAsset.isPending}
      />

      <ConfirmDialog
        isOpen={!!deleteAsset}
        title="Delete Asset"
        message={`Delete asset '${deleteAsset?.name || deleteAsset?.ip_address || deleteAsset?.cidr}'? Linked assignments will be deactivated.`}
        confirmLabel="Delete"
        cancelLabel="Cancel"
        isLoading={deleteAssetMut.isPending}
        onConfirm={async () => {
          if (!deleteAsset) return;
          try {
            await deleteAssetMut.mutateAsync({ clientId: id, assetId: deleteAsset.id });
            showToast('Asset deleted.', 'success');
          } catch (err: any) {
            showToast(err?.response?.data?.message || 'Failed to delete asset.', 'error');
          } finally {
            setDeleteAsset(null);
          }
        }}
        onCancel={() => setDeleteAsset(null)}
      />
    </div>
  );
};

// ---------------------------------------------------------------------------
// Summary card
// ---------------------------------------------------------------------------
const SummaryCard: React.FC<{
  label: string;
  value: string;
  action?: boolean;
  onClick?: () => void;
}> = ({ label, value, action, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    disabled={!action}
    className={cn(
      'text-left rounded-lg border p-3',
      action
        ? 'border-primary-500/30 bg-primary-500/5 text-primary-300 hover:border-primary-500/50 cursor-pointer'
        : 'border-dark-700 bg-dark-900/40 text-dark-100 cursor-default',
    )}
  >
    <div className="text-[10px] uppercase tracking-wider text-dark-500 mb-1">{label}</div>
    <div className="text-sm">{value}</div>
  </button>
);

// ---------------------------------------------------------------------------
// Add Asset modal
// ---------------------------------------------------------------------------
const AddAssetModal: React.FC<{
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: ClientAssetCreatePayload) => void;
  isLoading: boolean;
}> = ({ isOpen, onClose, onSubmit, isLoading }) => {
  const [assetType, setAssetType] = useState<ClientAssetType>('IP');
  const [ipAddress, setIpAddress] = useState('');
  const [cidr, setCidr] = useState('');
  const [domain, setDomain] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [networkName, setNetworkName] = useState('');
  const [vlanName, setVlanName] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});

  const reset = () => {
    setAssetType('IP'); setIpAddress(''); setCidr(''); setDomain(''); setName('');
    setDescription(''); setNetworkName(''); setVlanName(''); setErrors({});
  };

  const handleSubmit = () => {
    const errs: Record<string, string> = {};
    if (assetType === 'IP') {
      if (!ipAddress.trim()) errs.ipAddress = 'IP address is required.';
      else if (!/^(\d{1,3}\.){3}\d{1,3}$/.test(ipAddress.trim()) && !/^[0-9a-fA-F:]+$/.test(ipAddress.trim())) {
        errs.ipAddress = 'Invalid IP address format.';
      }
    } else if (assetType === 'IP_RANGE') {
      if (!cidr.trim()) errs.cidr = 'CIDR is required.';
      else if (!/^(\d{1,3}\.){3}\d{1,3}\/\d{1,2}$/.test(cidr.trim()) && !/^[0-9a-fA-F:]+\/\d{1,3}$/.test(cidr.trim())) {
        errs.cidr = 'Invalid CIDR format (e.g. 192.168.1.0/24).';
      }
    } else { // DOMAIN
      if (!domain.trim()) errs.domain = 'Domain is required.';
      else if (!/^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$/.test(domain.trim())) {
        errs.domain = 'Invalid domain (e.g. acme.com). Must include a valid TLD.';
      }
    }
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }
    onSubmit({
      asset_type: assetType,
      ip_address: assetType === 'IP' ? ipAddress.trim() : null,
      cidr: assetType === 'IP_RANGE' ? cidr.trim() : null,
      domain: assetType === 'DOMAIN' ? domain.trim().toLowerCase() : null,
      name: name.trim() || null,
      description: description.trim() || null,
      network_name: networkName.trim() || null,
      vlan_name: vlanName.trim() || null,
      is_active: true,
    });
    reset();
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add Asset" className="max-w-lg">
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1.5">Asset Type</label>
          <div className="grid grid-cols-3 gap-2">
            <button
              type="button"
              onClick={() => setAssetType('IP')}
              className={cn(
                'rounded-lg border p-3 text-left transition-all',
                assetType === 'IP'
                  ? 'border-primary-500/50 bg-primary-500/10 text-primary-300'
                  : 'border-dark-700 bg-dark-900/40 text-dark-300 hover:border-dark-600',
              )}
            >
              <div className="text-sm font-semibold">Single IP</div>
              <div className="text-xs text-dark-400">192.168.1.10</div>
            </button>
            <button
              type="button"
              onClick={() => setAssetType('IP_RANGE')}
              className={cn(
                'rounded-lg border p-3 text-left transition-all',
                assetType === 'IP_RANGE'
                  ? 'border-primary-500/50 bg-primary-500/10 text-primary-300'
                  : 'border-dark-700 bg-dark-900/40 text-dark-300 hover:border-dark-600',
              )}
            >
              <div className="text-sm font-semibold">IP Range / CIDR</div>
              <div className="text-xs text-dark-400">192.168.1.0/24</div>
            </button>
            <button
              type="button"
              onClick={() => setAssetType('DOMAIN')}
              className={cn(
                'rounded-lg border p-3 text-left transition-all',
                assetType === 'DOMAIN'
                  ? 'border-primary-500/50 bg-primary-500/10 text-primary-300'
                  : 'border-dark-700 bg-dark-900/40 text-dark-300 hover:border-dark-600',
              )}
            >
              <div className="text-sm font-semibold">Domain</div>
              <div className="text-xs text-dark-400">acme.com</div>
            </button>
          </div>
        </div>
        {assetType === 'IP' ? (
          <Input
            id="ip"
            label="IP Address *"
            placeholder="192.168.1.10"
            value={ipAddress}
            onChange={e => { setIpAddress(e.target.value); setErrors(prev => { const next = { ...prev }; delete next.ipAddress; return next; }); }}
            error={errors.ipAddress}
          />
        ) : assetType === 'IP_RANGE' ? (
          <Input
            id="cidr"
            label="CIDR *"
            placeholder="192.168.1.0/24"
            value={cidr}
            onChange={e => { setCidr(e.target.value); setErrors(prev => { const next = { ...prev }; delete next.cidr; return next; }); }}
            error={errors.cidr}
          />
        ) : (
          <Input
            id="domain"
            label="Domain *"
            placeholder="acme.com"
            value={domain}
            onChange={e => { setDomain(e.target.value); setErrors(prev => { const next = { ...prev }; delete next.domain; return next; }); }}
            error={errors.domain}
          />
        )}
        <Input
          id="name"
          label={assetType === 'IP' ? 'Device Name' : assetType === 'IP_RANGE' ? 'Network Name' : 'Site Name'}
          placeholder={assetType === 'IP' ? 'Web Server 01' : assetType === 'IP_RANGE' ? 'Office Network' : 'Corporate Website'}
          value={name}
          onChange={e => setName(e.target.value)}
        />
        {assetType === 'IP_RANGE' && (
          <div className="grid grid-cols-2 gap-3">
            <Input
              id="network-name"
              label="Network Name (alt)"
              placeholder="Head Office"
              value={networkName}
              onChange={e => setNetworkName(e.target.value)}
            />
            <Input
              id="vlan-name"
              label="VLAN Name"
              placeholder="VLAN 20"
              value={vlanName}
              onChange={e => setVlanName(e.target.value)}
            />
          </div>
        )}
        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1.5">Description</label>
          <textarea
            className="w-full bg-dark-900/70 border border-dark-700 rounded-xl py-2.5 px-4 text-dark-100 placeholder-dark-500 focus:outline-none focus:ring-2 focus:ring-primary-500/60 focus:border-primary-500/60 hover:border-dark-600 transition-all min-h-[60px]"
            placeholder="Optional notes"
            value={description}
            onChange={e => setDescription(e.target.value)}
          />
        </div>
        <div className="flex items-start gap-2 p-3 rounded-lg bg-amber-900/20 border border-amber-600/40">
          <ExclamationTriangleIcon className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <p className="text-xs text-amber-300">
            Backend validates IP/CIDR syntax, rejects duplicates, and supports both IPv4 and IPv6.
          </p>
        </div>
        <div className="flex justify-end gap-2 pt-3 border-t border-dark-800">
          <Button variant="secondary" size="sm" onClick={onClose}>Cancel</Button>
          <Button size="sm" onClick={handleSubmit} isLoading={isLoading}>
            <PlusIcon className="w-4 h-4 mr-1" />
            Add Asset
          </Button>
        </div>
      </div>
    </Modal>
  );
};

// ---------------------------------------------------------------------------
// AssignModal has been REMOVED.  All assignment management (full Client
// assignments AND direct-target assignments) now lives on the dedicated
// /admin/assignments page — see Assignments.tsx.  This is per the
// Sentinel Security change request section #20 ("Move assignment
// management OUT of Client Details") to make assignment management
// explicit and easier to understand.
// ---------------------------------------------------------------------------
