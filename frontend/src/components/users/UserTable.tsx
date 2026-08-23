// frontend/src/components/users/UserTable.tsx
import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Cog6ToothIcon,
  PencilSquareIcon,
  TrashIcon,
  AdjustmentsHorizontalIcon,
} from '@heroicons/react/24/outline';
import { Badge } from '@/components/ui/Badge';
import { ROUTES } from '@/routes/paths';
import type { User } from '@/types/user.types';

interface UserTableProps {
  users: User[];
  onEdit: (user: User) => void;
  onDelete: (id: number) => void;
  onManageNetworks: (user: User) => void;
  // NOTE: onManageModules is no longer used — module permissions now live
  // on a dedicated page at /admin/users/:userId/modules.  The prop is
  // kept for backwards compatibility but ignored.
  onManageModules?: (user: User) => void;
}

export const UserTable: React.FC<UserTableProps> = ({ users, onEdit, onDelete, onManageNetworks }) => {
  const navigate = useNavigate();

  const goToModuleSettings = (userId: number) => {
    navigate(ROUTES.USER_MODULE_SETTINGS_BY_ID(userId));
  };

  return (
    <div className="glass-panel border-glow-top rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left">
          <thead className="bg-dark-950/60 border-b border-dark-800">
            <tr>
              <th className="px-5 py-3 text-xs font-semibold text-dark-400 uppercase tracking-wider">User</th>
              <th className="px-5 py-3 text-xs font-semibold text-dark-400 uppercase tracking-wider hidden md:table-cell">Role</th>
              <th className="px-5 py-3 text-xs font-semibold text-dark-400 uppercase tracking-wider hidden sm:table-cell">Status</th>
              <th className="px-5 py-3 text-xs font-semibold text-dark-400 uppercase tracking-wider text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-dark-800/70">
            {users.map((user) => (
              <tr key={user.id} className="hover:bg-primary-500/[0.04] transition-colors">
                <td className="px-5 py-4">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-gradient-cyber/20 border border-primary-700/40 flex items-center justify-center text-xs font-display font-semibold text-primary-300 uppercase shrink-0">
                      {user.username?.slice(0, 2)}
                    </div>
                    <div className="flex flex-col">
                      <span className="text-sm font-medium text-dark-100">{user.username}</span>
                      <span className="text-xs text-dark-500 font-mono">{user.email}</span>
                    </div>
                  </div>
                </td>
                <td className="px-5 py-4 hidden md:table-cell">
                  <Badge variant={user.role.name === 'Administrator' ? 'primary' : 'neutral'}>
                    {user.role.name}
                  </Badge>
                </td>
                <td className="px-5 py-4 hidden sm:table-cell">
                  <Badge variant={user.is_active ? 'success' : 'danger'}>
                    {user.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                </td>
                <td className="px-5 py-4">
                  <div className="flex items-center justify-end space-x-2">
                    <button
                      onClick={() => goToModuleSettings(user.id)}
                      className="p-1.5 text-dark-400 hover:text-primary-400 hover:bg-dark-800 hover:shadow-glow-sm rounded-lg transition-all"
                      title="Manage Module Permissions"
                    >
                      <AdjustmentsHorizontalIcon className="w-5 h-5" />
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); onManageNetworks(user); }}
                      className="p-1.5 text-dark-400 hover:text-primary-400 hover:bg-dark-800 hover:shadow-glow-sm rounded-lg transition-all"
                      title="Manage Network Permissions"
                    >
                      <Cog6ToothIcon className="w-5 h-5" />
                    </button>
                    <button
                      onClick={() => onEdit(user)}
                      className="p-1.5 text-dark-400 hover:text-primary-400 hover:bg-dark-800 hover:shadow-glow-sm rounded-lg transition-all"
                      title="Edit User"
                    >
                      <PencilSquareIcon className="w-5 h-5" />
                    </button>
                    <button
                      onClick={() => onDelete(user.id)}
                      className="p-1.5 text-dark-400 hover:text-red-400 hover:bg-dark-800 rounded-lg transition-all"
                      title="Delete User"
                    >
                      <TrashIcon className="w-5 h-5" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
