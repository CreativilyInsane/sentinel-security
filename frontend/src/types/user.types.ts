// frontend/src/types/user.types.ts
export interface Role {
  id: number;
  name: string;
}

export interface User {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
  role: Role;
  created_at: string;
  updated_at: string;
}

export interface UserCreatePayload {
  username: string;
  email: string;
  password: string;
  role_name: string;
}

export interface UserUpdatePayload {
  email?: string;
  password?: string;
  role_name?: string;
  is_active?: boolean;
}