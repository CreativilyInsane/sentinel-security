// frontend/src/pages/Users.tsx
import React, { useState } from 'react';
import { PlusIcon } from '@heroicons/react/24/outline';
import { useUsers, useDeleteUser } from '@/hooks/useUsers';
import { UserTable } from '@/components/users/UserTable';
import { UserFormModal } from '@/components/users/UserFormModal';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import type { User } from '@/types/user.types';

export const Users: React.FC = () => {
  const { data: users, isLoading } = useUsers();
  const deleteUser = useDeleteUser();
  
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [deleteTargetId, setDeleteTargetId] = useState<number | null>(null);

  const handleOpenCreate = () => {
    setEditingUser(null);
    setIsModalOpen(true);
  };

  const handleOpenEdit = (user: User) => {
    setEditingUser(user);
    setIsModalOpen(true);
  };

  const handleDelete = (id: number) => {
    setDeleteTargetId(id);
  };

  const confirmDelete = async () => {
    if (deleteTargetId !== null) {
      await deleteUser.mutateAsync(deleteTargetId);
      setDeleteTargetId(null);
    }
  };

  const deleteTargetUser = users?.find((u) => u.id === deleteTargetId) ?? null;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner className="w-8 h-8" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold text-dark-50">User Management</h1>
          <p className="text-dark-400 mt-1">Manage user accounts, roles, and access permissions.</p>
        </div>
        <Button onClick={handleOpenCreate} className="flex items-center">
          <PlusIcon className="w-5 h-5 mr-1" />
          Add User
        </Button>
      </div>

      <UserTable users={users || []} onEdit={handleOpenEdit} onDelete={handleDelete} />

      <UserFormModal 
        isOpen={isModalOpen} 
        onClose={() => setIsModalOpen(false)} 
        user={editingUser} 
      />

      <ConfirmDialog
        isOpen={deleteTargetId !== null}
        title="Delete User"
        message={`Are you sure you want to delete ${deleteTargetUser ? `"${deleteTargetUser.username}"` : 'this user'}? This action cannot be undone.`}
        confirmLabel="Delete User"
        isLoading={deleteUser.isPending}
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTargetId(null)}
      />
    </div>
  );
};