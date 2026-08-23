// frontend/src/routes/paths.ts
export const ROUTES = {
  LOGIN: '/login',
  DASHBOARD: '/dashboard',
  // Phase 17 — role-aware navigation
  CLIENTS: '/clients',                  // admin only
  CLIENT_DETAIL: '/clients/:clientId',  // admin only
  CLIENT_DETAIL_BY_ID: (clientId: number | string) => `/clients/${clientId}`,
  TARGETS: '/targets',                  // regular users
  NETWORK_SCAN: '/network-scan',
  SCAN_DETAILS: '/scans/:scanId',
  SCAN_DETAILS_BY_ID: (scanId: number | string) => `/scans/${scanId}`,
  PREVIOUS_SCANS: '/previous-scans',
  ASSETS: '/assets',
  ASSET_DETAILS: '/assets/:assetId',
  ASSET_DETAILS_BY_ID: (assetId: number | string) => `/assets/${assetId}`,
  ASSETS_BY_HOST: '/assets/host/:host',
  ASSETS_BY_HOST_VALUE: (host: string) => `/assets/host/${encodeURIComponent(host)}`,
  REPORTS: '/reports',
  USERS: '/users',
  // Dedicated User Module Settings page (admin only)
  USER_MODULE_SETTINGS: '/admin/users/:userId/modules',
  USER_MODULE_SETTINGS_BY_ID: (userId: number | string) => `/admin/users/${userId}/modules`,
  // Dedicated Admin Assignments page (admin only) — explicit management
  // of full-Client assignments and direct-target assignments to users.
  ASSIGNMENTS: '/admin/assignments',
  PROFILE: '/profile',
  SETTINGS: '/settings',
};
