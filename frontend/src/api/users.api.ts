// frontend/src/api/users.api.ts
import { apiClient } from './client';
import type { User, UserCreatePayload, UserUpdatePayload } from '@/types/user.types';
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
};