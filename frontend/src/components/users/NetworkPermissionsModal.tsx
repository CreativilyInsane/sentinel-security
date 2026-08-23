// frontend/src/components/users/NetworkPermissionsModal.tsx
import React, { useState, useEffect } from 'react';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { usersApi } from '@/api/users.api';
import { useToast } from '@/context/ToastContext';
import type { User } from '@/types/user.types';

interface Props {
  user: User | null;
  isOpen: boolean;
  onClose: () => void;
}

export const NetworkPermissionsModal: React.FC<Props> = ({ user, isOpen, onClose }) => {
  const { showToast } = useToast();
  const [networks, setNetworks] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (isOpen && user) {
      setLoading(true);
      usersApi.getUserNetworks(user.id).then(data => {
        setNetworks(data.networks.join('\n'));
        setLoading(false);
      }).catch(() => {
        setNetworks('');
        setLoading(false);
      });
    }
  }, [isOpen, user]);

  const handleSave = async () => {
    if (!user) return;
    const list = networks.split('\n').map(s => s.trim()).filter(Boolean);
    // Basic CIDR validation
    const cidrRegex = /^(\d{1,3}\.){3}\d{1,3}\/\d{1,2}$/;
    for (const cidr of list) {
      if (!cidrRegex.test(cidr)) {
        showToast(`Invalid CIDR format: ${cidr}. Use format like 192.168.1.0/24`, 'error');
        return;
      }
    }
    setSaving(true);
    try {
      await usersApi.setUserNetworks(user.id, list);
      showToast(`Network permissions updated for ${user.username}`, 'success');
      onClose();
    } catch (err: any) {
      showToast(err?.response?.data?.message || 'Failed to update', 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Network Permissions: ${user?.username || ''}`}>
      <div className="space-y-4">
        <p className="text-xs text-dark-400">
          Specify which private/internal CIDR ranges this user is authorized to scan. One per line.
        </p>
        {loading ? (
          <div className="flex justify-center py-6"><Spinner className="w-6 h-6" /></div>
        ) : (
          <textarea
            className="w-full h-36 bg-dark-900/70 border border-dark-700 rounded-xl py-3 px-4 text-sm text-dark-100 font-mono hover:border-dark-600 focus:outline-none focus:ring-2 focus:ring-primary-500/60 focus:border-primary-500/60 transition-all resize-none"
            placeholder={`192.168.1.0/24\n10.0.0.0/8`}
            value={networks}
            onChange={e => setNetworks(e.target.value)}
          />
        )}
        <div className="flex space-x-3 pt-2">
          <Button type="button" variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
          <Button type="button" fullWidth isLoading={saving} onClick={handleSave}>Save</Button>
        </div>
      </div>
    </Modal>
  );
};
