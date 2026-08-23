// frontend/src/api/clients.api.ts
import { apiClient } from './client';
import type { StandardResponse } from '@/types/common.types';
import type {
  Client,
  ClientWithStats,
  ClientCreatePayload,
  ClientUpdatePayload,
  ClientAsset,
  ClientAssetCreatePayload,
  ClientAssetUpdatePayload,
  TargetAssignment,
  AssignClientPayload,
  AssignDirectTargetPayload,
  AssignmentUpdatePayload,
  AssignmentNotification,
  AuthorizedTarget,
  MyClient,
} from '@/types/client.types';

export const clientsApi = {
  // ---- Clients (admin) ----
  listClients: async (params?: {
    skip?: number; limit?: number; search?: string; is_active?: boolean;
  }): Promise<ClientWithStats[]> => {
    const res = await apiClient.get<StandardResponse<ClientWithStats[]>>('/clients', { params });
    return res.data.data;
  },

  getClient: async (clientId: number): Promise<Client> => {
    const res = await apiClient.get<StandardResponse<Client>>(`/clients/${clientId}`);
    return res.data.data;
  },

  createClient: async (payload: ClientCreatePayload): Promise<Client> => {
    const res = await apiClient.post<StandardResponse<Client>>('/clients', payload);
    return res.data.data;
  },

  updateClient: async (clientId: number, payload: ClientUpdatePayload): Promise<Client> => {
    const res = await apiClient.put<StandardResponse<Client>>(`/clients/${clientId}`, payload);
    return res.data.data;
  },

  deleteClient: async (clientId: number): Promise<void> => {
    await apiClient.delete(`/clients/${clientId}`);
  },

  // ---- Client Assets (admin) ----
  listClientAssets: async (clientId: number): Promise<ClientAsset[]> => {
    const res = await apiClient.get<StandardResponse<ClientAsset[]>>(`/clients/${clientId}/assets`);
    return res.data.data;
  },

  createClientAsset: async (clientId: number, payload: ClientAssetCreatePayload): Promise<ClientAsset> => {
    const res = await apiClient.post<StandardResponse<ClientAsset>>(`/clients/${clientId}/assets`, payload);
    return res.data.data;
  },

  updateClientAsset: async (clientId: number, assetId: number, payload: ClientAssetUpdatePayload): Promise<ClientAsset> => {
    const res = await apiClient.put<StandardResponse<ClientAsset>>(`/clients/${clientId}/assets/${assetId}`, payload);
    return res.data.data;
  },

  deleteClientAsset: async (clientId: number, assetId: number): Promise<void> => {
    await apiClient.delete(`/clients/${clientId}/assets/${assetId}`);
  },

  // ---- Assignments (admin) ----
  assignClient: async (payload: AssignClientPayload): Promise<TargetAssignment> => {
    const res = await apiClient.post<StandardResponse<TargetAssignment>>('/targets/assign/client', payload);
    return res.data.data;
  },

  assignDirectTarget: async (payload: AssignDirectTargetPayload): Promise<TargetAssignment> => {
    const res = await apiClient.post<StandardResponse<TargetAssignment>>('/targets/assign/direct', payload);
    return res.data.data;
  },

  listAssignments: async (params?: {
    skip?: number; limit?: number; user_id?: number; client_id?: number;
  }): Promise<TargetAssignment[]> => {
    const res = await apiClient.get<StandardResponse<TargetAssignment[]>>('/targets/assignments', { params });
    return res.data.data;
  },

  updateAssignment: async (assignmentId: number, payload: AssignmentUpdatePayload): Promise<TargetAssignment> => {
    const res = await apiClient.put<StandardResponse<TargetAssignment>>(`/targets/assignments/${assignmentId}`, payload);
    return res.data.data;
  },

  deleteAssignment: async (assignmentId: number): Promise<void> => {
    await apiClient.delete(`/targets/assignments/${assignmentId}`);
  },

  // ---- User-side endpoints ----
  myTargets: async (): Promise<AuthorizedTarget[]> => {
    const res = await apiClient.get<StandardResponse<AuthorizedTarget[]>>('/targets/my-targets');
    return res.data.data;
  },

  myClients: async (): Promise<MyClient[]> => {
    const res = await apiClient.get<StandardResponse<MyClient[]>>('/targets/my-clients');
    return res.data.data;
  },

  myNotifications: async (unreadOnly: boolean = false): Promise<AssignmentNotification[]> => {
    const res = await apiClient.get<StandardResponse<AssignmentNotification[]>>('/targets/notifications', {
      params: { unread_only: unreadOnly },
    });
    return res.data.data;
  },

  myUnreadCount: async (): Promise<number> => {
    const res = await apiClient.get<StandardResponse<{ count: number }>>('/targets/notifications/unread-count');
    return res.data.data.count;
  },

  markNotificationsRead: async (notificationIds?: number[]): Promise<number> => {
    const res = await apiClient.post<StandardResponse<{ updated: number }>>('/targets/notifications/read', {
      notification_ids: notificationIds,
    });
    return res.data.data.updated;
  },

  // ---- Active targets (user-level selection) ----
  listActiveTargets: async (): Promise<Array<{
    target_key: string; assignment_id: number; target_value: string; is_active: boolean;
  }>> => {
    const res = await apiClient.get<StandardResponse<any[]>>('/targets/active');
    return res.data.data;
  },

  toggleActiveTarget: async (
    assignmentId: number,
    targetValue: string,
    isActive: boolean,
  ): Promise<{ target_key: string; is_active: boolean }> => {
    const res = await apiClient.post<StandardResponse<{ target_key: string; is_active: boolean }>>(
      '/targets/active/toggle',
      { assignment_id: assignmentId, target_value: targetValue, is_active: isActive },
    );
    return res.data.data;
  },

  // ---- Phase 19 — per-user client/asset enable/disable toggles ----
  toggleClientPermission: async (clientId: number, enabled: boolean): Promise<{ client_id: number; enabled: boolean }> => {
    const res = await apiClient.post<StandardResponse<{ client_id: number; enabled: boolean }>>(
      `/targets/clients/${clientId}/toggle`,
      { enabled },
    );
    return res.data.data;
  },

  toggleAssetPermission: async (assetId: number, enabled: boolean): Promise<{ asset_id: number; enabled: boolean }> => {
    const res = await apiClient.post<StandardResponse<{ asset_id: number; enabled: boolean }>>(
      `/targets/assets/${assetId}/toggle`,
      { enabled },
    );
    return res.data.data;
  },

  // ---- Client-level merged report (admin or assigned user) ----
  /**
   * Issue a short-lived signed URL token for opening the merged client
   * report in a new browser tab/iframe.  This is the preferred path
   * over the legacy ``getClientReportHtmlUrl`` because the latter
   * cannot attach the JWT to a top-level navigation.
   */
  issueClientReportToken: async (clientId: number, fmt: 'html' | 'pdf' = 'html'): Promise<{ token: string; url: string; expires_in: number }> => {
    const res = await apiClient.post<StandardResponse<{ token: string; url: string; expires_in: number }>>(
      `/recon/clients/${clientId}/report/token`,
      null,
      { params: { fmt } },
    );
    return res.data.data;
  },

  fetchClientReportHtml: async (clientId: number): Promise<Blob> => {
    const res = await apiClient.get(`/recon/clients/${clientId}/report/html`, {
      responseType: 'blob',
    });
    return res.data;
  },

  // Legacy URL builder — kept for backwards compatibility, but new code
  // should prefer fetchClientReportHtml / issueClientReportToken.
  getClientReportHtmlUrl: (clientId: number): string => `/api/v1/recon/clients/${clientId}/report/html`,

  listClientScans: async (clientId: number): Promise<Array<{
    id: number; target: string; status: string; ownership_type: string;
    started_at: string | null; completed_at: string | null; created_at: string | null;
  }>> => {
    const res = await apiClient.get<StandardResponse<any[]>>(`/recon/clients/${clientId}/scans`);
    return res.data.data;
  },
};
