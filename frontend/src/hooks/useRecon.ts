// frontend/src/hooks/useRecon.ts
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { reconApi } from '@/api/recon.api';
import type { ScanCreatePayload, ScanSummary } from '@/types/recon.types';

// ---- Scan list ----
export const useScans = (params?: {
  skip?: number;
  limit?: number;
  status?: string;
  target?: string;
}) => {
  return useQuery({
    queryKey: ['recon', 'scans', params],
    queryFn: () => reconApi.listScans(params),
    placeholderData: keepPreviousData,
  });
};

// ---- Single scan (with polling while QUEUED / RUNNING) ----
export const useScan = (scanId: number | null) => {
  return useQuery({
    queryKey: ['recon', 'scan', scanId],
    queryFn: () => reconApi.getScan(scanId as number),
    enabled: scanId !== null,
    refetchInterval: (q) => {
      const data = q.state.data;
      if (!data) return 3000;
      if (data.status === 'QUEUED' || data.status === 'RUNNING') {
        return 3000; // poll every 3s while in progress
      }
      return false; // stop polling once terminal
    },
  });
};

// ---- Scan results ----
export const useScanResults = (scanId: number | null) => {
  return useQuery({
    queryKey: ['recon', 'scan-results', scanId],
    queryFn: () => reconApi.getScanResults(scanId as number),
    enabled: scanId !== null,
    // No polling here — useLiveScanDetail drives the polling based on
    // the scan status.  This hook is kept for components that only need
    // a one-shot fetch.
  });
};

// ---- Combined live scan detail (scan + results, polled) ----
export const useLiveScanDetail = (scanId: number | null) => {
  const scanQuery = useScan(scanId);
  const isRunning =
    scanQuery.data?.status === 'QUEUED' || scanQuery.data?.status === 'RUNNING';

  const resultsQuery = useQuery({
    queryKey: ['recon', 'scan-results', scanId],
    queryFn: () => reconApi.getScanResults(scanId as number),
    enabled: scanId !== null,
    refetchInterval: isRunning ? 3000 : false,
  });

  return { scan: scanQuery, results: resultsQuery, isRunning };
};

// ---- Create scan ----
export const useCreateScan = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ScanCreatePayload) => reconApi.createScan(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recon', 'scans'] });
      qc.invalidateQueries({ queryKey: ['recon', 'stats'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
};

// ---- Cancel scan ----
export const useCancelScan = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (scanId: number) => reconApi.cancelScan(scanId),
    onSuccess: (_data, scanId) => {
      qc.invalidateQueries({ queryKey: ['recon', 'scan', scanId] });
      qc.invalidateQueries({ queryKey: ['recon', 'scans'] });
      qc.invalidateQueries({ queryKey: ['recon', 'stats'] });
    },
  });
};

// ---- Delete scan ----
export const useDeleteScan = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (scanId: number) => reconApi.deleteScan(scanId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recon', 'scans'] });
      qc.invalidateQueries({ queryKey: ['recon', 'stats'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
};

// ---- Assets ----
export const useAssets = (params?: { skip?: number; limit?: number; host?: string }) => {
  return useQuery({
    queryKey: ['recon', 'assets', params],
    queryFn: () => reconApi.listAssets(params),
    placeholderData: keepPreviousData,
  });
};

export const useAsset = (assetId: number | null) => {
  return useQuery({
    queryKey: ['recon', 'asset', assetId],
    queryFn: () => reconApi.getAsset(assetId as number),
    enabled: assetId !== null,
  });
};

// ---- Assets by host (Asset Details view) ----
export const useAssetsByHost = (host: string | null) => {
  return useQuery({
    queryKey: ['recon', 'assets-by-host', host],
    queryFn: () => reconApi.listAssetsByHost(host as string),
    enabled: !!host,
  });
};

// ---- Delete asset (Phase 17 ownership rule enforced on backend) ----
export const useDeleteAsset = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (assetId: number) => reconApi.deleteAsset(assetId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recon', 'assets'] });
      qc.invalidateQueries({ queryKey: ['recon', 'assets-by-host'] });
      qc.invalidateQueries({ queryKey: ['recon', 'stats'] });
    },
  });
};

// ---- Stats ----
export const useReconStats = () => {
  return useQuery({
    queryKey: ['recon', 'stats'],
    queryFn: reconApi.getStats,
    refetchInterval: 15000, // refresh stats every 15s on the dashboard
  });
};

// ---- Report metadata ----
export const useReportMetadata = (scanId: number | null) => {
  return useQuery({
    queryKey: ['recon', 'report-meta', scanId],
    queryFn: () => reconApi.getReportMetadata(scanId as number),
    enabled: scanId !== null,
  });
};

// Helper for type narrowing in lists
export type { ScanSummary };
