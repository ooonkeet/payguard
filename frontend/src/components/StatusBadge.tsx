import React from 'react';

const STATUS_STYLES: Record<string, string> = {
  // Payment statuses
  SUCCESS: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  FAILED: 'bg-red-500/10 text-red-400 border-red-500/30',
  PENDING: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  PROCESSING: 'bg-sky-500/10 text-sky-400 border-sky-500/30',
  CREATED: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
  REFUNDED: 'bg-indigo-500/10 text-indigo-300 border-indigo-500/30',
  // Test & validation statuses
  PASSED: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  PASS: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  FAIL: 'bg-red-500/10 text-red-400 border-red-500/30',
  ERROR: 'bg-red-500/10 text-red-400 border-red-500/30',
  SKIPPED: 'bg-slate-500/15 text-slate-400 border-slate-500/30',
  WARN: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  RUNNING: 'bg-sky-500/10 text-sky-400 border-sky-500/30',
  // Webhooks
  DELIVERED: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  INVALID_SIGNATURE: 'bg-red-500/10 text-red-400 border-red-500/30',
  RECEIVED: 'bg-sky-500/10 text-sky-400 border-sky-500/30',
  // Bug severities & statuses
  Critical: 'bg-red-500/15 text-red-400 border-red-500/40',
  High: 'bg-orange-500/15 text-orange-300 border-orange-500/40',
  Medium: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
  Low: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
  OPEN: 'bg-red-500/10 text-red-400 border-red-500/30',
  IN_PROGRESS: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
  FIXED: 'bg-sky-500/10 text-sky-300 border-sky-500/30',
  VERIFIED: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  CLOSED: 'bg-slate-500/15 text-slate-400 border-slate-500/30',
};

export const StatusBadge: React.FC<{ value: string; className?: string }> = ({ value, className = '' }) => {
  const style = STATUS_STYLES[value] || 'bg-slate-500/15 text-slate-300 border-slate-500/30';
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-[11px] font-medium font-mono tracking-wide border rounded ${style} ${className}`}
    >
      {value}
    </span>
  );
};

export const SeededBadge: React.FC<{ isSeeded?: boolean }> = ({ isSeeded }) => {
  if (!isSeeded) return null;
  return (
    <span
      title="Synthetic record populated by initial sandbox seed"
      className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-mono uppercase tracking-wider rounded bg-slate-800 text-slate-400 border border-slate-700"
    >
      SEED
    </span>
  );
};

