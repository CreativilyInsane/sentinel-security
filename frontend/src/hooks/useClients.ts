// frontend/src/hooks/useClients.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { clientsApi } from '@/api/clients.api';
import type {
  ClientCreatePayload,
  ClientUpdatePayload,
  ClientAssetCreatePayload,
  ClientAssetUpdatePayload,
  AssignClientPayload,
  AssignDirectTargetPayload,
  AssignmentUpdatePayload,
} from '@/types/client.types';

// ---- Clients list ----
export const useClients = (params?: { skip?: number; limit?: number; search?: string; is_active?: boolean }) => {
  return useQuery({
    queryKey: ['clients', params],
    queryFn: () => clientsApi.listClients(params),
  });
};

export const useClient = (clientId: number | null) => {
  return useQuery({
    queryKey: ['client', clientId],
    queryFn: () => clientsApi.getClient(clientId as number),
    enabled: clientId !== null,
  });
};

export const useCreateClient = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ClientCreatePayload) => clientsApi.createClient(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['clients'] }),
  });
};

export const useUpdateClient = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ clientId, payload }: { clientId: number; payload: ClientUpdatePayload }) =>
      clientsApi.updateClient(clientId, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['clients'] }),
  });
};

export const useDeleteClient = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (clientId: number) => clientsApi.deleteClient(clientId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['clients'] }),
  });
};

// ---- Client assets ----
export const useClientAssets = (clientId: number | null) => {
  return useQuery({
    queryKey: ['client-assets', clientId],
    queryFn: () => clientsApi.listClientAssets(clientId as number),
    enabled: clientId !== null,
  });
};

export const useCreateClientAsset = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ clientId, payload }: { clientId: number; payload: ClientAssetCreatePayload }) =>
      clientsApi.createClientAsset(clientId, payload),
    onSuccess: (_d, vars) => qc.invalidateQueries({ queryKey: ['client-assets', vars.clientId] }),
  });
};

export const useUpdateClientAsset = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ clientId, assetId, payload }: {
      clientId: number; assetId: number; payload: ClientAssetUpdatePayload;
    }) => clientsApi.updateClientAsset(clientId, assetId, payload),
    onSuccess: (_d, vars) => qc.invalidateQueries({ queryKey: ['client-assets', vars.clientId] }),
  });
};

export const useDeleteClientAsset = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ clientId, assetId }: { clientId: number; assetId: number }) =>
      clientsApi.deleteClientAsset(clientId, assetId),
    onSuccess: (_d, vars) => qc.invalidateQueries({ queryKey: ['client-assets', vars.clientId] }),
  });
};

// ---- Assignments ----
export const useAssignments = (params?: { skip?: number; limit?: number; user_id?: number; client_id?: number }) => {
  return useQuery({
    queryKey: ['assignments', params],
    queryFn: () => clientsApi.listAssignments(params),
  });
};

export const useAssignClient = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: AssignClientPayload) => clientsApi.assignClient(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['assignments'] });
      qc.invalidateQueries({ queryKey: ['my-targets'] });
      qc.invalidateQueries({ queryKey: ['my-clients'] });
      qc.invalidateQueries({ queryKey: ['my-notifications'] });
      qc.invalidateQueries({ queryKey: ['unread-count'] });
    },
  });
};

export const useAssignDirectTarget = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: AssignDirectTargetPayload) => clientsApi.assignDirectTarget(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['assignments'] });
      qc.invalidateQueries({ queryKey: ['my-targets'] });
      qc.invalidateQueries({ queryKey: ['my-clients'] });
      qc.invalidateQueries({ queryKey: ['my-notifications'] });
      qc.invalidateQueries({ queryKey: ['unread-count'] });
    },
  });
};

export const useUpdateAssignment = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ assignmentId, payload }: { assignmentId: number; payload: AssignmentUpdatePayload }) =>
      clientsApi.updateAssignment(assignmentId, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['assignments'] }),
  });
};

export const useDeleteAssignment = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (assignmentId: number) => clientsApi.deleteAssignment(assignmentId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['assignments'] });
      qc.invalidateQueries({ queryKey: ['my-targets'] });
      qc.invalidateQueries({ queryKey: ['my-clients'] });
    },
  });
};

// ---- User-side queries ----
export const useMyTargets = () => {
  return useQuery({
    queryKey: ['my-targets'],
    queryFn: () => clientsApi.myTargets(),
  });
};

export const useMyClients = () => {
  return useQuery({
    queryKey: ['my-clients'],
    queryFn: () => clientsApi.myClients(),
  });
};

export const useMyNotifications = (unreadOnly: boolean = false) => {
  return useQuery({
    queryKey: ['my-notifications', { unreadOnly }],
    queryFn: () => clientsApi.myNotifications(unreadOnly),
  });
};

export const useUnreadCount = () => {
  return useQuery({
    queryKey: ['unread-count'],
    queryFn: () => clientsApi.myUnreadCount(),
    refetchInterval: 30_000,
  });
};

export const useMarkNotificationsRead = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (notificationIds?: number[]) => clientsApi.markNotificationsRead(notificationIds),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['my-notifications'] });
      qc.invalidateQueries({ queryKey: ['unread-count'] });
    },
  });
};

// ---- Active targets (user-level selection) ----
export const useActiveTargets = () => {
  return useQuery({
    queryKey: ['active-targets'],
    queryFn: () => clientsApi.listActiveTargets(),
  });
};

export const useToggleActiveTarget = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ assignmentId, targetValue, isActive }: {
      assignmentId: number; targetValue: string; isActive: boolean;
    }) => clientsApi.toggleActiveTarget(assignmentId, targetValue, isActive),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['active-targets'] });
      qc.invalidateQueries({ queryKey: ['my-targets'] });
    },
  });
};

export const useClientScans = (clientId: number | null) => {
  return useQuery({
    queryKey: ['client-scans', clientId],
    queryFn: () => clientsApi.listClientScans(clientId as number),
    enabled: clientId !== null,
  });
};
