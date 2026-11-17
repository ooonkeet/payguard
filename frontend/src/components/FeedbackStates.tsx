import React from 'react';
import { AlertCircle, Inbox } from 'lucide-react';

export const TableSkeleton: React.FC<{ rows?: number }> = ({ rows = 6 }) => (
  <div className="space-y-2.5 p-4 animate-pulse">
    {Array.from({ length: rows }).map((_, i) => (
      <div key={i} className="h-9 bg-[#1A202C] rounded" />
    ))}
  </div>
);

export const CardSkeleton: React.FC<{ count?: number }> = ({ count = 4 }) => (
  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 animate-pulse">
    {Array.from({ length: count }).map((_, i) => (
      <div key={i} className="pg-card p-4 h-24 bg-[#141923]" />
    ))}
  </div>
);

export const EmptyState: React.FC<{ title: string; description: string; action?: React.ReactNode }> = ({
  title,
  description,
  action,
}) => (
  <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
    <div className="h-10 w-10 rounded-lg bg-[#181E2A] border border-[#262E3F] flex items-center justify-center mb-3">
      <Inbox className="h-5 w-5 text-slate-400" />
    </div>
    <p className="text-sm font-medium text-slate-200">{title}</p>
    <p className="text-xs text-slate-400 mt-1 max-w-md">{description}</p>
    {action && <div className="mt-4">{action}</div>}
  </div>
);

export const ErrorBanner: React.FC<{ message: string; onRetry?: () => void }> = ({ message, onRetry }) => (
  <div className="flex items-center justify-between gap-3 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
    <div className="flex items-center gap-2.5">
      <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />
      <span>{message}</span>
    </div>
    {onRetry && (
      <button onClick={onRetry} className="text-xs font-medium underline hover:text-red-200 shrink-0">
        Retry
      </button>
    )}
  </div>
);

