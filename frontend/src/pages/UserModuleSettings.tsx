// frontend/src/pages/UserModuleSettings.tsx
import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeftIcon,
  AdjustmentsHorizontalIcon,
  CheckCircleIcon,
  ShieldCheckIcon,
  ShieldExclamationIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Spinner } from '@/components/ui/Spinner';
import { useToast } from '@/context/ToastContext';
import { usersApi } from '@/api/users.api';
import { ROUTES } from '@/routes/paths';
import { cn } from '@/utils/cn';

// ---------------------------------------------------------------------------
// Module catalogue — must mirror backend ModulePermission.ALL + UI_GROUPS
// ---------------------------------------------------------------------------
interface ModuleDef {
  name: string;
  label: string;
  description: string;
  group: string; // group id
}

const NETWORK_MODULE_GROUP = 'network_module_group';
const ASSETS_GROUP = 'assets_group';
const REPORTS_GROUP = 'reports_group';
const FEATURE_GROUP = 'feature_group';

const ALL_MODULES: ModuleDef[] = [
  // Network Module group — these are the 8 children of the parent
  // "Network Module" toggle.
  { name: 'host_discovery',     label: 'Host Discovery',       description: 'DNS resolution + TCP reachability check',                group: NETWORK_MODULE_GROUP },
  { name: 'dns',                label: 'DNS Lookup',            description: 'A, AAAA, MX, NS, TXT, SOA, CAA, PTR records',            group: NETWORK_MODULE_GROUP },
  { name: 'port_scan',          label: 'Port Scan',             description: 'TCP connect scan against common / web / custom ports',   group: NETWORK_MODULE_GROUP },
  { name: 'ssl',                label: 'SSL/TLS Analysis',      description: 'Certificate inspection, expiry, chain status',           group: NETWORK_MODULE_GROUP },
  { name: 'service_detection',  label: 'Service Detection',    description: 'Identify services and versions from open ports',        group: NETWORK_MODULE_GROUP },
  { name: 'http',               label: 'HTTPS Header',          description: 'Security header assessment (CSP, HSTS, …)',              group: NETWORK_MODULE_GROUP },
  { name: 'whois',              label: 'WHOIS',                 description: 'Registrar and registrant metadata',                     group: NETWORK_MODULE_GROUP },
  { name: 'screenshot',         label: 'Website Screenshot',    description: 'Browser screenshot capture (Playwright)',               group: NETWORK_MODULE_GROUP },
  // Assets
  { name: 'assets',             label: 'Assets',                description: 'View and manage discovered assets',                     group: ASSETS_GROUP },
  // Reports
  { name: 'reports',            label: 'Reports',               description: 'View, generate, and download HTML / PDF reports',       group: REPORTS_GROUP },
  // Features
  { name: 'private_network_scan', label: 'Private Network Scan', description: 'Allow scanning private/internal network targets (10/8, 172.16/12, 192.168/16)', group: FEATURE_GROUP },
];

const GROUPS: Array<{ id: string; label: string; description?: string; has_parent?: boolean }> = [
  { id: NETWORK_MODULE_GROUP, label: 'Network Module', description: 'Reconnaissance modules — each one runs an actual network operation.  Toggle the parent OFF to disable all submodules at once; toggle ON to restore previous submodule states.', has_parent: true },
  { id: ASSETS_GROUP,         label: 'Assets',         description: 'Page-level access to the discovered-assets inventory.' },
  { id: REPORTS_GROUP,        label: 'Reports',        description: 'Page-level access to scan reports (HTML + PDF generation).' },
  { id: FEATURE_GROUP,        label: 'Features',       description: 'Feature-level permissions that gate specific capabilities.' },
];

// ---------------------------------------------------------------------------
// Toggle switch component
// ---------------------------------------------------------------------------
const Toggle: React.FC<{ enabled: boolean; onClick: () => void; disabled?: boolean }> = ({ enabled, onClick, disabled }) => (
  <button
    type="button"
    role="switch"
    aria-checked={enabled}
    disabled={disabled}
    onClick={onClick}
    className={cn(
      'relative inline-flex items-center h-6 w-11 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500/60 focus:ring-offset-2 focus:ring-offset-dark-900',
      enabled ? 'bg-primary-500' : 'bg-dark-700',
      disabled && 'opacity-50 cursor-not-allowed',
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

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export const UserModuleSettings: React.FC = () => {
  const { userId } = useParams<{ userId: string }>();
  const uid = Number(userId);
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [userName, setUserName] = useState<string>('');
  const [userRole, setUserRole] = useState<string>('');
  const [isDefaultOpen, setIsDefaultOpen] = useState(true);
  // permissions map: { module_name: is_allowed }
  const [permissions, setPermissions] = useState<Record<string, boolean>>({});
  // original permissions (for dirty-state detection)
  const [original, setOriginal] = useState<Record<string, boolean>>({});
  // Phase 19 — saved snapshot of the Network submodule states when the
  // parent is OFF.  Used to restore the previous states when the parent
  // is turned back ON.  Persisted across parent toggles but cleared on
  // save.
  const networkChildrenSnapshotRef = useRef<Record<string, boolean> | null>(null);

  // Load user info + permissions
  useEffect(() => {
    if (!uid) return;
    setLoading(true);
    Promise.all([
      usersApi.getUsers(), // to find the user's name + role
      usersApi.getModulePermissions(uid),
    ]).then(([users, perms]) => {
      const u = users.find(x => x.id === uid);
      if (u) {
        setUserName(u.username);
        setUserRole(u.role.name);
      }
      setIsDefaultOpen(perms.is_default_open);
      const map: Record<string, boolean> = {};
      for (const m of ALL_MODULES) {
        const found = perms.permissions.find(p => p.module_name === m.name);
        map[m.name] = found ? found.is_allowed : perms.is_default_open;
      }
      setPermissions(map);
      setOriginal({ ...map });
    }).catch(err => {
      const msg = err?.response?.data?.message || 'Failed to load module permissions.';
      showToast(msg, 'error');
    }).finally(() => setLoading(false));
  }, [uid, showToast]);

  const dirty = useMemo(() => {
    for (const m of ALL_MODULES) {
      if ((permissions[m.name] ?? false) !== (original[m.name] ?? false)) return true;
    }
    return false;
  }, [permissions, original]);

  // -----------------------------------------------------------------
  // Network submodule names (the 8 children of the parent toggle).
  // -----------------------------------------------------------------
  const networkChildren = ALL_MODULES.filter(m => m.group === NETWORK_MODULE_GROUP);
  const networkParentEnabled = useMemo(
    () => networkChildren.some(m => permissions[m.name]),
    [permissions, networkChildren],
  );

  const toggleModule = (name: string) => {
    setPermissions(prev => ({ ...prev, [name]: !prev[name] }));
    setIsDefaultOpen(false);
  };

  // -----------------------------------------------------------------
  // Parent Network Module toggle.
  //
  // Turning the parent OFF:
  //   - Save the current state of every child to
  //     ``networkChildrenSnapshotRef`` so we can restore them later.
  //   - Set every child to False.
  //
  // Turning the parent ON:
  //   - If a snapshot exists, restore the children to their previous
  //     states.  This preserves the "individual child can stay OFF
  //     even when parent is ON" use-case (e.g. the admin previously
  //     disabled Port Scan while keeping the parent ON).
  //   - If no snapshot exists (first time turning ON, or after a
  //     fresh save), default every child to True.
  // -----------------------------------------------------------------
  const toggleNetworkParent = () => {
    setIsDefaultOpen(false);
    setPermissions(prev => {
      const next = { ...prev };
      if (networkParentEnabled) {
        // Turning parent OFF — snapshot the current children, then disable.
        const snapshot: Record<string, boolean> = {};
        for (const m of networkChildren) {
          snapshot[m.name] = !!prev[m.name];
          next[m.name] = false;
        }
        networkChildrenSnapshotRef.current = snapshot;
      } else {
        // Turning parent ON — restore previous child states if a
        // snapshot exists, otherwise default to True.
        const snapshot = networkChildrenSnapshotRef.current;
        for (const m of networkChildren) {
          if (snapshot && m.name in snapshot) {
            next[m.name] = snapshot[m.name];
          } else {
            next[m.name] = true;
          }
        }
        // Clear the snapshot once we've consumed it so a subsequent
        // OFF → ON cycle defaults to all-on.
        networkChildrenSnapshotRef.current = null;
      }
      return next;
    });
  };

  const handleSave = async () => {
    if (!uid) return;
    setSaving(true);
    try {
      const perms = ALL_MODULES.map(m => ({
        module_name: m.name,
        is_allowed: permissions[m.name] ?? false,
      }));
      const result = await usersApi.setModulePermissions(uid, perms);
      setIsDefaultOpen(result.is_default_open);
      const map: Record<string, boolean> = {};
      for (const m of ALL_MODULES) {
        const found = result.permissions.find(p => p.module_name === m.name);
        map[m.name] = found ? found.is_allowed : result.is_default_open;
      }
      setPermissions(map);
      setOriginal({ ...map });
      // Clear the snapshot — after a save, the "previous state" is the
      // saved state, so a future parent-OFF → ON cycle should restore
      // the saved children, not the in-memory snapshot.
      networkChildrenSnapshotRef.current = null;
      showToast(`Module permissions saved for ${userName}.`, 'success');
    } catch (err: any) {
      const msg = err?.response?.data?.message || 'Failed to save module permissions.';
      showToast(msg, 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleResetToDefault = async () => {
    if (!uid) return;
    setSaving(true);
    try {
      // Send empty list to return to default-open
      const result = await usersApi.setModulePermissions(uid, []);
      setIsDefaultOpen(result.is_default_open);
      const map: Record<string, boolean> = {};
      for (const m of ALL_MODULES) {
        map[m.name] = true; // default-open = all True
      }
      setPermissions(map);
      setOriginal({ ...map });
      networkChildrenSnapshotRef.current = null;
      showToast(`Module permissions reset to default (all allowed) for ${userName}.`, 'success');
    } catch (err: any) {
      const msg = err?.response?.data?.message || 'Failed to reset module permissions.';
      showToast(msg, 'error');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Spinner className="w-8 h-8" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="space-y-2">
        <button
          onClick={() => navigate(ROUTES.USERS)}
          className="text-xs text-dark-400 hover:text-primary-300 transition-colors flex items-center gap-1"
        >
          <ArrowLeftIcon className="w-3.5 h-3.5" />
          Back to Users
        </button>
        <div className="flex items-center gap-3 flex-wrap">
          <div className="w-10 h-10 rounded-xl bg-gradient-cyber/20 border border-primary-700/40 flex items-center justify-center text-primary-300 shrink-0">
            <AdjustmentsHorizontalIcon className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-display font-bold text-dark-50">
              User Module Settings
            </h1>
            <p className="text-sm text-dark-400 mt-0.5">
              Configuring permissions for{' '}
              <span className="text-dark-200 font-mono">{userName || `user #${uid}`}</span>{' '}
              {userRole && (
                <Badge variant={userRole === 'Administrator' ? 'primary' : 'neutral'} noDot>
                  {userRole}
                </Badge>
              )}
            </p>
          </div>
        </div>
      </div>

      {/* Default-open banner */}
      <div
        className={cn(
          'flex items-start gap-3 p-4 rounded-xl border',
          isDefaultOpen
            ? 'bg-emerald-900/20 border-emerald-600/40'
            : 'bg-primary-900/15 border-primary-700/30',
        )}
      >
        {isDefaultOpen ? (
          <ShieldCheckIcon className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
        ) : (
          <InformationCircleIcon className="w-5 h-5 text-primary-300 shrink-0 mt-0.5" />
        )}
        <div className="text-xs">
          {isDefaultOpen ? (
            <>
              <strong className="text-emerald-300">Default-open (all allowed).</strong>{' '}
              <span className="text-dark-300">
                This user currently has access to every module.  Toggling any switch below will
                switch the user to explicit-mode, where only the modules with an explicit ON row
                are accessible.
              </span>
            </>
          ) : (
            <>
              <strong className="text-primary-300">Explicit permissions mode.</strong>{' '}
              <span className="text-dark-300">
                Only the modules with an explicit ON row are accessible to this user.  Use the
                Reset button below to return to default-open.
              </span>
            </>
          )}
        </div>
      </div>

      {/* Permission groups */}
      {GROUPS.map(group => {
        const groupModules = ALL_MODULES.filter(m => m.group === group.id);
        return (
          <div key={group.id} className="glass-panel border-glow-top rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-dark-800 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 min-w-0">
                <span className="w-1.5 h-1.5 rounded-full bg-primary-400 shadow-glow-sm" />
                <h2 className="text-base font-display font-semibold text-dark-50">{group.label}</h2>
                <span className="text-xs text-dark-500 ml-1">
                  ({groupModules.filter(m => permissions[m.name]).length}/{groupModules.length} on)
                </span>
              </div>
              {/* Phase 19 — parent toggle for the Network Module group. */}
              {group.has_parent && (
                <div className="flex items-center gap-3 shrink-0">
                  <span className={cn(
                    'text-xs font-medium',
                    networkParentEnabled ? 'text-primary-300' : 'text-dark-500',
                  )}>
                    {networkParentEnabled ? 'ON' : 'OFF'}
                  </span>
                  <Toggle
                    enabled={networkParentEnabled}
                    onClick={toggleNetworkParent}
                    disabled={saving}
                  />
                </div>
              )}
            </div>
            {group.description && (
              <div className="px-5 pt-3 text-xs text-dark-400">{group.description}</div>
            )}
            <div className="p-3 sm:p-5 space-y-1.5">
              {/* Phase 19 — when the parent is OFF, the children are
                  visually dimmed and disabled to communicate that
                  they cannot be turned ON individually until the
                  parent is re-enabled. */}
              {groupModules.map(m => {
                const enabled = permissions[m.name] ?? false;
                const parentDisabled = !!group.has_parent && !networkParentEnabled;
                const visuallyDisabled = parentDisabled;
                return (
                  <div
                    key={m.name}
                    className={cn(
                      'flex items-center justify-between gap-3 rounded-lg border p-3 transition-all',
                      enabled && !visuallyDisabled
                        ? 'border-primary-500/30 bg-primary-500/[0.03]'
                        : 'border-dark-700/60 bg-dark-900/40',
                      visuallyDisabled && 'opacity-50',
                    )}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-dark-100">{m.label}</span>
                        <code className="text-[10px] text-dark-500 font-mono">{m.name}</code>
                      </div>
                      <p className="text-xs text-dark-500 mt-0.5">{m.description}</p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <span className={cn(
                        'text-xs font-medium',
                        enabled ? 'text-primary-300' : 'text-dark-500',
                      )}>
                        {enabled ? 'ON' : 'OFF'}
                      </span>
                      <Toggle
                        enabled={enabled}
                        onClick={() => toggleModule(m.name)}
                        disabled={saving || visuallyDisabled}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      {/* Action bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleResetToDefault}
            isLoading={saving}
          >
            Reset to Default (All Allowed)
          </Button>
          <Link to={ROUTES.USERS}>
            <Button variant="ghost" size="sm" disabled={saving}>Cancel</Button>
          </Link>
        </div>
        <div className="flex items-center gap-3">
          {dirty && (
            <span className="text-xs text-amber-400 flex items-center gap-1">
              <ShieldExclamationIcon className="w-4 h-4" />
              Unsaved changes
            </span>
          )}
          <Button
            onClick={handleSave}
            isLoading={saving}
            disabled={!dirty}
          >
            <CheckCircleIcon className="w-4 h-4 mr-1.5" />
            Save Permissions
          </Button>
        </div>
      </div>
    </div>
  );
};
