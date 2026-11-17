import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Eye, Loader2, RefreshCw, RotateCw, Send, ShieldCheck, ShieldX, X } from 'lucide-react';
import { EmptyState, ErrorBanner, TableSkeleton } from '../components/FeedbackStates';
import { SeededBadge, StatusBadge } from '../components/StatusBadge';
import { useToast } from '../components/ToastProvider';
import { extractErrorMessage, payguardApi } from '../services/api';
import type { WebhookEvent } from '../types';
import { formatDateTime } from '../utils/format';

export const WebhookMonitorPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const [statusFilter, setStatusFilter] = useState('ALL');
  const [selectedEvent, setSelectedEvent] = useState<WebhookEvent | null>(null);

  // Simulator controls
  const [txId, setTxId] = useState('');
  const [eventType, setEventType] = useState<'payment.success' | 'payment.failed' | 'payment.pending' | 'payment.refunded'>('payment.success');
  const [invalidSig, setInvalidSig] = useState(false);
  const [duplicateMode, setDuplicateMode] = useState(false);
  const [failDelivery, setFailDelivery] = useState(false);
  const [delayMs, setDelayMs] = useState(0);

  const eventsQ = useQuery({
    queryKey: ['webhooks', statusFilter],
    queryFn: () =>
      payguardApi.listWebhookEvents({
        delivery_status: statusFilter !== 'ALL' ? statusFilter : undefined,
      }),
  });

  const txListQ = useQuery({
    queryKey: ['webhooks-tx-selector'],
    queryFn: () => payguardApi.listPayments({ page: 1, page_size: 30 }),
  });

  const transactions = txListQ.data?.items || [];
  const effectiveTxId = txId || transactions[0]?.transaction_id || '';

  const simulateMutation = useMutation({
    mutationFn: () =>
      payguardApi.simulateWebhook({
        transaction_id: effectiveTxId,
        event_type: eventType,
        simulate_invalid_signature: invalidSig,
        simulate_duplicate: duplicateMode,
        simulate_delivery_failure: failDelivery,
        delay_ms: delayMs,
      }),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });

      if (res.status === 401) {
        addToast('warning', 'Invalid Signature Rejected (401)', res.errorMessage || 'HMAC mismatch logged.');
      } else if (res.deduplicated) {
        addToast(
          'info',
          'Duplicate Webhook Deduplicated',
          `Event ${res.event.event_id} was already processed; transaction was NOT processed twice.`,
        );
      } else if (res.event.delivery_status === 'FAILED') {
        addToast('error', 'Simulated Delivery Failure', `Event ${res.event.event_id} queued for retry.`);
      } else {
        addToast('success', 'Webhook Delivered', `${res.event.event_id} (${res.event.event_type}) processed.`);
      }
    },
    onError: (err) => addToast('error', 'Webhook Simulation Failed', extractErrorMessage(err)),
  });

  const retryMutation = useMutation({
    mutationFn: (eventId: string) => payguardApi.retryWebhookEvent(eventId),
    onSuccess: (ev) => {
      addToast('success', 'Webhook Retry Succeeded', `${ev.event_id} marked ${ev.delivery_status}.`);
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
    },
    onError: (err) => addToast('error', 'Retry Failed', extractErrorMessage(err)),
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-100">Webhook Monitor</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Verify HMAC-SHA256 signatures, enforce database-level event deduplication, and simulate delayed or failed webhook retries.
          </p>
        </div>
        <button onClick={() => eventsQ.refetch()} className="pg-btn-secondary text-xs self-start">
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh Events
        </button>
      </div>

      {/* Webhook Delivery Simulator Card */}
      <div className="pg-card p-4 space-y-4">
        <div className="flex items-center justify-between border-b border-[#222836] pb-2.5">
          <h2 className="text-sm font-semibold text-slate-200">Simulate Webhook Delivery</h2>
          <span className="text-[11px] font-mono text-emerald-400">HMAC-SHA256 signed server-side</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div>
            <label className="block text-xs text-slate-400 mb-1" htmlFor="wh-tx-select">
              Target Transaction
            </label>
            <select
              id="wh-tx-select"
              value={effectiveTxId}
              onChange={(e) => setTxId(e.target.value)}
              className="pg-select w-full font-mono text-xs"
            >
              {transactions.map((t) => (
                <option key={t.transaction_id} value={t.transaction_id}>
                  {t.transaction_id} ({t.status})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1" htmlFor="wh-type-select">
              Event Type
            </label>
            <select
              id="wh-type-select"
              value={eventType}
              onChange={(e) => setEventType(e.target.value as any)}
              className="pg-select w-full font-mono text-xs"
            >
              <option value="payment.success">payment.success</option>
              <option value="payment.failed">payment.failed</option>
              <option value="payment.pending">payment.pending</option>
              <option value="payment.refunded">payment.refunded</option>
            </select>
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1" htmlFor="wh-delay">
              Simulated Delay (ms)
            </label>
            <input
              id="wh-delay"
              type="number"
              min={0}
              max={3000}
              step={100}
              value={delayMs}
              onChange={(e) => setDelayMs(Number(e.target.value))}
              className="pg-input font-mono text-xs"
            />
          </div>

          <div className="flex items-end">
            <button
              type="button"
              onClick={() => simulateMutation.mutate()}
              disabled={simulateMutation.isPending || !effectiveTxId}
              className="pg-btn-primary text-xs w-full"
            >
              {simulateMutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Send className="h-3.5 w-3.5" />
              )}
              Dispatch Webhook
            </button>
          </div>
        </div>

        <div className="flex flex-wrap gap-5 text-xs text-slate-300 pt-1">
          <label className="inline-flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={duplicateMode}
              onChange={(e) => setDuplicateMode(e.target.checked)}
              className="accent-emerald-500"
            />
            Simulate Duplicate Delivery (reuses last event_id)
          </label>
          <label className="inline-flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={invalidSig}
              onChange={(e) => setInvalidSig(e.target.checked)}
              className="accent-red-500"
            />
            Simulate Invalid HMAC Signature (401)
          </label>
          <label className="inline-flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={failDelivery}
              onChange={(e) => setFailDelivery(e.target.checked)}
              className="accent-amber-500"
            />
            Simulate Failed Delivery (for retry testing)
          </label>
        </div>
      </div>

      {/* Filter & Events Table */}
      <div className="pg-card overflow-hidden">
        <div className="px-4 py-3 border-b border-[#222836] bg-[#0D1016] flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs font-semibold text-slate-200">Persisted Webhook Event Log</span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="pg-select py-1 text-xs"
            aria-label="Filter webhook delivery status"
          >
            <option value="ALL">All Statuses</option>
            <option value="DELIVERED">DELIVERED</option>
            <option value="FAILED">FAILED</option>
            <option value="INVALID_SIGNATURE">INVALID_SIGNATURE</option>
          </select>
        </div>

        {eventsQ.isError && <ErrorBanner message={extractErrorMessage(eventsQ.error)} />}

        {eventsQ.isLoading ? (
          <TableSkeleton rows={6} />
        ) : (eventsQ.data || []).length === 0 ? (
          <EmptyState title="No webhook events" description="Dispatch a simulated webhook above to inspect HMAC verification." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#0D1016] text-slate-400 border-b border-[#222836]">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Event ID</th>
                  <th className="px-4 py-2.5 font-medium">Event Type</th>
                  <th className="px-4 py-2.5 font-medium">Transaction ID</th>
                  <th className="px-4 py-2.5 font-medium">HMAC Sig</th>
                  <th className="px-4 py-2.5 font-medium">Delivery Status</th>
                  <th className="px-4 py-2.5 font-medium">Attempts</th>
                  <th className="px-4 py-2.5 font-medium">Timestamp</th>
                  <th className="px-4 py-2.5 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1D2330]">
                {(eventsQ.data || []).map((ev) => (
                  <tr key={ev.event_id} className="hover:bg-[#161C27]">
                    <td className="px-4 py-2.5 font-mono text-slate-100 whitespace-nowrap">
                      <span className="inline-flex items-center gap-1.5">
                        {ev.event_id}
                        <SeededBadge isSeeded={ev.is_seeded} />
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-slate-300">{ev.event_type}</td>
                    <td className="px-4 py-2.5 font-mono text-slate-400">{ev.transaction_id || '—'}</td>
                    <td className="px-4 py-2.5">
                      {ev.signature_valid ? (
                        <span className="inline-flex items-center gap-1 text-emerald-400 font-mono text-[11px]">
                          <ShieldCheck className="h-3.5 w-3.5" /> Valid
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-red-400 font-mono text-[11px]">
                          <ShieldX className="h-3.5 w-3.5" /> Invalid
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <StatusBadge value={ev.delivery_status} />
                    </td>
                    <td className="px-4 py-2.5 font-mono text-slate-300">
                      {ev.attempt_count}
                      {ev.duplicate_attempts > 0 && (
                        <span className="text-amber-400 ml-1">({ev.duplicate_attempts} dup)</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-slate-400 whitespace-nowrap">{formatDateTime(ev.created_at)}</td>
                    <td className="px-4 py-2.5 text-right whitespace-nowrap space-x-1.5">
                      {ev.delivery_status === 'FAILED' && (
                        <button
                          onClick={() => retryMutation.mutate(ev.event_id)}
                          disabled={retryMutation.isPending}
                          className="inline-flex items-center gap-1 px-2 py-1 rounded bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 text-amber-300 text-[11px]"
                        >
                          <RotateCw className="h-3 w-3" /> Retry
                        </button>
                      )}
                      <button
                        onClick={() => setSelectedEvent(ev)}
                        className="inline-flex items-center gap-1 px-2 py-1 rounded bg-[#181E2A] hover:bg-[#232C3D] text-slate-200 text-[11px]"
                      >
                        <Eye className="h-3 w-3" /> Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Event Details Modal */}
      {selectedEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="dialog">
          <div className="w-full max-w-xl rounded-lg bg-[#12161F] border border-[#2A3244] shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-[#222836]">
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm font-semibold text-slate-100">{selectedEvent.event_id}</span>
                <StatusBadge value={selectedEvent.delivery_status} />
              </div>
              <button onClick={() => setSelectedEvent(null)} className="text-slate-400 hover:text-slate-200">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="p-4 space-y-4 max-h-[75vh] overflow-y-auto text-xs">
              <div>
                <p className="font-medium text-slate-300 mb-1.5">Webhook Payload</p>
                <pre className="p-3 rounded bg-[#0A0C10] border border-[#222836] font-mono text-[11px] text-slate-300 overflow-x-auto">
                  {JSON.stringify(selectedEvent.payload, null, 2)}
                </pre>
              </div>
              <div>
                <p className="font-medium text-slate-300 mb-1.5">Event Processing Logs</p>
                <div className="space-y-1.5">
                  {(selectedEvent.processing_logs || []).map((log, idx) => (
                    <div key={idx} className="p-2 rounded bg-[#0D1016] border border-[#222836] font-mono text-[11px]">
                      <span className="text-slate-500 mr-2">{formatDateTime(log.timestamp)}</span>
                      <span
                        className={
                          log.level === 'ERROR'
                            ? 'text-red-400'
                            : log.level === 'WARNING'
                              ? 'text-amber-300'
                              : 'text-emerald-400'
                        }
                      >
                        [{log.level}]
                      </span>{' '}
                      <span className="text-slate-200">{log.message}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

