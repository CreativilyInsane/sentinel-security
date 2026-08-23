// frontend/src/pages/Clients.tsx
import React, { useState, useMemo } from 'react';
import {
  MagnifyingGlassIcon,
  BuildingOffice2Icon,
  PlusIcon,
  TrashIcon,
  ServerStackIcon,
  UserPlusIcon,
  EyeIcon,
} from '@heroicons/react/24/outline';
import { Link, useNavigate } from 'react-router-dom';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Spinner } from '@/components/ui/Spinner';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { useClients, useCreateClient, useDeleteClient } from '@/hooks/useClients';
import { useToast } from '@/context/ToastContext';
import { ROUTES } from '@/routes/paths';
import { cn } from '@/utils/cn';
import type { ClientWithStats, ClientCreatePayload } from '@/types/client.types';

const fmtDate = (iso: string): string => {
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
};

const Th: React.FC<{ children?: React.ReactNode; className?: string }> = ({ children, className = '' }) => (
  <th className={cn('px-4 py-3 text-xs font-semibold text-dark-400 uppercase tracking-wider', className)}>{children}</th>
);

export const Clients: React.FC = () => {
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ClientWithStats | null>(null);

  const { data, isLoading, isFetching } = useClients({ search: search || undefined, limit: 200 });
  const createClient = useCreateClient();
  const deleteClient = useDeleteClient();

  const clients = data || [];

  const filtered = useMemo(() => {
    if (!search) return clients;
    const q = search.toLowerCase();
    return clients.filter(c =>
      c.name.toLowerCase().includes(q) ||
      (c.company_name || '').toLowerCase().includes(q),
    );
  }, [clients, search]);

  const onDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await deleteClient.mutateAsync(deleteTarget.id);
      showToast(`Client '${deleteTarget.name}' deactivated.`, 'success');
    } catch (err: any) {
      showToast(err?.response?.data?.message || 'Failed to delete client.', 'error');
    } finally {
      setDeleteTarget(null);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-display font-bold text-dark-50">Clients</h1>
          <p className="text-dark-400 mt-1">
            Create and manage customer / network environments.  Add IP and CIDR assets, then assign them to users.
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <PlusIcon className="w-4 h-4 mr-1.5" />
          Create Client
        </Button>
      </div>

      <div className="glass-panel rounded-xl p-4">
        <Input
          id="search"
          placeholder="Search clients by name or company..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          icon={<MagnifyingGlassIcon className="w-4 h-4" />}
        />
      </div>

      <div className="glass-panel border-glow-top rounded-xl overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Spinner className="w-7 h-7" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-dark-400">
            <BuildingOffice2Icon className="w-10 h-10 mb-3 text-dark-600" />
            <p className="text-sm">No clients found.</p>
            <Button variant="secondary" size="sm" className="mt-3" onClick={() => setShowCreate(true)}>
              <PlusIcon className="w-4 h-4 mr-1" /> Create your first client
            </Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-dark-950/60 border-b border-dark-800">
                <tr>
                  <Th>Client Name</Th>
                  <Th>Company</Th>
                  <Th>Assets</Th>
                  <Th>Assigned Users</Th>
                  <Th>Status</Th>
                  <Th>Created</Th>
                  <Th className="text-right">Actions</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-800/70">
                {filtered.map(c => (
                  <tr key={c.id} className="hover:bg-primary-500/[0.04] transition-colors">
                    <td className="px-4 py-3">
                      <Link to={ROUTES.CLIENT_DETAIL_BY_ID(c.id)} className="text-sm font-medium text-dark-100 hover:text-primary-300 transition-colors">
                        {c.name}
                      </Link>
                      {c.description && (
                        <div className="text-xs text-dark-500 line-clamp-1">{c.description}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-dark-300">{c.company_name || '—'}</td>
                    <td className="px-4 py-3">
                      <Badge variant="info" noDot>{c.asset_count}</Badge>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={c.active_assignment_count > 0 ? 'success' : 'neutral'} noDot>
                        {c.assigned_user_count} ({c.active_assignment_count} active)
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={c.is_active ? 'success' : 'neutral'} noDot>
                        {c.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-xs text-dark-400">{fmtDate(c.created_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1.5">
                        <Link to={ROUTES.CLIENT_DETAIL_BY_ID(c.id)} title="View / Manage">
                          <Button variant="ghost" size="sm">
                            <EyeIcon className="w-4 h-4" />
                            <span className="ml-1 hidden sm:inline">View</span>
                          </Button>
                        </Link>
                        <Link to={ROUTES.CLIENT_DETAIL_BY_ID(c.id)} title="Manage Assets">
                          <Button variant="ghost" size="sm">
                            <ServerStackIcon className="w-4 h-4" />
                          </Button>
                        </Link>
                        <Link to={ROUTES.CLIENT_DETAIL_BY_ID(c.id)} title="Assign">
                          <Button variant="ghost" size="sm">
                            <UserPlusIcon className="w-4 h-4" />
                          </Button>
                        </Link>
                        <button
                          onClick={() => setDeleteTarget(c)}
                          className="p-1.5 text-dark-400 hover:text-red-400 hover:bg-dark-800 rounded-lg transition-all"
                          title="Delete"
                        >
                          <TrashIcon className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {isFetching && !isLoading && (
          <div className="text-center py-2 text-xs text-dark-500">Syncing…</div>
        )}
      </div>

      <CreateClientModal
        isOpen={showCreate}
        onClose={() => setShowCreate(false)}
        onSubmit={async (payload) => {
          try {
            const c = await createClient.mutateAsync(payload);
            showToast(`Client '${c.name}' created.`, 'success');
            setShowCreate(false);
            navigate(ROUTES.CLIENT_DETAIL_BY_ID(c.id));
          } catch (err: any) {
            showToast(err?.response?.data?.message || 'Failed to create client.', 'error');
          }
        }}
        isLoading={createClient.isPending}
      />

      <ConfirmDialog
        isOpen={!!deleteTarget}
        title="Deactivate Client"
        message={`This will deactivate '${deleteTarget?.name}' and remove all active user assignments. Historical scans and reports are preserved.`}
        confirmLabel="Deactivate"
        cancelLabel="Cancel"
        isLoading={deleteClient.isPending}
        onConfirm={onDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
};

// ---------------------------------------------------------------------------
// Create Client modal
// ---------------------------------------------------------------------------
const CreateClientModal: React.FC<{
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (payload: ClientCreatePayload) => void;
  isLoading: boolean;
}> = ({ isOpen, onClose, onSubmit, isLoading }) => {
  const [name, setName] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [description, setDescription] = useState('');
  const [isActive, setIsActive] = useState(true);
  const [errors, setErrors] = useState<{ name?: string }>({});

  const handleSubmit = () => {
    if (!name.trim()) {
      setErrors({ name: 'Client name is required.' });
      return;
    }
    onSubmit({
      name: name.trim(),
      company_name: companyName.trim() || null,
      description: description.trim() || null,
      is_active: isActive,
    });
    // reset
    setName(''); setCompanyName(''); setDescription(''); setIsActive(true); setErrors({});
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Create Client" className="max-w-lg">
      <div className="space-y-4">
        <Input
          id="client-name"
          label="Client Name *"
          placeholder="ACME Corporation"
          value={name}
          onChange={e => { setName(e.target.value); setErrors(prev => ({ ...prev, name: undefined })); }}
          error={errors.name}
        />
        <Input
          id="client-company"
          label="Company Name"
          placeholder="ACME Inc."
          value={companyName}
          onChange={e => setCompanyName(e.target.value)}
        />
        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1.5">Description</label>
          <textarea
            className="w-full bg-dark-900/70 border border-dark-700 rounded-xl py-2.5 px-4 text-dark-100 placeholder-dark-500 focus:outline-none focus:ring-2 focus:ring-primary-500/60 focus:border-primary-500/60 hover:border-dark-600 transition-all min-h-[80px]"
            placeholder="Brief description of the client environment"
            value={description}
            onChange={e => setDescription(e.target.value)}
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-dark-300">
          <input
            type="checkbox"
            checked={isActive}
            onChange={e => setIsActive(e.target.checked)}
            className="rounded border-dark-600 bg-dark-900 text-primary-500 focus:ring-primary-500/40"
          />
          Active
        </label>
        <div className="flex justify-end gap-2 pt-3 border-t border-dark-800">
          <Button variant="secondary" size="sm" onClick={onClose}>Cancel</Button>
          <Button size="sm" onClick={handleSubmit} isLoading={isLoading}>
            <PlusIcon className="w-4 h-4 mr-1" />
            Create Client
          </Button>
        </div>
      </div>
    </Modal>
  );
};
