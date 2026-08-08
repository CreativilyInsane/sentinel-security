// frontend/src/api/auth.api.ts
import { apiClient } from './client';
import type { LoginRequest, TokenResponse, LogoutRequest, User } from '@/types';
import type { StandardResponse } from '@/types/common.types';

export const authApi = {
  login: async (data: LoginRequest): Promise<TokenResponse> => {
    const res = await apiClient.post<StandardResponse<TokenResponse>>('/auth/login', data);
    return res.data.data;
  },
  
  logout: async (data: LogoutRequest): Promise<void> => {
    await apiClient.post('/auth/logout', data);
  },
  
  getMe: async (): Promise<User> => {
    const res = await apiClient.get<StandardResponse<User>>('/auth/me');
    return res.data.data;
  },
};