import React from 'react';
import { AlertTriangle, X } from 'lucide-react';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  open,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  danger = true,
  loading = false,
  onConfirm,
  onCancel,
}) => {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      role="dialog"
      aria-modal="true"
    >
      <div className="w-full max-w-md rounded-lg bg-[#12161F] border border-[#2A3244] shadow-2xl">
        <div className="flex items-start justify-between p-4 border-b border-[#222836]">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className={`h-5 w-5 ${danger ? 'text-red-400' : 'text-amber-400'}`} />
            <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
          </div>
          <button onClick={onCancel} className="text-slate-500 hover:text-slate-300" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-4">
          <p className="text-sm text-slate-300 leading-relaxed">{description}</p>
        </div>
        <div className="flex items-center justify-end gap-2 px-4 py-3 bg-[#0E1118] border-t border-[#222836] rounded-b-lg">
          <button type="button" onClick={onCancel} className="pg-btn-secondary" disabled={loading}>
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={danger ? 'pg-btn-danger' : 'pg-btn-primary'}
            disabled={loading}
          >
            {loading ? 'Processing...' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};

