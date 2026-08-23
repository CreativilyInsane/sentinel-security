// frontend/src/pages/Settings.tsx
import React, { useState } from 'react';
import {
  UserCircleIcon,
  LockClosedIcon,
  EnvelopeIcon,
  SwatchIcon,
  KeyIcon,
  EyeIcon,
  EyeSlashIcon,
} from '@heroicons/react/24/outline';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Spinner } from '@/components/ui/Spinner';
import { useAuth } from '@/context/AuthContext';
import { useToast } from '@/context/ToastContext';
import { useTheme, THEMES } from '@/context/ThemeContext';
import { authApi } from '@/api/auth.api';
import { cn } from '@/utils/cn';

type TabId = 'profile' | 'security' | 'appearance';

const TABS: Array<{ id: TabId; label: string; icon: React.ComponentType<{ className?: string }> }> = [
  { id: 'profile', label: 'Profile', icon: UserCircleIcon },
  { id: 'security', label: 'Security', icon: LockClosedIcon },
  { id: 'appearance', label: 'Appearance', icon: SwatchIcon },
];

export const Settings: React.FC = () => {
  const { user, refreshUser } = useAuth();
  const [activeTab, setActiveTab] = useState<TabId>('profile');

  if (!user) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Spinner className="w-8 h-8" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-display font-bold text-dark-50">Settings</h1>
        <p className="text-dark-400 mt-1">
          Manage your account profile, security credentials, and appearance preferences.
        </p>
      </div>

      {/* Tab bar */}
      <div className="glass-panel rounded-xl p-1.5 inline-flex gap-1 flex-wrap">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
                isActive
                  ? 'bg-primary-500/15 text-primary-300 border border-primary-500/40 shadow-glow-sm'
                  : 'text-dark-400 hover:text-dark-100 border border-transparent',
              )}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      {activeTab === 'profile' && <ProfileTab user={user} refreshUser={refreshUser} />}
      {activeTab === 'security' && <SecurityTab user={user} />}
      {activeTab === 'appearance' && <AppearanceTab />}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Profile tab — read-only username + role, editable email
// ---------------------------------------------------------------------------
const ProfileTab: React.FC<{ user: any; refreshUser: () => Promise<void> }> = ({ user, refreshUser }) => {
  const { showToast } = useToast();
  const [email, setEmail] = useState(user.email || '');
  const [saving, setSaving] = useState(false);

  const handleSaveEmail = async () => {
    setSaving(true);
    try {
      await authApi.updateEmail(email);
      await refreshUser();
      showToast('Email updated successfully.', 'success');
    } catch (err: any) {
      const msg = err?.response?.data?.message || 'Failed to update email.';
      showToast(msg, 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="glass-panel border-glow-top rounded-xl p-6 space-y-4">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-primary-400 shadow-glow-sm" />
          <h2 className="text-base font-display font-semibold text-dark-50">Account Information</h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-dark-400 mb-1">Username</label>
            <div className="px-3 py-2 rounded-lg bg-dark-900/60 border border-dark-700 text-sm font-mono text-dark-200">
              {user.username}
            </div>
            <p className="text-[10px] text-dark-500 mt-1">Username cannot be changed.</p>
          </div>
          <div>
            <label className="block text-xs text-dark-400 mb-1">Role</label>
            <div className="px-3 py-2 rounded-lg bg-dark-900/60 border border-dark-700 text-sm">
              <Badge variant={user.role.name === 'Administrator' ? 'primary' : 'neutral'} noDot>
                {user.role.name}
              </Badge>
            </div>
            <p className="text-[10px] text-dark-500 mt-1">Assigned by an administrator.</p>
          </div>
        </div>

        <Input
          id="email"
          label="Email address"
          icon={<EnvelopeIcon className="w-4 h-4" />}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          type="email"
        />

        <div className="flex justify-end">
          <Button
            onClick={handleSaveEmail}
            isLoading={saving}
            disabled={email.trim() === user.email || !email.trim()}
          >
            Save Email
          </Button>
        </div>
      </div>

      {/* Note about module permissions */}
      <div className="glass-panel rounded-xl p-5 space-y-2">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-primary-400 shadow-glow-sm" />
          <h2 className="text-sm font-display font-semibold text-dark-50">Module Permissions</h2>
        </div>
        <p className="text-xs text-dark-400">
          Module-level permissions (recon modules, assets, reports, private network scan) are managed
          by an administrator on the dedicated <strong>User Module Settings</strong> page.  Open
          <span className="text-dark-200"> Users → click the module-permissions icon</span> next to a user to
          configure their permissions.
        </p>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Security tab — change password only (private scan toggle removed)
// ---------------------------------------------------------------------------
const SecurityTab: React.FC<{ user: any }> = () => {
  const { showToast } = useToast();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);

  const newPasswordError = validatePassword(newPassword);
  const confirmError = newPassword !== confirmPassword ? 'Passwords do not match.' : null;

  const handleChangePassword = async () => {
    if (!currentPassword.trim()) {
      showToast('Current password is required.', 'error');
      return;
    }
    if (newPasswordError) {
      showToast(newPasswordError, 'error');
      return;
    }
    if (confirmError) {
      showToast(confirmError, 'error');
      return;
    }
    setSavingPassword(true);
    try {
      await authApi.changePassword(currentPassword, newPassword);
      showToast('Password updated successfully.', 'success');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      const msg = err?.response?.data?.message || 'Failed to update password.';
      showToast(msg, 'error');
    } finally {
      setSavingPassword(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="glass-panel border-glow-top rounded-xl p-6 space-y-4">
        <div className="flex items-center gap-2">
          <KeyIcon className="w-5 h-5 text-primary-400" />
          <h2 className="text-base font-display font-semibold text-dark-50">Change Password</h2>
        </div>
        <p className="text-xs text-dark-400">
          Use a strong, unique password.  Passwords must be at least 8 characters and contain
          uppercase, lowercase, numeric, and special-character (@$!%*?&) components.
        </p>

        <div className="space-y-3">
          <div className="relative">
            <Input
              id="current-password"
              label="Current password"
              type={showCurrent ? 'text' : 'password'}
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              icon={<LockClosedIcon className="w-4 h-4" />}
            />
            <button
              type="button"
              onClick={() => setShowCurrent(!showCurrent)}
              className="absolute right-3 top-9 text-dark-400 hover:text-dark-100"
              tabIndex={-1}
            >
              {showCurrent ? <EyeSlashIcon className="w-4 h-4" /> : <EyeIcon className="w-4 h-4" />}
            </button>
          </div>

          <div className="relative">
            <Input
              id="new-password"
              label="New password"
              type={showNew ? 'text' : 'password'}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              error={newPassword && newPasswordError ? newPasswordError : undefined}
              icon={<LockClosedIcon className="w-4 h-4" />}
            />
            <button
              type="button"
              onClick={() => setShowNew(!showNew)}
              className="absolute right-3 top-9 text-dark-400 hover:text-dark-100"
              tabIndex={-1}
            >
              {showNew ? <EyeSlashIcon className="w-4 h-4" /> : <EyeIcon className="w-4 h-4" />}
            </button>
          </div>

          <Input
            id="confirm-password"
            label="Confirm new password"
            type={showNew ? 'text' : 'password'}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            error={confirmPassword && confirmError ? confirmError : undefined}
            icon={<LockClosedIcon className="w-4 h-4" />}
          />
        </div>

        <div className="flex justify-end">
          <Button
            onClick={handleChangePassword}
            isLoading={savingPassword}
            disabled={!currentPassword || !newPassword || !confirmPassword || !!newPasswordError || !!confirmError}
          >
            Update Password
          </Button>
        </div>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Appearance tab — theme switcher
// ---------------------------------------------------------------------------
const AppearanceTab: React.FC = () => {
  const { theme, setTheme } = useTheme();
  return (
    <div className="glass-panel border-glow-top rounded-xl p-6 space-y-4">
      <div className="flex items-center gap-2">
        <SwatchIcon className="w-5 h-5 text-primary-400" />
        <h2 className="text-base font-display font-semibold text-dark-50">Color Theme</h2>
      </div>
      <p className="text-xs text-dark-400">
        Choose a color theme for the dashboard.  Your preference is stored in this browser.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {THEMES.map((t) => {
          const isActive = theme === t.id;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => setTheme(t.id)}
              className={cn(
                'text-left rounded-xl p-4 border transition-all',
                isActive
                  ? 'border-primary-500/50 bg-primary-500/10 shadow-glow-sm'
                  : 'border-dark-700 bg-dark-900/40 hover:border-primary-500/30',
              )}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span
                    className="w-5 h-5 rounded-full border border-dark-700"
                    style={{ background: `linear-gradient(135deg, ${t.swatch[0]} 0%, ${t.swatch[1]} 100%)` }}
                  />
                  <span className="text-sm font-display font-semibold text-dark-100">{t.name}</span>
                </div>
                {/* CheckCircleIcon removed to avoid unused import; using a simple dot instead */}
                {isActive && <span className="w-5 h-5 rounded-full bg-primary-500/30 border border-primary-400" />}
              </div>
              <p className="text-xs text-dark-400">{t.description}</p>
            </button>
          );
        })}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// Password complexity validator (mirrors backend policy)
// ---------------------------------------------------------------------------
function validatePassword(v: string): string | null {
  if (!v) return null;
  if (v.length < 8) return 'Password must be at least 8 characters.';
  if (!/[A-Z]/.test(v)) return 'Password must contain an uppercase letter.';
  if (!/[a-z]/.test(v)) return 'Password must contain a lowercase letter.';
  if (!/[0-9]/.test(v)) return 'Password must contain a digit.';
  if (!/[@$!%*?&]/.test(v)) return 'Password must contain a special character (@$!%*?&).';
  return null;
}
