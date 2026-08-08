// frontend/src/context/ToastContext.tsx
import React, { createContext, useContext, useState, useCallback } from 'react';
import { CheckCircleIcon, ExclamationCircleIcon, InformationCircleIcon, XMarkIcon } from '@heroicons/react/24/solid';

type ToastType = 'success' | 'error' | 'info';

interface Toast {
  id: string;
  message: string;
  type: ToastType;
}

interface ToastContextType {
  showToast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, type: ToastType = 'info') => {
    const id = Math.random().toString(36).substr(2, 9);
    setToasts((prev) => [...prev, { id, message, type }]);
    
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  }, []);

  const removeToast = (id: string) => setToasts((prev) => prev.filter((t) => t.id !== id));

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-full max-w-sm">
        {toasts.map((toast) => (
          <div 
            key={toast.id} 
            className={`flex items-start p-4 rounded-xl shadow-lg backdrop-blur-md border transition-all transform translate-x-0 opacity-100 ${
              toast.type === 'success' ? 'bg-dark-800/90 border-primary-500/50 text-primary-300' :
              toast.type === 'error' ? 'bg-dark-800/90 border-red-500/50 text-red-300' :
              'bg-dark-800/90 border-dark-600 text-dark-200'
            }`}
          >
            <div className="flex-shrink-0 mr-3">
              {toast.type === 'success' && <CheckCircleIcon className="w-5 h-5 text-primary-400" />}
              {toast.type === 'error' && <ExclamationCircleIcon className="w-5 h-5 text-red-400" />}
              {toast.type === 'info' && <InformationCircleIcon className="w-5 h-5 text-dark-400" />}
            </div>
            <div className="flex-1 text-sm font-medium">{toast.message}</div>
            <button onClick={() => removeToast(toast.id)} className="ml-3 text-dark-400 hover:text-dark-100">
              <XMarkIcon className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast must be used within ToastProvider');
  return context;
};