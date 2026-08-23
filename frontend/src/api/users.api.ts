// frontend/src/api/users.api.ts
import { apiClient } from './client';
import type { User, UserCreatePayload, UserUpdatePayload, ModulePermissionsRead } from '@/types/user.types';
import type { StandardResponse } from '@/types/common.types';

export const usersApi = {
  getUsers: async (): Promise<User[]> => {
    const res = await apiClient.get<StandardResponse<User[]>>('/users/');
    return res.data.data;
  },

  createUser: async (data: UserCreatePayload): Promise<User> => {
    const res = await apiClient.post<StandardResponse<User>>('/users/', data);
    return res.data.data;
  },

  updateUser: async (id: number, data: UserUpdatePayload): Promise<User> => {
    const res = await apiClient.put<StandardResponse<User>>(`/users/${id}`, data);
    return res.data.data;
  },

  deleteUser: async (id: number): Promise<void> => {
    await apiClient.delete(`/users/${id}`);
  },

  getUserNetworks: async (userId: number): Promise<{user_id: number; username: string; networks: string[]}> => {
    const res = await apiClient.get<StandardResponse<any>>(`/users/${userId}/networks`);
    return res.data.data;
  },

  setUserNetworks: async (userId: number, networks: string[]): Promise<any> => {
    const res = await apiClient.put<StandardResponse<any>>(`/users/${userId}/networks`, { networks });
    return res.data.data;
  },

  // NOTE: togglePrivateScan has been REMOVED — private-network scan access
  // is now controlled by the per-user `private_network_scan` module
  // permission on the User Module Settings page (/admin/users/:userId/modules).

  // ---- Module permissions ----
  getModulePermissions: async (userId: number): Promise<ModulePermissionsRead> => {
    const res = await apiClient.get<StandardResponse<ModulePermissionsRead>>(`/users/${userId}/modules`);
    return res.data.data;
  },

  setModulePermissions: async (
    userId: number,
    permissions: Array<{ module_name: string; is_allowed: boolean }>,
  ): Promise<ModulePermissionsRead> => {
    const res = await apiClient.put<StandardResponse<ModulePermissionsRead>>(`/users/${userId}/modules`, { permissions });
    return res.data.data;
  },

  getAllowedModules: async (userId: number): Promise<{
    modules: string[]; is_default_open: boolean;
  }> => {
    const res = await apiClient.get<StandardResponse<any>>(`/users/${userId}/allowed-modules`);
    return res.data.data;
  },
};
