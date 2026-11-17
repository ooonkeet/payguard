import React, { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Copy,
  CreditCard,
  Loader2,
  Play,
  RefreshCw,
  ShieldAlert,
  X,
  XCircle,
} from 'lucide-react';
import { StatusBadge } from '../components/StatusBadge';
import { useToast } from '../components/ToastProvider';
import { extractErrorMessage, payguardApi } from '../services/api';
import type { PaymentMethod, PaymentScenario, SupportedCurrency, Transaction } from '../types';
import { formatCurrency, formatDateTime, formatDurationMs, generateIdempotencyKey, generateOrderId } from '../utils/format';

const SCENARIOS: Array<{ value: PaymentScenario; label: string; hint: string }> = [
  { value: 'successful_payment', label: '1. Successful Payment', hint: 'Authorized & captured (SUCCESS)' },
  { value: 'insufficient_balance', label: '2. Insufficient Balance', hint: 'Issuer decline code 51 (FAILED)' },
  { value: 'invalid_payment_details', label: '3. Invalid Payment Details', hint: 'Synthetic instrument rejected (FAILED)' },
  { value: 'gateway_timeout', label: '4. Gateway Timeout', hint: 'Unknown outcome — stays PENDING for reconciliation' },
  { value: 'gateway_unavailable', label: '5. Gateway Unavailable', hint: 'Upstream 503 circuit open (FAILED)' },
  { value: 'pending_transaction', label: '6. Pending Transaction', hint: 'Awaiting async issuer confirmation (PENDING)' },
  { value: 'delayed_webhook', label: '7. Delayed Webhook', hint: 'PENDING until settlement webhook arrives' },
  { value: 'duplicate_payment_request', label: '8. Duplicate Payment Request', hint: 'Tests idempotent replay with same key' },
  { value: 'payment_failure', label: '9. Payment Failure', hint: 'Acquirer risk authorization decline (FAILED)' },
  { value: 'processing_error', label: '10. Processing Error', hint: 'Simulated ISO-8583 switch error 96 (FAILED)' },
];

const LIFECYCLE_STAGES = [
  'REQUEST_RECEIVED',
  'VALIDATING',
  'PROCESSING',
  'GATEWAY_RESPONSE',
  'TRANSACTION_UPDATED',
  'COMPLETED',
];

export const PaymentSimulatorPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const [orderId, setOrderId] = useState(generateOrderId);
  const [amount, setAmount] = useState('1499.00');
  const [currency, setCurrency] = useState<SupportedCurrency>('INR');
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('UPI');
  const [customerReference, setCustomerReference] = useState('cust_sandbox_qa_01');
  const [idempotencyKey, setIdempotencyKey] = useState(() => generateIdempotencyKey('idem-sim'));
  const [scenario, setScenario] = useState<PaymentScenario>('successful_payment');

  const [lastResult, setLastResult] = useState<{ tx: Transaction; replay: boolean } | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [conflictError, setConflictError] = useState<string | null>(null);

  const simulateMutation = useMutation({
    mutationFn: () =>
      payguardApi.createPayment({
        order_id: orderId.trim(),
        amount: amount.trim(),
        currency,
        payment_method: paymentMethod,
        customer_reference: customerReference.trim() || undefined,
        idempotency_key: idempotencyKey.trim(),
        scenario,
      }),
    onSuccess: ({ transaction, idempotentReplay }) => {
      setConflictError(null);
      setLastResult({ tx: transaction, replay: idempotentReplay });
      setShowModal(true);
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });

      if (idempotentReplay) {
        addToast(
          'info',
          'Idempotent Replay Returned',
          `Preserved existing transaction ${transaction.transaction_id} without creating a duplicate.`,
        );
      } else if (transaction.status === 'SUCCESS') {
        addToast('success', 'Payment Captured', `${transaction.transaction_id} succeeded (${transaction.response_code}).`);
      } else if (transaction.status === 'PENDING') {
        addToast('warning', 'Payment Pending', `${transaction.transaction_id} requires webhook or reconciliation.`);
      } else {
        addToast('error', 'Payment Failed', `${transaction.transaction_id}: ${transaction.response_code}`);
      }
    },
    onError: (err) => {
      const msg = extractErrorMessage(err);
      setConflictError(msg);
      addToast('error', 'Payment Request Rejected', msg);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setConflictError(null);
    simulateMutation.mutate();
  };

  const resetForFreshPayment = () => {
    setOrderId(generateOrderId());
    setIdempotencyKey(generateIdempotencyKey('idem-sim'));
    setConflictError(null);
  };

  const activeTimeline = lastResult?.tx.timeline || [];
  const completedStages = new Set(activeTimeline.map((t) => t.stage));

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-100">Payment Simulator</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Execute real FastAPI payment simulations with database-enforced idempotency, state machine validation, and timeout handling.
          </p>
        </div>
        <button type="button" onClick={resetForFreshPayment} className="pg-btn-secondary text-xs self-start">
          <RefreshCw className="h-3.5 w-3.5" />
          New Order & Idempotency Key
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Form Panel */}
        <form onSubmit={handleSubmit} className="pg-card p-5 lg:col-span-7 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-[#222836]">
            <div className="flex items-center gap-2">
              <CreditCard className="h-4 w-4 text-emerald-400" />
              <h2 className="text-sm font-semibold text-slate-200">Synthetic Payment Request</h2>
            </div>
            <span className="text-[11px] font-mono text-amber-400">NO REAL FUNDS</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5" htmlFor="sim-order-id">
                Order ID
              </label>
              <input
                id="sim-order-id"
                type="text"
                required
                value={orderId}
                onChange={(e) => setOrderId(e.target.value)}
                className="pg-input font-mono text-xs"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5" htmlFor="sim-customer">
                Customer Reference
              </label>
              <input
                id="sim-customer"
                type="text"
                value={customerReference}
                onChange={(e) => setCustomerReference(e.target.value)}
                className="pg-input font-mono text-xs"
                placeholder="cust_synth_01"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5" htmlFor="sim-amount">
                Amount (Decimal)
              </label>
              <input
                id="sim-amount"
                type="number"
                step="0.01"
                required
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="pg-input font-mono text-xs"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5" htmlFor="sim-currency">
                Currency
              </label>
              <select
                id="sim-currency"
                value={currency}
                onChange={(e) => setCurrency(e.target.value as SupportedCurrency)}
                className="pg-select w-full text-xs"
              >
                <option value="INR">INR — Indian Rupee</option>
                <option value="USD">USD — US Dollar</option>
                <option value="EUR">EUR — Euro</option>
                <option value="GBP">GBP — British Pound</option>
                <option value="SGD">SGD — Singapore Dollar</option>
              </select>
            </div>
          </div>

          {/* Payment Method Selector */}
          <div>
            <span className="block text-xs font-medium text-slate-300 mb-1.5">Payment Method (Simulated)</span>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {(
                [
                  ['UPI', 'UPI (Simulated)'],
                  ['CARD', 'Card (Synthetic)'],
                  ['NET_BANKING', 'Net Banking'],
                  ['WALLET', 'Wallet'],
                ] as const
              ).map(([val, label]) => (
                <button
                  key={val}
                  type="button"
                  onClick={() => setPaymentMethod(val)}
                  className={`px-3 py-2 rounded-md border text-xs font-medium transition-colors ${
                    paymentMethod === val
                      ? 'bg-emerald-500/10 border-emerald-500/50 text-emerald-300'
                      : 'bg-[#0D1016] border-[#262D3D] text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Idempotency Key */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-slate-300" htmlFor="sim-idem-key">
                Idempotency Key
              </label>
              <button
                type="button"
                onClick={() => setIdempotencyKey(generateIdempotencyKey('idem-sim'))}
                className="text-[11px] text-emerald-400 hover:text-emerald-300"
              >
                Regenerate Key
              </button>
            </div>
            <input
              id="sim-idem-key"
              type="text"
              required
              value={idempotencyKey}
              onChange={(e) => setIdempotencyKey(e.target.value)}
              className="pg-input font-mono text-xs"
            />
            <p className="text-[11px] text-slate-500 mt-1">
              Re-submit with identical payload to test idempotent replay (200), or modify amount with the same key to verify HTTP 409 Conflict.
            </p>
          </div>

          {/* Scenario Selection */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5" htmlFor="sim-scenario">
              Simulation Scenario
            </label>
            <select
              id="sim-scenario"
              value={scenario}
              onChange={(e) => setScenario(e.target.value as PaymentScenario)}
              className="pg-select w-full text-xs"
            >
              {SCENARIOS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label} — {s.hint}
                </option>
              ))}
            </select>
          </div>

          {conflictError && (
            <div className="rounded-md bg-red-500/10 border border-red-500/35 p-3 flex items-start gap-2.5">
              <ShieldAlert className="h-4 w-4 text-red-400 mt-0.5 shrink-0" />
              <div className="text-xs text-red-200">
                <p className="font-semibold text-red-300">Backend Rejection</p>
                <p className="mt-0.5">{conflictError}</p>
              </div>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2.5 pt-2">
            <button type="submit" disabled={simulateMutation.isPending} className="pg-btn-primary">
              {simulateMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Processing Transaction...
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  Simulate Payment
                </>
              )}
            </button>

            {lastResult && (
              <button
                type="button"
                onClick={() => setShowModal(true)}
                className="pg-btn-secondary text-xs"
              >
                View Last Result
              </button>
            )}
          </div>
        </form>

        {/* Live Lifecycle Visualization Panel */}
        <div className="pg-card p-5 lg:col-span-5 flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-[#222836]">
              <h2 className="text-sm font-semibold text-slate-200">Backend Processing Lifecycle</h2>
              {lastResult && <StatusBadge value={lastResult.tx.status} />}
            </div>

            <div className="mt-4 space-y-3">
              {LIFECYCLE_STAGES.map((stage, idx) => {
                const event = activeTimeline.find((t) => t.stage === stage);
                const isDone = completedStages.has(stage);
                const isProcessingNow = simulateMutation.isPending && idx <= 2;

                return (
                  <div key={stage} className="flex items-start gap-3">
                    <div className="mt-0.5">
                      {isProcessingNow ? (
                        <Loader2 className="h-4 w-4 text-sky-400 animate-spin" />
                      ) : isDone ? (
                        event?.status === 'FAILED' ? (
                          <XCircle className="h-4 w-4 text-red-400" />
                        ) : event?.status === 'PENDING' ? (
                          <Clock className="h-4 w-4 text-amber-400" />
                        ) : (
                          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                        )
                      ) : (
                        <div className="h-4 w-4 rounded-full border border-[#2F384C] bg-[#0D1016]" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span
                          className={`font-mono text-xs font-medium ${
                            isDone ? 'text-slate-100' : 'text-slate-500'
                          }`}
                        >
                          {stage.replace(/_/g, ' ')}
                        </span>
                        {event && <span className="font-mono text-[10px] text-slate-500">+{event.elapsed_ms}ms</span>}
                      </div>
                      <p className="text-[11px] text-slate-400 mt-0.5">
                        {event
                          ? event.detail
                          : simulateMutation.isPending
                            ? 'Awaiting backend state update...'
                            : 'Pending execution'}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Engineering Guarantees Box */}
          <div className="rounded-md bg-[#0D1016] border border-[#222836] p-3 text-[11px] text-slate-400 space-y-1.5">
            <p className="font-semibold text-slate-300">Enforced Payment Engineering Rules</p>
            <p>• Idempotency keys use SHA-256 payload fingerprinting & DB unique constraints.</p>
            <p>• Gateway timeouts stay PENDING instead of falsely marking FAILED.</p>
            <p>• State transitions follow CREATED → PROCESSING → SUCCESS / FAILED / PENDING.</p>
          </div>
        </div>
      </div>

      {/* Transaction Result Modal */}
      {showModal && lastResult && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-lg rounded-lg bg-[#12161F] border border-[#2A3244] shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-[#222836]">
              <div className="flex items-center gap-2.5">
                {lastResult.tx.status === 'SUCCESS' ? (
                  <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                ) : lastResult.tx.status === 'PENDING' ? (
                  <AlertTriangle className="h-5 w-5 text-amber-400" />
                ) : (
                  <XCircle className="h-5 w-5 text-red-400" />
                )}
                <div>
                  <h3 className="text-sm font-semibold text-slate-100">Transaction Result</h3>
                  {lastResult.replay && (
                    <span className="text-[11px] font-mono text-sky-400">
                      IDEMPOTENT REPLAY — Original transaction returned
                    </span>
                  )}
                </div>
              </div>
              <button onClick={() => setShowModal(false)} className="text-slate-400 hover:text-slate-200">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="p-5 space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div className="p-2.5 rounded bg-[#0D1016] border border-[#222836]">
                  <p className="text-slate-500">Transaction ID</p>
                  <p className="font-mono text-slate-100 mt-0.5">{lastResult.tx.transaction_id}</p>
                </div>
                <div className="p-2.5 rounded bg-[#0D1016] border border-[#222836]">
                  <p className="text-slate-500">Status</p>
                  <div className="mt-1">
                    <StatusBadge value={lastResult.tx.status} />
                  </div>
                </div>
                <div className="p-2.5 rounded bg-[#0D1016] border border-[#222836]">
                  <p className="text-slate-500">Order ID</p>
                  <p className="font-mono text-slate-200 mt-0.5">{lastResult.tx.order_id}</p>
                </div>
                <div className="p-2.5 rounded bg-[#0D1016] border border-[#222836]">
                  <p className="text-slate-500">Amount</p>
                  <p className="font-mono text-slate-100 mt-0.5">
                    {formatCurrency(lastResult.tx.amount, lastResult.tx.currency)}
                  </p>
                </div>
                <div className="p-2.5 rounded bg-[#0D1016] border border-[#222836]">
                  <p className="text-slate-500">Response Code</p>
                  <p className="font-mono text-slate-200 mt-0.5">{lastResult.tx.response_code}</p>
                </div>
                <div className="p-2.5 rounded bg-[#0D1016] border border-[#222836]">
                  <p className="text-slate-500">Processing Time</p>
                  <p className="font-mono text-slate-200 mt-0.5">
                    {formatDurationMs(lastResult.tx.processing_duration_ms)}
                  </p>
                </div>
                <div className="p-2.5 rounded bg-[#0D1016] border border-[#222836]">
                  <p className="text-slate-500">Gateway Reference</p>
                  <p className="font-mono text-slate-200 mt-0.5">{lastResult.tx.gateway_reference || '—'}</p>
                </div>
                <div className="p-2.5 rounded bg-[#0D1016] border border-[#222836]">
                  <p className="text-slate-500">Timestamp</p>
                  <p className="font-mono text-slate-200 mt-0.5">{formatDateTime(lastResult.tx.created_at)}</p>
                </div>
              </div>

              {lastResult.tx.failure_reason && (
                <div className="rounded bg-red-500/10 border border-red-500/30 p-3 text-red-200">
                  <p className="font-semibold text-red-300">Failure / Reconciliation Reason</p>
                  <p className="mt-0.5">{lastResult.tx.failure_reason}</p>
                </div>
              )}
            </div>

            <div className="flex items-center justify-between px-5 py-3 bg-[#0D1016] border-t border-[#222836]">
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(lastResult.tx.transaction_id);
                  addToast('info', 'Copied', lastResult.tx.transaction_id);
                }}
                className="pg-btn-secondary text-xs"
              >
                <Copy className="h-3.5 w-3.5" />
                Copy TXN ID
              </button>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowModal(false);
                    resetForFreshPayment();
                  }}
                  className="pg-btn-secondary text-xs"
                >
                  New Payment
                </button>
                <button type="button" onClick={() => setShowModal(false)} className="pg-btn-primary text-xs">
                  Done
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

