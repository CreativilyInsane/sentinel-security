// frontend/src/types/dashboard.types.ts
export interface DashboardStats {
  total_assets: number;
  last_scan: string;
  reports_generated: number;
  system_status: string;
}

export interface ActivityItem {
  id: number;
  type: string;
  description: string;
  timestamp: string;
}

export interface DashboardData {
  stats: DashboardStats;
  recent_activity: ActivityItem[];
}