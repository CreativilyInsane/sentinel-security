// frontend/src/pages/Login.tsx
import React from 'react';
import { useForm } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import { ShieldCheckIcon, UserIcon, LockClosedIcon } from '@heroicons/react/24/outline';
import { useAuth } from '@/context/AuthContext';
import { useToast } from '@/context/ToastContext';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

interface LoginFormInputs {
  username: string;
  password: string;
}

export const Login: React.FC = () => {
  const { login } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<LoginFormInputs>();

  const onSubmit = async (data: LoginFormInputs) => {
    try {
      await login(data.username, data.password);
      navigate('/dashboard');
    } catch (error: any) {
      const message = error.response?.data?.message || 'Login failed. Please check your credentials.';
      showToast(message, 'error');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-dark-950 px-4 relative overflow-hidden">
      {/* Grid + Gradient Background Effects */}
      <div className="absolute inset-0 pointer-events-none bg-grid-pattern bg-grid [mask-image:radial-gradient(ellipse_60%_60%_at_50%_30%,black,transparent)]" />
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-primary-700/20 rounded-full blur-3xl animate-float"></div>
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-accent-700/15 rounded-full blur-3xl animate-float" style={{ animationDelay: '1.5s' }}></div>
      </div>

      <div className="relative w-full max-w-md animate-fade-in-up">
        <div className="text-center mb-8">
          <div className="relative inline-flex items-center justify-center w-16 h-16 bg-gradient-cyber rounded-2xl shadow-glow-lg mb-4">
            <div className="absolute inset-0 rounded-2xl bg-gradient-cyber blur-md opacity-60 -z-10" />
            <ShieldCheckIcon className="w-9 h-9 text-white" />
          </div>
          <h1 className="text-2xl font-display font-bold text-dark-50">Security Management System</h1>
          <p className="text-dark-400 mt-2 font-mono text-sm tracking-wide">&gt; Sign in to your secure dashboard_</p>
        </div>

        <div className="glass-panel border-glow-top rounded-2xl shadow-2xl shadow-black/40 p-8 relative overflow-hidden">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 relative">
            <Input
              id="username"
              label="Username"
              placeholder="Enter your username"
              icon={<UserIcon className="w-5 h-5" />}
              error={errors.username?.message}
              {...register('username', { required: 'Username is required' })}
            />

            <Input
              id="password"
              type="password"
              label="Password"
              placeholder="Enter your password"
              icon={<LockClosedIcon className="w-5 h-5" />}
              error={errors.password?.message}
              {...register('password', { required: 'Password is required' })}
            />

            <Button type="submit" fullWidth size="lg" isLoading={isSubmitting}>
              Sign In
            </Button>
          </form>
        </div>

        <p className="text-center text-xs text-dark-500 mt-6 font-mono tracking-wide uppercase">
          Protected by Enterprise Security Protocols
        </p>
      </div>
    </div>
  );
};