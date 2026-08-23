// frontend/src/types/user.types.ts
export interface Role {
  id: number;
  name: string;
}

export interface User {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
  // NOTE: private_scan_enabled has been REMOVED — private-network scan
  // access is now controlled by the per-user `private_network_scan`
  // module permission on the User Module Settings page.
  role: Role;
  created_at: string;
  updated_at: string;
}

export interface UserCreatePayload {
  username: string;
  email: string;
  password: string;
  role_name: string;
}

export interface UserUpdatePayload {
  email?: string;
  password?: string;
  role_name?: string;
  is_active?: boolean;
}

// ---- Module permissions ---------------------------------------------------
export interface ModulePermissionItem {
  module_name: string;
  is_allowed: boolean;
}

export interface ModulePermissionsRead {
  user_id: number;
  permissions: ModulePermissionItem[];
  is_default_open: boolean;
  // Phase 19 — computed parent Network Module toggle (True if ANY of
  // the 8 Network submodules is True).  Not stored in the DB; the
  // frontend uses this to render the parent toggle state.
  network_module_enabled?: boolean;
}
