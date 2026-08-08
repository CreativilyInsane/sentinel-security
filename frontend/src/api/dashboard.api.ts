// frontend/src/api/dashboard.api.ts
import { apiClient } from './client';
import type { DashboardData } from '@/types/dashboard.types';
import type { StandardResponse } from '@/types/common.types';

export const dashboardApi = {
  getDashboardData: async (): Promise<DashboardData> => {
    const res = await apiClient.get<StandardResponse<DashboardData>>('/dashboard/');
    return res.data.data;
  },
};