// frontend/src/pages/NetworkScan.tsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  SignalIcon,
  ServerStackIcon,
  CircleStackIcon,
  IdentificationIcon,
  GlobeAltIcon,
  ShieldCheckIcon,
  GlobeAsiaAustraliaIcon,
  CameraIcon,
  CheckCircleIcon,
  XMarkIcon,
  ShieldExclamationIcon,
} from '@heroicons/react/24/outline';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Spinner } from '@/components/ui/Spinner';
import { useToast } from '@/context/ToastContext';
import { useAuth } from '@/context/AuthContext';
import { useCreateScan } from '@/hooks/useRecon';
import { useMyTargets } from '@/hooks/useClients';
import { usersApi } from '@/api/users.api';
import { ROUTES } from '@/routes/paths';
import type { ReconModule, PortPreset } from '@/types/recon.types';
import { cn } from '@/utils/cn';

interface ModuleOption {
  id: ReconModule;
  name: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}

const MODULE_OPTIONS: ModuleOption[] = [
  { id: 'host_discovery', name: 'Host Discovery', description: 'Resolve DNS and verify host reachability via safe TCP probes.', icon: ServerStackIcon },
  { id: 'port_scan', name: 'Port Scan', description: 'Safe TCP connect scan against configurable common, web, or custom port sets.', icon: SignalIcon },
  { id: 'service_detection', name: 'Service Detection', description: 'Identify services and versions from open ports using protocol-aware probes.', icon: CircleStackIcon },
  { id: 'whois', name: 'WHOIS', description: 'Retrieve registrar, dates, name servers, and registrant metadata for a domain.', icon: IdentificationIcon },
  { id: 'dns', name: 'DNS Lookup', description: 'Resolve A, AAAA, CNAME, MX, NS, TXT, SOA, PTR, and CAA records.', icon: GlobeAltIcon },
  { id: 'ssl', name: 'SSL / TLS Analysis', description: 'Inspect the server certificate, expiry, signature, SANs, and chain status.', icon: ShieldCheckIcon },
  { id: 'http', name: 'HTTP Headers', description: 'Assess security headers (CSP, HSTS, X-Frame-Options, Referrer-Policy, …).', icon: GlobeAsiaAustraliaIcon },
  { id: 'screenshot', name: 'Website Screenshot', description: 'Capture a browser screenshot of the target homepage in a sandboxed renderer.', icon: CameraIcon },
];

export const NetworkScan: React.FC = () => {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { user } = useAuth();
  const createScan = useCreateScan();
  const myTargets = useMyTargets();

  const isAdmin = user?.role.name === 'Administrator';
  // privateScanEnabled now derives from the per-user `private_network_scan`
  // module permission fetched via allowed-modules.  Admins always have it.
  const [privateScanEnabled, setPrivateScanEnabled] = React.useState<boolean>(!!isAdmin);

  // Fetch the user's allowed modules.  Admins skip this (all allowed).
  const [allowedModules, setAllowedModules] = React.useState<Set<string> | null>(null);
  React.useEffect(() => {
    if (!user || isAdmin) {
      setAllowedModules(null);
      setPrivateScanEnabled(true);
      return;
    }
    usersApi.getAllowedModules(user.id).then(data => {
      setAllowedModules(new Set(data.modules));
      setPrivateScanEnabled(data.modules.includes('private_network_scan'));
    }).catch(() => {
      setAllowedModules(null); // on error, allow all
      setPrivateScanEnabled(true);
    });
  }, [user, isAdmin]);

  const [target, setTarget] = useState('');
  const [targetError, setTargetError] = useState<string | null>(null);
  const [selectedModules, setSelectedModules] = useState<Set<ReconModule>>(
    new Set<ReconModule>([
      'host_discovery', 'port_scan', 'service_detection', 'whois', 'dns', 'ssl', 'http',
    ])
  );

  // When allowedModules is loaded, remove any modules the user doesn't have
  // permission for from the selection set.
  React.useEffect(() => {
    if (!allowedModules) return;
    setSelectedModules(prev => {
      const next = new Set<ReconModule>();
      prev.forEach(m => {
        if (allowedModules.has(m)) next.add(m);
      });
      return next;
    });
  }, [allowedModules]);
  const [portPreset, setPortPreset] = useState<PortPreset>('common');
  const [customPorts, setCustomPorts] = useState('');
  const [customPortsError, setCustomPortsError] = useState<string | null>(null);

  // Phase 17 — assignment-aware target selection.
  // Use a composite key (assignment_id:target_value) so that individual
  // assets from the same CLIENT assignment are independently selectable.
  // Previously all assets from one client shared the same assignment_id,
  // making it impossible to select just one.
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());

  const authorizedTargets = myTargets.data || [];
  const hasAssignments = authorizedTargets.length > 0;
  const assignmentMode = selectedKeys.size > 0;

  const targetKey = (t: { assignment_id: number; target_value: string }) =>
    `${t.assignment_id}:${t.target_value}`;

  // Filter the module list based on the user's permissions.  If
  // allowedModules is null (admin or not yet loaded), show all.
  const visibleModules = React.useMemo(() => {
    if (!allowedModules) return MODULE_OPTIONS;
    return MODULE_OPTIONS.filter(m => allowedModules.has(m.id));
  }, [allowedModules]);

  // ---- target validation (frontend mirror of backend logic) ----
  const validateTarget = (value: string): string | null => {
    if (!value.trim()) return 'A target is required.';
    if (value.length > 512) return 'Target exceeds maximum length of 512 characters.';
    const v = value.trim().toLowerCase();

    if (v.includes('://')) {
      const scheme = v.split('://', 1)[0];
      if (scheme !== 'http' && scheme !== 'https') {
        return `Unsupported URL scheme '${scheme}'. Only http and https are allowed.`;
      }
    }

    const internalHosts = ['localhost', 'db', 'redis', 'backend', 'frontend', 'nginx', 'worker', 'metadata.google.internal'];
    const hostPart = v.includes('://')
      ? (() => { try { return new URL(v).hostname; } catch { return ''; } })()
      : v.split('/')[0];
    if (internalHosts.includes(hostPart)) return 'The requested target is internal and not authorized.';

    const ipMatch = hostPart.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
    const cidrMatch = v.match(/^(\d{1,3}\.){3}\d{1,3}\/\d{1,2}$/);
    if (ipMatch) {
      const [_, a, b] = ipMatch;
      const ai = parseInt(a, 10), bi = parseInt(b, 10);
      if (ai === 127 || ai === 10 || ai === 0 || (ai === 169 && bi === 254) || (ai === 192 && bi === 168) || (ai === 172 && bi >= 16 && bi <= 31) || (ai === 100 && bi >= 64 && bi < 128)) {
        if (!privateScanEnabled) {
          return 'Private/internal IPs require either an explicit assignment or private-scan permission. Ask an administrator.';
        }
      }
    }
    if (cidrMatch) {
      const networkPart = v.split('/', 1)[0];
      const octets = networkPart.split('.').map(Number);
      const ai = octets[0], bi = octets[1];
      if (ai === 127 || ai === 10 || ai === 0 || (ai === 169 && bi === 254) || (ai === 192 && bi === 168) || (ai === 172 && bi >= 16 && bi <= 31) || (ai === 100 && bi >= 64 && bi < 128)) {
        if (!privateScanEnabled) {
          return 'Private/internal CIDR ranges require either an explicit assignment or private-scan permission.';
        }
      }
    }

    const isBareIp = !!ipMatch;
    const isCidr = !!cidrMatch;
    if (!v.includes('://') && !isBareIp && !isCidr && !v.match(/\.[a-z]{2,}$/)) {
      return 'Domain must include a valid top-level domain (e.g. .com, .org, .dev).';
    }
    return null;
  };

  const onTargetChange = (value: string) => {
    setTarget(value);
    setTargetError(validateTarget(value));
  };

  const toggleModule = (id: ReconModule) => {
    setSelectedModules(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const validateCustomPorts = (value: string): string | null => {
    if (!value.trim()) return 'At least one port is required.';
    const parts = value.split(',').map(p => p.trim()).filter(Boolean);
    if (parts.length === 0) return 'At least one port is required.';
    if (parts.length > 100) return 'Maximum of 100 ports allowed.';
    for (const p of parts) {
      const n = Number(p);
      if (!Number.isInteger(n) || n < 1 || n > 65535) {
        return `Port '${p}' is not a valid TCP port (must be 1..65535).`;
      }
    }
    return null;
  };

  const onCustomPortsChange = (value: string) => {
    setCustomPorts(value);
    if (portPreset === 'custom') setCustomPortsError(validateCustomPorts(value));
  };

  const toggleTarget = (t: { assignment_id: number; target_value: string }) => {
    const key = targetKey(t);
    setSelectedKeys(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const clearSelection = () => setSelectedKeys(new Set());

  // ---- submit ----
  const onSubmit = async () => {
    if (selectedModules.size === 0) {
      showToast('Select at least one recon module.', 'error');
      return;
    }

    let customPortsList: number[] | undefined;
    if (selectedModules.has('port_scan') && portPreset === 'custom') {
      const pErr = validateCustomPorts(customPorts);
      if (pErr) {
        setCustomPortsError(pErr);
        showToast(pErr, 'error');
        return;
      }
      customPortsList = customPorts.split(',').map(p => parseInt(p.trim(), 10)).filter(n => n >= 1 && n <= 65535);
    }

    // Phase 17 — submission path
    if (assignmentMode) {
      // Multi-target submission: queue one scan per selected target.
      // Each scan carries its assignment_id so the backend re-validates.
      const selected = authorizedTargets.filter(t => selectedKeys.has(targetKey(t)));
      if (selected.length === 0) {
        showToast('No targets selected.', 'error');
        return;
      }
      try {
        const scans = [];
        for (const t of selected) {
          const scan = await createScan.mutateAsync({
            target: t.target_value,
            modules: Array.from(selectedModules),
            port_preset: selectedModules.has('port_scan') ? portPreset : undefined,
            custom_ports: customPortsList,
            assignment_id: t.assignment_id,
          });
          scans.push(scan);
        }
        showToast(`${scans.length} scan(s) queued.`, 'success');
        navigate(ROUTES.SCAN_DETAILS_BY_ID(scans[0].id));
      } catch (err: any) {
        const msg = err?.response?.data?.message || 'Failed to start scan.';
        showToast(msg, 'error');
      }
      return;
    }

    // Manual mode
    const tErr = validateTarget(target);
    if (tErr) {
      setTargetError(tErr);
      showToast(tErr, 'error');
      return;
    }

    try {
      const scan = await createScan.mutateAsync({
        target: target.trim(),
        modules: Array.from(selectedModules),
        port_preset: selectedModules.has('port_scan') ? portPreset : undefined,
        custom_ports: customPortsList,
      });
      showToast(`Scan #${scan.id} queued for ${scan.target}`, 'success');
      navigate(ROUTES.SCAN_DETAILS_BY_ID(scan.id));
    } catch (err: any) {
      const message = err?.response?.data?.message || 'Failed to start scan.';
      showToast(message, 'error');
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-display font-bold text-dark-50">Network Reconnaissance</h1>
        <p className="text-dark-400 mt-1">
          Perform authorized reconnaissance against a target. All modules run server-side under strict
          SSRF protection, rate limits, and audit logging.
        </p>
      </div>

      {/* Phase 17 — private-scan permission banner */}
      <PrivateScanBanner isAdmin={isAdmin} enabled={privateScanEnabled} />

      {/* Phase 17 — Assigned targets selector */}
      {hasAssignments && (
        <div className="glass-panel border-glow-top rounded-xl p-5 sm:p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-primary-400 shadow-glow-sm" />
              <h2 className="text-base font-display font-semibold text-dark-50">Assigned Targets</h2>
              <span className="text-xs text-dark-500">
                ({selectedKeys.size} selected)
              </span>
            </div>
            {assignmentMode && (
              <button
                onClick={clearSelection}
                className="text-xs text-dark-400 hover:text-primary-300 transition-colors flex items-center gap-1"
              >
                <XMarkIcon className="w-3 h-3" />
                Clear selection (switch to manual input)
              </button>
            )}
          </div>
          <p className="text-xs text-dark-400">
            Select one or more authorized targets to scan.  Each target is individually selectable —
            you can pick a single asset from a client without selecting the whole client.
            Backend re-validates every selection.
          </p>
          {myTargets.isLoading ? (
            <div className="flex justify-center py-4"><Spinner /></div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-72 overflow-y-auto">
              {authorizedTargets.map((t, idx) => {
                const key = targetKey(t);
                const selected = selectedKeys.has(key);
                return (
                  <button
                    key={key || idx}
                    type="button"
                    onClick={() => toggleTarget(t)}
                    className={cn(
                      'text-left rounded-lg border p-3 transition-all',
                      selected
                        ? 'border-primary-500/50 bg-primary-500/10 shadow-glow-sm'
                        : 'border-dark-700 bg-dark-900/40 hover:border-primary-500/30',
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge variant={t.ownership_type === 'CLIENT' ? 'info' : 'primary'} noDot>
                            {t.ownership_type === 'CLIENT' ? 'Client' : 'Direct'}
                          </Badge>
                          <Badge variant={t.target_type === 'IP' ? 'neutral' : 'neutral'} noDot>
                            {t.target_type}
                          </Badge>
                        </div>
                        <div className="text-sm font-mono text-dark-100 mt-1 truncate">
                          {t.target_value}
                        </div>
                        <div className="text-xs text-dark-500 truncate">
                          {t.client_name ? `${t.client_name} — ` : ''}{t.label}
                        </div>
                      </div>
                      {selected && <CheckCircleIcon className="w-5 h-5 text-primary-400 shrink-0" />}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Target Input — manual mode only */}
      {!assignmentMode && (
        <div className="glass-panel border-glow-top rounded-xl p-5 sm:p-6 space-y-4">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-primary-400 shadow-glow-sm" />
            <h2 className="text-base font-display font-semibold text-dark-50">Target</h2>
            {hasAssignments && (
              <span className="text-xs text-dark-500 ml-2">
                (no assigned target selected — manual entry)
              </span>
            )}
          </div>
          <Input
            id="target"
            label="Target domain, IP, URL, or authorized CIDR"
            placeholder="example.com  |  8.8.8.8  |  https://example.com  |  8.0.0.0/29"
            value={target}
            onChange={(e) => onTargetChange(e.target.value)}
            error={targetError ?? undefined}
          />
          <div className="flex flex-wrap gap-2">
            <Badge variant="info" noDot>DOMAIN</Badge>
            <Badge variant="info" noDot>IP</Badge>
            <Badge variant="info" noDot>URL</Badge>
            <Badge variant="info" noDot>CIDR (authorized ranges only)</Badge>
          </div>
        </div>
      )}

      {/* Module Selection */}
      <div className="glass-panel border-glow-top rounded-xl p-5 sm:p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-primary-400 shadow-glow-sm" />
            <h2 className="text-base font-display font-semibold text-dark-50">Modules</h2>
            {allowedModules && allowedModules.size < MODULE_OPTIONS.length && (
              <span className="text-xs text-amber-400 ml-2">
                ({MODULE_OPTIONS.length - allowedModules.size} restricted by admin)
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setSelectedModules(new Set(visibleModules.map(m => m.id)))}
              className="text-xs text-primary-300 hover:text-primary-200 transition-colors"
            >
              Select all
            </button>
            <span className="text-dark-600">|</span>
            <button
              onClick={() => setSelectedModules(new Set())}
              className="text-xs text-dark-400 hover:text-dark-200 transition-colors"
            >
              Clear
            </button>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {visibleModules.map((m) => {
            const active = selectedModules.has(m.id);
            const Icon = m.icon;
            return (
              <button
                key={m.id}
                type="button"
                onClick={() => toggleModule(m.id)}
                className={cn(
                  'group relative text-left rounded-xl p-4 border transition-all duration-200',
                  active
                    ? 'bg-primary-500/10 border-primary-500/40 shadow-glow-sm'
                    : 'bg-dark-900/60 border-dark-700 hover:border-primary-500/30 hover:bg-dark-800/60'
                )}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className={cn('p-2 rounded-lg border transition-colors',
                    active
                      ? 'bg-primary-500/20 border-primary-500/40 text-primary-300'
                      : 'bg-dark-800 border-dark-700 text-dark-400 group-hover:text-primary-300')}>
                    <Icon className="w-5 h-5" />
                  </div>
                  {active && <CheckCircleIcon className="w-5 h-5 text-primary-400" />}
                </div>
                <h3 className="text-sm font-display font-semibold text-dark-50 mb-1">{m.name}</h3>
                <p className="text-xs text-dark-400 leading-relaxed">{m.description}</p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Port Configuration */}
      {selectedModules.has('port_scan') && (
        <div className="glass-panel border-glow-top rounded-xl p-5 sm:p-6 space-y-4">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-primary-400 shadow-glow-sm" />
            <h2 className="text-base font-display font-semibold text-dark-50">Port Configuration</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {(['common', 'web', 'custom'] as PortPreset[]).map((preset) => (
              <button
                key={preset}
                type="button"
                onClick={() => {
                  setPortPreset(preset);
                  if (preset === 'custom') setCustomPortsError(validateCustomPorts(customPorts));
                  else setCustomPortsError(null);
                }}
                className={cn(
                  'text-left rounded-xl p-3 border transition-all',
                  portPreset === preset
                    ? 'bg-primary-500/10 border-primary-500/40 shadow-glow-sm'
                    : 'bg-dark-900/60 border-dark-700 hover:border-primary-500/30'
                )}
              >
                <div className="text-sm font-display font-semibold text-dark-50 capitalize">{preset} Ports</div>
                <div className="text-xs text-dark-400 mt-1">
                  {preset === 'common' && '21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 587, 993, 995, 3306, 3389, 5432, 6379, 8080, 8443'}
                  {preset === 'web' && '80, 443, 3000, 5000, 8000, 8080, 8443, 9000'}
                  {preset === 'custom' && 'Up to 100 user-specified ports (1..65535).'}
                </div>
              </button>
            ))}
          </div>
          {portPreset === 'custom' && (
            <Input
              id="custom-ports"
              label="Custom ports (comma-separated)"
              placeholder="22, 80, 443, 8080"
              value={customPorts}
              onChange={(e) => onCustomPortsChange(e.target.value)}
              error={customPortsError ?? undefined}
            />
          )}
        </div>
      )}

      {/* Submit */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <p className="text-xs text-dark-500">
          {selectedModules.size} module(s) selected ·{' '}
          {assignmentMode ? (
            <span className="text-primary-300">
              {selectedKeys.size} target(s) selected
            </span>
          ) : (
            <>
              Target: <span className="text-dark-300 font-mono">{target || '—'}</span>
            </>
          )}
        </p>
        <Button
          size="lg"
          onClick={onSubmit}
          isLoading={createScan.isPending}
          disabled={(!assignmentMode && (!target || !!targetError)) || selectedModules.size === 0}
        >
          <SignalIcon className="w-5 h-5 mr-2" />
          {assignmentMode ? `Start ${selectedKeys.size} Scan(s)` : 'Start Reconnaissance'}
        </Button>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Private scan banner
// ---------------------------------------------------------------------------
const PrivateScanBanner: React.FC<{ isAdmin: boolean; enabled: boolean }> = ({ isAdmin, enabled }) => {
  if (enabled) {
    return (
      <div className="flex items-start gap-2 p-3 rounded-lg bg-emerald-900/20 border border-emerald-600/40">
        <ShieldCheckIcon className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
        <div className="text-xs text-emerald-300">
          <strong>Private network scanning is enabled</strong>
          {isAdmin ? ' for your administrator account.' : ' for your account.'} You may scan
          private/internal IPs and CIDRs.  Assigned private targets remain authorised even when this
          is disabled.
        </div>
      </div>
    );
  }
  return (
    <div className="flex items-start gap-2 p-3 rounded-lg bg-amber-900/20 border border-amber-600/40">
      <ShieldExclamationIcon className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
      <div className="text-xs text-amber-300">
        <strong>Private network scanning is disabled</strong>
        {isAdmin ? ' for your administrator account.' : ' for your account.'} You may still scan
        private targets that have been explicitly assigned to you.  Public targets remain fully
        available.
      </div>
    </div>
  );
};
