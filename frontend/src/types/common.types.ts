// frontend/src/types/common.types.ts
export interface StandardResponse<T> {
  success: boolean;
  message: string;
  data: T;
}