// frontend/src/api/recon.api.ts
import { apiClient } from './client';
import { storage } from '@/utils/storage';
import type { StandardResponse } from '@/types/common.types';
import type {
  Scan,
  ScanSummary,
  ScanCreatePayload,
  ScanResultGrouped,
  CancelResponse,
  Asset,
  ReconStats,
  ReportMetadata,
} from '@/types/recon.types';

export interface ReportTokenResponse {
  token: string;
  url: string;
  expires_in: number;
}

export const reconApi = {
  // ---- Scans ----
  createScan: async (payload: ScanCreatePayload): Promise<Scan> => {
    const res = await apiClient.post<StandardResponse<Scan>>('/recon/scans', payload);
    return res.data.data;
  },

  listScans: async (params?: {
    skip?: number;
    limit?: number;
    status?: string;
    target?: string;
  }): Promise<ScanSummary[]> => {
    const res = await apiClient.get<StandardResponse<ScanSummary[]>>('/recon/scans', { params });
    return res.data.data;
  },

  getScan: async (scanId: number): Promise<Scan> => {
    const res = await apiClient.get<StandardResponse<Scan>>(`/recon/scans/${scanId}`);
    return res.data.data;
  },

  getScanResults: async (scanId: number): Promise<ScanResultGrouped> => {
    const res = await apiClient.get<StandardResponse<ScanResultGrouped>>(`/recon/scans/${scanId}/results`);
    return res.data.data;
  },

  cancelScan: async (scanId: number): Promise<CancelResponse> => {
    const res = await apiClient.post<StandardResponse<CancelResponse>>(`/recon/scans/${scanId}/cancel`);
    return res.data.data;
  },

  deleteScan: async (scanId: number): Promise<void> => {
    await apiClient.delete(`/recon/scans/${scanId}`);
  },

  /**
   * Returns an EventSource URL for the scan-events SSE stream.  The
   * browser's EventSource API cannot set custom headers, so we pass the
   * JWT as a query param.  The backend endpoint accepts either a JWT
   * (Authorization header) or a ``?token=`` query param.
   *
   * Note: we deliberately use the access token here (short-lived) to
   * avoid leaking the refresh token in a URL.
   */
  scanEventsUrl: (scanId: number): string => {
    const token = storage.getAccessToken();
    const base = import.meta.env.VITE_API_URL || '/api/v1';
    return `${base}/recon/scans/${scanId}/events?token=${encodeURIComponent(token || '')}`;
  },

  // ---- Reports ----
  getReportMetadata: async (scanId: number): Promise<ReportMetadata> => {
    const res = await apiClient.get<StandardResponse<ReportMetadata>>(`/recon/scans/${scanId}/report`);
    return res.data.data;
  },

  /**
   * Issue a short-lived signed URL token for opening a scan report in a
   * new browser tab/iframe.  The token bypasses the JWT requirement on
   * the report endpoint for one use only (5-minute TTL).
   */
  issueScanReportToken: async (scanId: number, fmt: 'html' | 'pdf' = 'html'): Promise<ReportTokenResponse> => {
    const res = await apiClient.post<StandardResponse<ReportTokenResponse>>(
      `/recon/scans/${scanId}/report/token`,
      null,
      { params: { fmt } },
    );
    return res.data.data;
  },

  /**
   * Issue a short-lived signed URL token for opening a merged client
   * report in a new browser tab/iframe.
   */
  issueClientReportToken: async (clientId: number, fmt: 'html' | 'pdf' = 'html'): Promise<ReportTokenResponse> => {
    const res = await apiClient.post<StandardResponse<ReportTokenResponse>>(
      `/recon/clients/${clientId}/report/token`,
      null,
      { params: { fmt } },
    );
    return res.data.data;
  },

  /**
   * Fetch the scan HTML report as a Blob (Bearer token attached by the
   * axios interceptor).  The caller should create an object URL and
   * open it in a new tab.
   */
  fetchScanReportHtml: async (scanId: number): Promise<Blob> => {
    const res = await apiClient.get(`/recon/scans/${scanId}/report/html`, {
      responseType: 'blob',
    });
    return res.data;
  },

  fetchScanReportPdf: async (scanId: number): Promise<Blob> => {
    const res = await apiClient.get(`/recon/scans/${scanId}/report/pdf`, {
      responseType: 'blob',
    });
    return res.data;
  },

  fetchClientReportHtml: async (clientId: number): Promise<Blob> => {
    const res = await apiClient.get(`/recon/clients/${clientId}/report/html`, {
      responseType: 'blob',
    });
    return res.data;
  },

  // Legacy URL builders — kept for backwards compatibility with any
  // callers that prefer the token-based approach.  Prefer the
  // fetch*ReportHtml / issue*ReportToken methods above for new code.
  getReportHtmlUrl: (scanId: number): string => {
    return `/api/v1/recon/scans/${scanId}/report/html`;
  },

  getReportPdfUrl: (scanId: number): string => {
    return `/api/v1/recon/scans/${scanId}/report/pdf`;
  },

  // ---- Assets ----
  listAssets: async (params?: { skip?: number; limit?: number; host?: string }): Promise<Asset[]> => {
    const res = await apiClient.get<StandardResponse<Asset[]>>('/recon/assets', { params });
    return res.data.data;
  },

  listAssetsByHost: async (host: string): Promise<Asset[]> => {
    // Encode the host so dots / slashes don't break the path.
    const res = await apiClient.get<StandardResponse<Asset[]>>(
      `/recon/assets/host/${encodeURIComponent(host)}`,
    );
    return res.data.data;
  },

  getAsset: async (assetId: number): Promise<Asset> => {
    const res = await apiClient.get<StandardResponse<Asset>>(`/recon/assets/${assetId}`);
    return res.data.data;
  },

  deleteAsset: async (assetId: number): Promise<void> => {
    await apiClient.delete(`/recon/assets/${assetId}`);
  },

  // ---- Stats ----
  getStats: async (): Promise<ReconStats> => {
    const res = await apiClient.get<StandardResponse<ReconStats>>('/recon/stats');
    return res.data.data;
  },
};
