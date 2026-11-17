import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  CheckCircle2,
  Clock,
  Copy,
  Database,
  ExternalLink,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  Webhook,
  X,
  XCircle,
} from 'lucide-react';
import { extractErrorMessage, payguardApi } from '../services/api';
import { formatCurrency, formatDateTime, formatDurationMs } from '../utils/format';
import { ConfirmDialog } from './ConfirmDialog';
import { SeededBadge, StatusBadge } from './StatusBadge';
import { useToast } from './ToastProvider';

interface Props {
  transactionId: string | null;
  onClose: () => void;
}

export const TransactionDetailDrawer: React.FC<Props> = ({ transactionId, onClose }) => {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  const [confirmRefund, setConfirmRefund] = useState(false);
  const [activeTab, setActiveTab] = useState<'timeline' | 'payloads' | 'webhooks' | 'links'>('timeline');

  const { data: tx, isLoading, error } = useQuery({
    queryKey: ['transaction', transactionId],
    queryFn: () => payguardApi.getPaymentDetail(transactionId!),
    enabled: Boolean(transactionId),
  });

  const refundMutation = useMutation({
    mutationFn: () => payguardApi.refundPayment(transactionId!, 'Manual refund from Transaction Detail Console'),
    onSuccess: () => {
      addToast('success', 'Transaction Refunded', `${transactionId} transitioned to REFUNDED.`);
      setConfirmRefund(false);
      queryClient.invalidateQueries({ queryKey: ['transaction', transactionId] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
    onError: (err) => addToast('error', 'Refund Failed', extractErrorMessage(err)),
  });

  const reconcileMutation = useMutation({
    mutationFn: (resolved: 'SUCCESS' | 'FAILED') =>
      payguardApi.reconcilePayment(transactionId!, resolved, `Reconciled as ${resolved} via PayGuard console`),
    onSuccess: (updated) => {
      addToast('success', 'Transaction Reconciled', `${updated.transaction_id} is now ${updated.status}.`);
      queryClient.invalidateQueries({ queryKey: ['transaction', transactionId] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
    onError: (err) => addToast('error', 'Reconciliation Failed', extractErrorMessage(err)),
  });

  if (!transactionId) return null;

  const copyText = (text: string, label: string) => {
    navigator.clipboard.writeText(text).then(() => addToast('info', `Copied ${label}`, text));
  };

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-black/60" role="dialog" aria-modal="true">
      <div className="w-full max-w-2xl bg-[#0F1219] border-l border-[#222836] h-full flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#222836] bg-[#11141B]">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-semibold text-slate-100 truncate">{transactionId}</span>
              {tx && <StatusBadge value={tx.status} />}
              {tx && <SeededBadge isSeeded={tx.is_seeded} />}
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              {tx ? `${tx.order_id} • ${tx.payment_method} • ${formatDateTime(tx.created_at)}` : 'Loading record...'}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md text-slate-400 hover:text-slate-100 hover:bg-[#1C222E]"
            aria-label="Close transaction drawer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {isLoading && <div className="text-sm text-slate-400 animate-pulse">Loading transaction record...</div>}
          {error && (
            <div className="rounded-md bg-red-500/10 border border-red-500/30 p-3 text-sm text-red-300">
              {extractErrorMessage(error)}
            </div>
          )}

          {tx && (
            <>
              {/* Key Metadata Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <div className="pg-card p-3">
                  <p className="text-[11px] uppercase tracking-wider text-slate-400">Amount</p>
                  <p className="text-base font-semibold font-mono text-slate-100 mt-1">
                    {formatCurrency(tx.amount, tx.currency)}
                  </p>
                </div>
                <div className="pg-card p-3">
                  <p className="text-[11px] uppercase tracking-wider text-slate-400">Response Code</p>
                  <p className="text-xs font-mono text-slate-200 mt-1.5 break-all">{tx.response_code}</p>
                </div>
                <div className="pg-card p-3">
                  <p className="text-[11px] uppercase tracking-wider text-slate-400">Processing Time</p>
                  <p className="text-sm font-mono text-slate-100 mt-1">{formatDurationMs(tx.processing_duration_ms)}</p>
                </div>
              </div>

              {/* Action Strip for valid state machine transitions */}
              <div className="flex flex-wrap items-center gap-2">
                {tx.status === 'SUCCESS' && (
                  <button onClick={() => setConfirmRefund(true)} className="pg-btn-secondary text-xs">
                    <RotateCcw className="h-3.5 w-3.5" />
                    Issue Refund (SUCCESS → REFUNDED)
                  </button>
                )}
                {tx.status === 'PENDING' && (
                  <>
                    <button
                      onClick={() => reconcileMutation.mutate('SUCCESS')}
                      disabled={reconcileMutation.isPending}
                      className="pg-btn-primary text-xs"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Reconcile → SUCCESS
                    </button>
                    <button
                      onClick={() => reconcileMutation.mutate('FAILED')}
                      disabled={reconcileMutation.isPending}
                      className="pg-btn-danger text-xs"
                    >
                      <XCircle className="h-3.5 w-3.5" />
                      Reconcile → FAILED
                    </button>
                  </>
                )}
                <button
                  onClick={() => copyText(tx.idempotency_key, 'Idempotency Key')}
                  className="pg-btn-secondary text-xs"
                >
                  <Copy className="h-3.5 w-3.5" />
                  Copy Idempotency Key
                </button>
              </div>

              {tx.failure_reason && (
                <div className="rounded-md bg-red-500/10 border border-red-500/30 p-3 flex items-start gap-2.5">
                  <ShieldAlert className="h-4 w-4 text-red-400 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-xs font-semibold text-red-300">Failure / Timeout Diagnostic</p>
                    <p className="text-xs text-red-200/80 mt-0.5">{tx.failure_reason}</p>
                  </div>
                </div>
              )}

              {/* Database Record Summary */}
              <div className="pg-card p-3.5 space-y-2 text-xs">
                <div className="flex items-center gap-1.5 text-slate-300 font-medium mb-1">
                  <Database className="h-3.5 w-3.5 text-emerald-400" />
                  Persisted Database Record (transactions.id = #{tx.id})
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-y-1.5 gap-x-4 font-mono text-[11px]">
                  <div className="flex justify-between gap-2">
                    <span className="text-slate-500">idempotency_key</span>
                    <span className="text-slate-200 truncate">{tx.idempotency_key}</span>
                  </div>
                  <div className="flex justify-between gap-2">
                    <span className="text-slate-500">gateway_reference</span>
                    <span className="text-slate-200">{tx.gateway_reference || '—'}</span>
                  </div>
                  <div className="flex justify-between gap-2">
                    <span className="text-slate-500">scenario</span>
                    <span className="text-slate-200">{tx.scenario}</span>
                  </div>
                  <div className="flex justify-between gap-2">
                    <span className="text-slate-500">customer_ref</span>
                    <span className="text-slate-200">{tx.customer_reference || '—'}</span>
                  </div>
                </div>
              </div>

              {/* Tabs */}
              <div className="border-b border-[#222836] flex gap-4 text-xs">
                {(
                  [
                    ['timeline', `Lifecycle Timeline (${tx.timeline?.length || 0})`],
                    ['payloads', 'Request / Response JSON'],
                    ['webhooks', `Webhooks (${tx.webhooks.length})`],
                    ['links', `Tests & Bugs (${tx.related_bugs.length + tx.related_tests.length})`],
                  ] as const
                ).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setActiveTab(key)}
                    className={`pb-2.5 border-b-2 font-medium transition-colors ${
                      activeTab === key
                        ? 'border-emerald-500 text-emerald-400'
                        : 'border-transparent text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              {activeTab === 'timeline' && (
                <div className="space-y-3">
                  {(tx.timeline || []).map((step, idx) => (
                    <div key={`${step.stage}-${idx}`} className="flex gap-3">
                      <div className="flex flex-col items-center">
                        <div
                          className={`h-2.5 w-2.5 rounded-full mt-1.5 ${
                            step.status === 'FAILED'
                              ? 'bg-red-400'
                              : step.status === 'PENDING'
                                ? 'bg-amber-400'
                                : 'bg-emerald-400'
                          }`}
                        />
                        {idx < (tx.timeline?.length || 0) - 1 && (
                          <div className="w-px flex-1 bg-[#262E3F] my-1" />
                        )}
                      </div>
                      <div className="flex-1 pb-2">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-mono text-xs font-semibold text-slate-200">{step.stage}</span>
                          <span className="font-mono text-[11px] text-slate-500">+{step.elapsed_ms} ms</span>
                        </div>
                        <p className="text-xs text-slate-400 mt-0.5">{step.detail}</p>
                        <p className="text-[10px] font-mono text-slate-500 mt-0.5">{formatDateTime(step.timestamp)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {activeTab === 'payloads' && (
                <div className="space-y-4">
                  <div>
                    <p className="text-xs font-medium text-slate-300 mb-1.5">Request Payload</p>
                    <pre className="p-3 rounded-md bg-[#0A0C10] border border-[#222836] text-[11px] font-mono text-slate-300 overflow-x-auto">
                      {JSON.stringify(tx.request_payload || {}, null, 2)}
                    </pre>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-slate-300 mb-1.5">Response Payload</p>
                    <pre className="p-3 rounded-md bg-[#0A0C10] border border-[#222836] text-[11px] font-mono text-slate-300 overflow-x-auto">
                      {JSON.stringify(tx.response_payload || {}, null, 2)}
                    </pre>
                  </div>
                </div>
              )}

              {activeTab === 'webhooks' && (
                <div className="space-y-2.5">
                  {tx.webhooks.length === 0 ? (
                    <p className="text-xs text-slate-400 py-4 text-center">
                      No webhook events associated with this transaction yet.
                    </p>
                  ) : (
                    tx.webhooks.map((wh) => (
                      <div key={wh.event_id} className="pg-card p-3 flex items-center justify-between gap-3 text-xs">
                        <div>
                          <div className="flex items-center gap-2">
                            <Webhook className="h-3.5 w-3.5 text-slate-400" />
                            <span className="font-mono text-slate-200">{wh.event_id}</span>
                            <span className="text-slate-400">({wh.event_type})</span>
                          </div>
                          <p className="text-[11px] text-slate-500 mt-1">
                            Attempts: {wh.attempt_count} • Duplicates Blocked: {wh.duplicate_attempts} • Sig:{' '}
                            {wh.signature_valid ? 'Valid HMAC' : 'Invalid'}
                          </p>
                        </div>
                        <StatusBadge value={wh.delivery_status} />
                      </div>
                    ))
                  )}
                </div>
              )}

              {activeTab === 'links' && (
                <div className="space-y-4">
                  <div>
                    <p className="text-xs font-medium text-slate-300 mb-2">Linked Defect Reports</p>
                    {tx.related_bugs.length === 0 ? (
                      <p className="text-xs text-slate-500">No defects linked to this transaction.</p>
                    ) : (
                      <div className="space-y-2">
                        {tx.related_bugs.map((b) => (
                          <div key={b.bug_id} className="pg-card p-2.5 flex items-center justify-between text-xs">
                            <div>
                              <span className="font-mono text-slate-300 mr-2">{b.bug_id}</span>
                              <span className="text-slate-200">{b.title}</span>
                            </div>
                            <div className="flex items-center gap-1.5">
                              <StatusBadge value={b.severity} />
                              <StatusBadge value={b.status} />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <div>
                    <p className="text-xs font-medium text-slate-300 mb-2">Related Automated Test Cases</p>
                    {tx.related_tests.length === 0 ? (
                      <p className="text-xs text-slate-500">No executed test cases matched yet.</p>
                    ) : (
                      <div className="space-y-1.5">
                        {tx.related_tests.map((t, i) => (
                          <div key={`${t.run_id}-${i}`} className="pg-card p-2.5 flex items-center justify-between text-xs">
                            <span className="font-mono text-slate-300 truncate">{t.test_name}</span>
                            <div className="flex items-center gap-2 shrink-0">
                              <span className="text-[11px] text-slate-500">{t.duration.toFixed(2)}s</span>
                              <StatusBadge value={t.test_status} />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={confirmRefund}
        title="Confirm Sandbox Refund"
        description={`Transition transaction ${transactionId} from SUCCESS to REFUNDED? This state transition is irreversible under the payment state machine.`}
        confirmLabel="Issue Refund"
        danger={false}
        loading={refundMutation.isPending}
        onConfirm={() => refundMutation.mutate()}
        onCancel={() => setConfirmRefund(false)}
      />
    </div>
  );
};

