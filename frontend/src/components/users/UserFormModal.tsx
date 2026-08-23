// frontend/src/components/users/UserFormModal.tsx
import React from 'react';
import { useForm } from 'react-hook-form';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useCreateUser, useUpdateUser } from '@/hooks/useUsers';
import type { User, UserCreatePayload, UserUpdatePayload } from '@/types/user.types';

interface UserFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  user?: User | null; // If provided, it's an edit form
}

export const UserFormModal: React.FC<UserFormModalProps> = ({ isOpen, onClose, user }) => {
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  
  const isEdit = !!user;

  const { register, handleSubmit, reset, formState: { errors } } = useForm({
    defaultValues: {
      username: user?.username || '',
      email: user?.email || '',
      password: '',
      role_name: user?.role.name || 'User',
      is_active: user?.is_active ?? true,
    }
  });

  React.useEffect(() => {
    if (isOpen) {
      reset({
        username: user?.username || '',
        email: user?.email || '',
        password: '',
        role_name: user?.role.name || 'User',
        is_active: user?.is_active ?? true,
      });
    }
  }, [isOpen, user, reset]);

  const onSubmit = async (data: any) => {
    try {
      if (isEdit && user) {
        const payload: UserUpdatePayload = {
          email: data.email,
          role_name: data.role_name,
          is_active: data.is_active,
        };
        // Only send password if it was changed
        if (data.password) {
          payload.password = data.password;
        }
        await updateUser.mutateAsync({ id: user.id, data: payload });
      } else {
        const payload: UserCreatePayload = {
          username: data.username,
          email: data.email,
          password: data.password,
          role_name: data.role_name,
        };
        await createUser.mutateAsync(payload);
      }
      onClose();
    } catch (error) {
      // Error is handled by the mutation hook
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={isEdit ? 'Edit User' : 'Create New User'}>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {!isEdit && (
          <Input
            label="Username"
            {...register('username', { required: 'Username is required' })}
            error={errors.username?.message as string}
          />
        )}
        
        <Input
          label="Email Address"
          type="email"
          {...register('email', { required: 'Email is required' })}
          error={errors.email?.message as string}
        />
        
        <Input
          label={isEdit ? "New Password (leave blank to keep current)" : "Password"}
          type="password"
          {...register('password', { 
            required: !isEdit ? 'Password is required' : false,
            minLength: { value: 8, message: 'Password must be at least 8 characters' }
          })}
          error={errors.password?.message as string}
        />

        <div>
          <label className="block text-sm font-medium text-dark-300 mb-1.5 tracking-wide">Role</label>
          <select
            {...register('role_name')}
            className="w-full bg-dark-900/70 border border-dark-700 rounded-xl py-2.5 px-4 text-dark-100 hover:border-dark-600 focus:outline-none focus:ring-2 focus:ring-primary-500/60 focus:border-primary-500/60 transition-all"
          >
            <option value="User">User</option>
            <option value="Administrator">Administrator</option>
          </select>
        </div>

        {isEdit && (
          <div className="flex items-center space-x-3 pt-2">
            <input
              type="checkbox"
              id="is_active"
              {...register('is_active')}
              className="w-4 h-4 rounded bg-dark-900 border-dark-700 text-primary-600 focus:ring-primary-500/60 focus:ring-offset-0"
            />
            <label htmlFor="is_active" className="text-sm text-dark-200">Account Active</label>
          </div>
        )}

        <div className="flex space-x-3 pt-4">
          <Button type="button" variant="secondary" fullWidth onClick={onClose}>
            Cancel
          </Button>
          <Button 
            type="submit" 
            fullWidth 
            isLoading={createUser.isPending || updateUser.isPending}
          >
            {isEdit ? 'Save Changes' : 'Create User'}
          </Button>
        </div>
      </form>
    </Modal>
  );
};