// frontend/src/types/client.types.ts
// Phase 17 — Client + ClientAsset + TargetAssignment types

export type ClientAssetType = 'IP' | 'IP_RANGE' | 'DOMAIN';
export type AssignmentType = 'CLIENT' | 'DIRECT_TARGET';
export type OwnershipType = 'CLIENT' | 'ASSIGNED_TARGET' | 'USER_MANUAL';
export type AssignmentNotificationType =
  | 'CLIENT_ASSIGNED'
  | 'TARGET_ASSIGNED'
  | 'TARGET_REMOVED'
  | 'CLIENT_REMOVED';

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------
export interface Client {
  id: number;
  name: string;
  description: string | null;
  company_name: string | null;
  is_active: boolean;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface ClientWithStats extends Client {
  asset_count: number;
  assigned_user_count: number;
  active_assignment_count: number;
}

export interface ClientCreatePayload {
  name: string;
  company_name?: string | null;
  description?: string | null;
  is_active?: boolean;
}

export interface ClientUpdatePayload {
  name?: string;
  company_name?: string | null;
  description?: string | null;
  is_active?: boolean;
}

// ---------------------------------------------------------------------------
// ClientAsset
// ---------------------------------------------------------------------------
export interface ClientAsset {
  id: number;
  client_id: number;
  asset_type: ClientAssetType;
  ip_address: string | null;
  cidr: string | null;
  domain: string | null;
  name: string | null;
  description: string | null;
  network_name: string | null;
  vlan_name: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ClientAssetCreatePayload {
  asset_type: ClientAssetType;
  ip_address?: string | null;
  cidr?: string | null;
  domain?: string | null;
  name?: string | null;
  description?: string | null;
  network_name?: string | null;
  vlan_name?: string | null;
  is_active?: boolean;
}

export interface ClientAssetUpdatePayload {
  asset_type?: ClientAssetType;
  ip_address?: string | null;
  cidr?: string | null;
  domain?: string | null;
  name?: string | null;
  description?: string | null;
  network_name?: string | null;
  vlan_name?: string | null;
  is_active?: boolean;
}

// ---------------------------------------------------------------------------
// TargetAssignment
// ---------------------------------------------------------------------------
export interface TargetAssignment {
  id: number;
  user_id: number;
  client_id: number | null;
  client_asset_id: number | null;
  assignment_type: AssignmentType;
  target_type: string; // 'CLIENT' | 'IP' | 'IP_RANGE'
  target_value: string;
  target_label: string | null;
  assigned_by: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  // joined fields
  client_name: string | null;
  client_asset_name: string | null;
  assigner_username: string | null;
  user_username: string | null;
}

export interface AssignClientPayload {
  user_id: number;
  client_id: number;
}

export interface AssignDirectTargetPayload {
  user_id: number;
  target_type: 'IP' | 'IP_RANGE' | 'DOMAIN';
  target_value: string;
  target_label?: string | null;
  client_id?: number | null;
  client_asset_id?: number | null;
}

export interface AssignmentUpdatePayload {
  is_active?: boolean;
  target_label?: string | null;
}

// ---------------------------------------------------------------------------
// Authorized target (returned by /targets/my-targets)
// ---------------------------------------------------------------------------
export interface AuthorizedTarget {
  assignment_id: number;
  ownership_type: OwnershipType;
  client_id: number | null;
  client_asset_id: number | null;
  target_type: 'IP' | 'CIDR' | 'DOMAIN' | 'CLIENT';
  target_value: string;
  label: string;
  client_name: string | null;
}

// ---------------------------------------------------------------------------
// Assignment notification
// ---------------------------------------------------------------------------
export interface AssignmentNotification {
  id: number;
  user_id: number;
  assignment_id: number | null;
  type: AssignmentNotificationType;
  message: string | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// My-clients (returned by /targets/my-clients)
//
// The endpoint merges BOTH ``CLIENT`` assignments and ``DIRECT_TARGET``
// assignments under their parent Client, so the User UI has a single
// consistent grouping instead of a separate "Direct Targets" section.
// ---------------------------------------------------------------------------
export interface MyClientAsset {
  // id is null for "synthetic" assets — i.e. ad-hoc direct targets whose
  // value is NOT one of the client's existing ClientAsset rows (e.g. the
  // admin typed an IP/CIDR/Domain directly into the direct-target form).
  id: number | null;
  asset_type: ClientAssetType;
  ip_address: string | null;
  cidr: string | null;
  domain: string | null;
  name: string | null;
  description: string | null;
  network_name: string | null;
  vlan_name: string | null;
  value: string;
  // Phase 19 — per-user, per-asset toggle (default-open: missing == true).
  enabled?: boolean;
  // How this asset reached the user — "CLIENT" means the entire Client
  // is assigned so all of its assets are visible.  "DIRECT_TARGET" means
  // only this specific asset was directly assigned to the user.
  assigned_via?: 'CLIENT' | 'DIRECT_TARGET';
  // The TargetAssignment row id that backs this asset's visibility.
  // Used by the frontend to toggle the active-target visibility and to
  // know which assignment to disable/enable.
  assignment_id?: number | null;
}

export interface MyClient {
  // id is null for the synthetic "Direct Targets" pseudo-client that
  // surfaces orphan direct-target assignments (those without a client_id).
  id: number | null;
  name: string;
  description: string | null;
  company_name: string | null;
  assets: MyClientAsset[];
  // Phase 19 — per-user, per-client toggle (default-open: missing == true).
  enabled?: boolean;
}
