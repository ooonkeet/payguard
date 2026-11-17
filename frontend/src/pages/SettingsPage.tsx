import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Database, RotateCcw, ShieldCheck } from 'lucide-react';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { ErrorBanner } from '../components/FeedbackStates';
import { useToast } from '../components/ToastProvider';
import { extractErrorMessage, payguardApi } from '../services/api';

export const SettingsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [confirmReset, setConfirmReset] = useState(false);

  const settingsQ = useQuery({
    queryKey: ['settings'],
    queryFn: payguardApi.getSettings,
  });

  const resetMutation = useMutation({
    mutationFn: payguardApi.resetDemoData,
    onSuccess: (res) => {
      setConfirmReset(false);
      addToast(
        'success',
        'Demo Data Reset',
        `Restored ${res.counts.transactions} transactions, ${res.counts.webhooks} webhooks, ${res.counts.test_runs} test runs, and ${res.counts.bugs} bugs.`,
      );
      queryClient.invalidateQueries();
    },
    onError: (err) => addToast('error', 'Reset Failed', extractErrorMessage(err)),
  });

  const s = settingsQ.data;

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-lg font-semibold tracking-tight text-slate-100">Settings</h1>
        <p className="text-xs text-slate-400 mt-0.5">
          Sandbox runtime configuration, database status, security posture, and demo dataset controls.
        </p>
      </div>

      {settingsQ.isError && <ErrorBanner message={extractErrorMessage(settingsQ.error)} />}

      {s && (
        <>
          <div className="pg-card p-5 space-y-4">
            <div className="flex items-center gap-2 pb-2.5 border-b border-[#222836]">
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
              <h2 className="text-sm font-semibold text-slate-200">Environment & Security Configuration</h2>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div className="p-3 rounded bg-[#0D1016] border border-[#222836]">
                <p className="text-slate-500">Environment Mode</p>
                <p className="font-mono text-amber-400 font-semibold mt-1">{s.environment} (SIMULATED PAYMENT ENVIRONMENT)</p>
              </div>
              <div className="p-3 rounded bg-[#0D1016] border border-[#222836]">
                <p className="text-slate-500">Database Engine</p>
                <p className="font-mono text-slate-200 mt-1">{s.database_engine}</p>
              </div>
              <div className="p-3 rounded bg-[#0D1016] border border-[#222836]">
                <p className="text-slate-500">Webhook Signing Algorithm</p>
                <p className="font-mono text-emerald-400 mt-1">
                  {s.webhook_hmac_algorithm} (Secret kept server-side only)
                </p>
              </div>
              <div className="p-3 rounded bg-[#0D1016] border border-[#222836]">
                <p className="text-slate-500">Version</p>
                <p className="font-mono text-slate-200 mt-1">PayGuard v{s.version}</p>
              </div>
            </div>
          </div>

          <div className="pg-card p-5 space-y-4">
            <div className="flex items-center gap-2 pb-2.5 border-b border-[#222836]">
              <Database className="h-4 w-4 text-sky-400" />
              <h2 className="text-sm font-semibold text-slate-200">Persisted Database Record Counts</h2>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
              {Object.entries(s.record_counts || {}).map(([key, val]) => (
                <div key={key} className="p-3 rounded bg-[#0D1016] border border-[#222836]">
                  <p className="text-slate-500 capitalize">{key.replace(/_/g, ' ')}</p>
                  <p className="font-mono text-lg font-semibold text-slate-100 mt-0.5">{String(val)}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="pg-card p-5 border-red-500/25 space-y-3">
            <h2 className="text-sm font-semibold text-slate-100">Reset Sandbox Demo Data</h2>
            <p className="text-xs text-slate-400 leading-relaxed">
              Clears all live simulated transactions, webhooks, validation runs, test execution history, and custom defects, then re-seeds the initial baseline (20 successful, 5 failed, 3 pending transactions, 5 webhooks, 3 test runs, 3 bugs, and 4 API collections).
            </p>
            <button onClick={() => setConfirmReset(true)} className="pg-btn-danger text-xs">
              <RotateCcw className="h-3.5 w-3.5" />
              RESET DEMO DATA
            </button>
          </div>
        </>
      )}

      <ConfirmDialog
        open={confirmReset}
        title="Reset Sandbox Demo Data"
        description="This will erase all custom transactions, test executions, webhooks, and bugs, restoring only the initial synthetic demo baseline. Continue?"
        confirmLabel="Yes, Reset Demo Data"
        danger={true}
        loading={resetMutation.isPending}
        onConfirm={() => resetMutation.mutate()}
        onCancel={() => setConfirmReset(false)}
      />
    </div>
  );
};

