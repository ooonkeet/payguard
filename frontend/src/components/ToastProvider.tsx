import React, { createContext, useCallback, useContext, useState } from 'react';
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

interface ToastItem {
  id: string;
  type: ToastType;
  title: string;
  description?: string;
}

interface ToastContextValue {
  addToast: (type: ToastType, title: string, description?: string) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback(
    (type: ToastType, title: string, description?: string) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      setToasts((prev) => [...prev.slice(-3), { id, type, title, description }]);
      window.setTimeout(() => dismiss(id), 4500);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div
        aria-live="polite"
        className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-full max-w-sm pointer-events-none"
      >
        {toasts.map((toast) => {
          const border =
            toast.type === 'success'
              ? 'border-emerald-500/40'
              : toast.type === 'error'
                ? 'border-red-500/40'
                : toast.type === 'warning'
                  ? 'border-amber-500/40'
                  : 'border-slate-600/50';
          const Icon =
            toast.type === 'success'
              ? CheckCircle2
              : toast.type === 'error' || toast.type === 'warning'
                ? AlertCircle
                : Info;
          const iconColor =
            toast.type === 'success'
              ? 'text-emerald-400'
              : toast.type === 'error'
                ? 'text-red-400'
                : toast.type === 'warning'
                  ? 'text-amber-400'
                  : 'text-sky-400';

          return (
            <div
              key={toast.id}
              className={`pointer-events-auto flex items-start gap-3 rounded-lg bg-[#141821] border ${border} px-3.5 py-3 shadow-xl`}
            >
              <Icon className={`h-4 w-4 mt-0.5 shrink-0 ${iconColor}`} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-100">{toast.title}</p>
                {toast.description && (
                  <p className="text-xs text-slate-400 mt-0.5 break-words">{toast.description}</p>
                )}
              </div>
              <button
                onClick={() => dismiss(toast.id)}
                className="text-slate-500 hover:text-slate-300 transition-colors"
                aria-label="Dismiss notification"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
};

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}

