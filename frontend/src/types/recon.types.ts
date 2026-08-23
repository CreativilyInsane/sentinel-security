// frontend/src/types/recon.types.ts
// TypeScript types for the Network Recon Dashboard API.
// These mirror the Pydantic schemas in backend/app/recon/schemas/.

// ---------------------------------------------------------------------------
// Enums (string-literal unions to avoid runtime overhead)
// ---------------------------------------------------------------------------
export type ScanStatus =
  | 'QUEUED'
  | 'RUNNING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED';

export type ScanModuleStatusValue =
  | 'QUEUED'
  | 'RUNNING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED';

export type TargetType = 'DOMAIN' | 'IP' | 'URL' | 'CIDR';

export type ReconModule =
  | 'host_discovery'
  | 'port_scan'
  | 'service_detection'
  | 'whois'
  | 'dns'
  | 'ssl'
  | 'http'
  | 'screenshot';

export type ResultType =
  | 'HOST_DISCOVERY'
  | 'PORT_SCAN'
  | 'SERVICE'
  | 'WHOIS'
  | 'DNS'
  | 'SSL'
  | 'HTTP'
  | 'SCREENSHOT';

export type PortPreset = 'common' | 'web' | 'custom';

// ---------------------------------------------------------------------------
// Per-module status (Phase 19 — real-time scan progress)
// ---------------------------------------------------------------------------
export interface ScanModuleStatus {
  module_name: string;
  status: ScanModuleStatusValue;
  progress: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

// ---------------------------------------------------------------------------
// Scan
// ---------------------------------------------------------------------------
export interface Scan {
  id: number;
  user_id: number;
  name: string | null;
  target: string;
  target_type: TargetType;
  status: ScanStatus;
  modules: ReconModule[];
  port_preset: PortPreset | null;
  custom_ports: number[] | null;
  progress: number;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  celery_task_id: string | null;
  created_at: string;
  updated_at: string;
  // Phase 17 ownership
  ownership_type?: 'CLIENT' | 'ASSIGNED_TARGET' | 'USER_MANUAL';
  client_id?: number | null;
  client_asset_id?: number | null;
  assignment_id?: number | null;
  client_name?: string | null;
  // Phase 19 — per-module status (real-time scan UI)
  module_statuses?: ScanModuleStatus[];
}

export interface ScanSummary {
  id: number;
  user_id: number;
  name: string | null;
  target: string;
  target_type: TargetType;
  status: ScanStatus;
  progress: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  modules: ReconModule[];
  // Phase 17 ownership
  ownership_type?: 'CLIENT' | 'ASSIGNED_TARGET' | 'USER_MANUAL';
  client_id?: number | null;
  assignment_id?: number | null;
  client_name?: string | null;
  user_username?: string | null;
}

export interface ScanCreatePayload {
  target: string;
  modules: ReconModule[];
  name?: string;
  port_preset?: PortPreset;
  custom_ports?: number[];
  // Phase 17 — optional assignment context (validated server-side)
  assignment_id?: number;
}

export interface CancelResponse {
  id: number;
  status: ScanStatus;
  message: string;
}

// ---------------------------------------------------------------------------
// Results
// ---------------------------------------------------------------------------
export interface HostDiscoveryResult {
  hosts: Array<{
    host: string;
    ip: string | null;
    hostname: string | null;
    status: string;
    latency_ms: number | null;
    error?: string;
  }>;
}

export interface PortScanResult {
  scans: Array<{
    host: string;
    ip: string;
    ports: Array<{
      port: number;
      state: string;
      protocol: string;
      service_guess: string;
      latency_ms: number | null;
    }>;
  }>;
}

export interface ServiceDetectionResult {
  scans: Array<{
    host: string;
    ip: string;
    services: Array<{
      port: number;
      service: string;
      protocol: string;
      banner: string | null;
      version: string | null;
      confidence: string;
    }>;
  }>;
}

export interface DnsRecord {
  record_type: string;
  name: string;
  values: string[];
  ttl: number;
}

export interface DnsResult {
  target: string;
  records: DnsRecord[];
}

export interface WhoisResult {
  target: string;
  available: boolean;
  error?: string;
  domain?: string | string[];
  registrar?: string | string[];
  creation_date?: string | string[];
  expiration_date?: string | string[];
  updated_date?: string | string[];
  name_servers?: string[];
  status?: string[];
  registrant?: {
    name?: string;
    organization?: string;
    country?: string;
    state?: string;
    city?: string;
    address?: string;
    email?: string | string[];
  } | null;
}

export interface SslResult {
  hostname: string;
  port: number;
  available: boolean;
  error?: string;
  tls_version?: string | null;
  certificate_subject?: string;
  certificate_issuer?: string;
  valid_from?: string;
  valid_until?: string;
  days_remaining?: number | null;
  serial_number?: string;
  signature_algorithm?: string;
  public_key_algorithm?: string;
  sans?: string[];
  chain_status?: string;
  expiration_status?: 'Valid' | 'Expiring Soon' | 'Expired' | 'Unknown';
}

export interface SecurityHeaderAssessment {
  header: string;
  present: boolean;
  value: string | null;
  severity: 'good' | 'info' | 'low' | 'medium' | 'high';
}

export interface HttpAnalysisResult {
  url: string;
  available: boolean;
  error?: string;
  status_code?: number;
  server?: string | null;
  content_type?: string | null;
  content_length?: number;
  headers?: Record<string, string>;
  body_preview?: string;
  security_headers?: SecurityHeaderAssessment[];
  redirected?: boolean;
  final_url?: string;
}

export interface ScreenshotResult {
  url: string;
  captured: boolean;
  error?: string;
  screenshot_id?: string;
  screenshot_url?: string;
  content_type?: string;
}

export interface ScanResultGrouped {
  scan_id: number;
  host_discovery: HostDiscoveryResult[];
  port_scan: PortScanResult[];
  service: ServiceDetectionResult[];
  whois: WhoisResult | Record<string, never>;
  dns: DnsResult[];
  ssl: SslResult | Record<string, never>;
  http: HttpAnalysisResult | Record<string, never>;
  screenshot: ScreenshotResult[];
  errors: Array<{ module: string; error: string }>;
}

// ---------------------------------------------------------------------------
// Assets
// ---------------------------------------------------------------------------
export interface Asset {
  id: number;
  user_id: number;
  scan_id: number | null;
  host: string;
  ip_address: string | null;
  hostname: string | null;
  port: number | null;
  protocol: string | null;
  service: string | null;
  status: string | null;
  first_seen: string;
  last_seen: string;
  metadata: Record<string, unknown>;
  // Phase 17 ownership
  ownership_type?: 'CLIENT' | 'ASSIGNED_TARGET' | 'USER_MANUAL';
  client_id?: number | null;
  client_asset_id?: number | null;
  assignment_id?: number | null;
  client_name?: string | null;
  can_delete?: boolean;
}

// ---------------------------------------------------------------------------
// Stats (dashboard)
// ---------------------------------------------------------------------------
export interface ReconStats {
  total_scans: number;
  running_scans: number;
  completed_scans: number;
  total_assets: number;
  open_ports: number;
  recent_scans: Array<{
    id: number;
    target: string;
    status: ScanStatus;
    progress: number;
    created_at: string | null;
    completed_at: string | null;
  }>;
  recent_assets: Array<{
    id: number;
    host: string;
    ip_address: string | null;
    port: number | null;
    service: string | null;
    last_seen: string | null;
  }>;
}

export interface ReportMetadata {
  scan_id: number;
  target: string;
  status: ScanStatus;
  formats: string[];
  created_at: string;
  completed_at: string | null;
}
