import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, CheckCircle2, Database, Loader2, Play, Search, ShieldCheck } from 'lucide-react';
import { EmptyState, ErrorBanner, TableSkeleton } from '../components/FeedbackStates';
import { StatusBadge } from '../components/StatusBadge';
import { useToast } from '../components/ToastProvider';
import { extractErrorMessage, payguardApi } from '../services/api';
import type { ConsistencyReport } from '../types';
import { formatDateTime } from '../utils/format';

export const DatabaseValidationPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const [selectedChecks, setSelectedChecks] = useState<string[]>([]);
  const [txIdInput, setTxIdInput] = useState('');
  const [consistencyReport, setConsistencyReport] = useState<ConsistencyReport | null>(null);

  const checksQ = useQuery({
    queryKey: ['validation-checks'],
    queryFn: payguardApi.getValidationChecks,
  });

  const resultsQ = useQuery({
    queryKey: ['validation-results'],
    queryFn: payguardApi.listValidationResults,
  });

  const txListQ = useQuery({
    queryKey: ['validation-tx-list'],
    queryFn: () => payguardApi.listPayments({ page: 1, page_size: 25 }),
  });

  const runMutation = useMutation({
    mutationFn: (keys?: string[]) => payguardApi.runValidationChecks(keys && keys.length ? keys : undefined),
    onSuccess: (results) => {
      queryClient.invalidateQueries({ queryKey: ['validation-results'] });
      const failed = results.filter((r) => r.execution_status !== 'PASS').length;
      addToast(
        failed > 0 ? 'warning' : 'success',
        'Database Validation Complete',
        `${results.length - failed}/${results.length} integrity checks passed.`,
      );
    },
    onError: (err) => addToast('error', 'Validation Failed', extractErrorMessage(err)),
  });

  const consistencyMutation = useMutation({
    mutationFn: (id: string) => payguardApi.checkConsistency(id.trim()),
    onSuccess: (report) => {
      setConsistencyReport(report);
      addToast(
        report.consistent ? 'success' : 'warning',
        report.consistent ? 'Transaction Consistent' : 'Discrepancy Detected',
        report.consistent
          ? `${report.transaction_id} matches across API, DB, and Webhook records.`
          : `${report.discrepancies.length} discrepancy(ies) found for ${report.transaction_id}.`,
      );
    },
    onError: (err) => addToast('error', 'Consistency Check Error', extractErrorMessage(err)),
  });

  const toggleCheck = (key: string) => {
    setSelectedChecks((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));
  };

  const checks = checksQ.data || [];
  const results = resultsQ.data || [];
  const txs = txListQ.data?.items || [];
  const effectiveTxId = txIdInput || txs[0]?.transaction_id || '';

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-100">Database Validation Console</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Run predefined parameterized read-only SQLAlchemy integrity checks and cross-layer transaction consistency verification.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => runMutation.mutate(selectedChecks)}
            disabled={runMutation.isPending}
            className="pg-btn-primary text-xs"
          >
            {runMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
            {selectedChecks.length > 0 ? `Run Selected (${selectedChecks.length})` : 'Run All 8 Checks'}
          </button>
        </div>
      </div>

      {/* Predefined Validation Checks */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {checks.map((check) => {
          const isChecked = selectedChecks.includes(check.check_key);
          return (
            <label
              key={check.check_key}
              className={`pg-card p-3.5 cursor-pointer transition-colors flex flex-col justify-between gap-2 ${
                isChecked ? 'border-emerald-500/50 bg-emerald-500/5' : 'hover:border-[#2E3648]'
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="text-xs font-semibold text-slate-200">{check.check_name}</span>
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={() => toggleCheck(check.check_key)}
                  className="accent-emerald-500 mt-0.5"
                />
              </div>
              <p className="text-[11px] text-slate-400 leading-snug">{check.description}</p>
              <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500">{check.category}</span>
            </label>
          );
        })}
      </div>

      {/* Transaction Consistency Checker */}
      <div className="pg-card p-4 space-y-4">
        <div className="flex items-center justify-between border-b border-[#222836] pb-2.5">
          <div>
            <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
              Transaction Consistency Checker
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Compares API Response Payload vs Database Record vs Webhook Event vs Final Payment State.
            </p>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-2.5">
          <select
            value={effectiveTxId}
            onChange={(e) => setTxIdInput(e.target.value)}
            className="pg-select font-mono text-xs flex-1"
            aria-label="Select transaction to check consistency"
          >
            {txs.map((t) => (
              <option key={t.transaction_id} value={t.transaction_id}>
                {t.transaction_id} — {t.order_id} ({t.status} • {t.currency} {t.amount})
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => effectiveTxId && consistencyMutation.mutate(effectiveTxId)}
            disabled={consistencyMutation.isPending || !effectiveTxId}
            className="pg-btn-secondary text-xs shrink-0"
          >
            {consistencyMutation.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Search className="h-3.5 w-3.5" />
            )}
            Verify Consistency
          </button>
        </div>

        {consistencyReport && (
          <div className="rounded-lg bg-[#0D1016] border border-[#222836] p-4 space-y-3 text-xs">
            <div className="flex items-center justify-between">
              <span className="font-mono font-semibold text-slate-100">{consistencyReport.transaction_id}</span>
              {consistencyReport.consistent ? (
                <span className="inline-flex items-center gap-1.5 text-emerald-400 font-medium">
                  <CheckCircle2 className="h-4 w-4" /> All Layers Consistent
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 text-red-400 font-medium">
                  <AlertCircle className="h-4 w-4" /> Discrepancies Found
                </span>
              )}
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="p-2.5 rounded bg-[#11141B] border border-[#222836]">
                <p className="text-[10px] text-slate-500 uppercase">API Response Status</p>
                <p className="font-mono text-slate-200 mt-1">{consistencyReport.api_response_status || '—'}</p>
              </div>
              <div className="p-2.5 rounded bg-[#11141B] border border-[#222836]">
                <p className="text-[10px] text-slate-500 uppercase">DB Transaction Status</p>
                <p className="font-mono text-slate-200 mt-1">{consistencyReport.db_status || '—'}</p>
              </div>
              <div className="p-2.5 rounded bg-[#11141B] border border-[#222836]">
                <p className="text-[10px] text-slate-500 uppercase">Latest Webhook</p>
                <p className="font-mono text-slate-200 mt-1">
                  {consistencyReport.latest_webhook_event
                    ? `${consistencyReport.latest_webhook_event} (${consistencyReport.latest_webhook_status})`
                    : 'None'}
                </p>
              </div>
              <div className="p-2.5 rounded bg-[#11141B] border border-[#222836]">
                <p className="text-[10px] text-slate-500 uppercase">Amount Match</p>
                <p
                  className={`font-mono mt-1 ${
                    consistencyReport.amount_consistent ? 'text-emerald-400' : 'text-red-400'
                  }`}
                >
                  {consistencyReport.amount_consistent ? 'EXACT DECIMAL MATCH' : 'MISMATCH'}
                </p>
              </div>
            </div>

            {consistencyReport.discrepancies.length > 0 && (
              <div className="rounded bg-red-500/10 border border-red-500/30 p-3 space-y-1 text-red-200">
                {consistencyReport.discrepancies.map((d, i) => (
                  <p key={i}>• {d}</p>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Validation Results History Table */}
      <div className="pg-card overflow-hidden">
        <div className="px-4 py-3 border-b border-[#222836] bg-[#0D1016] flex items-center gap-2">
          <Database className="h-4 w-4 text-slate-400" />
          <h2 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">Validation Results</h2>
        </div>

        {resultsQ.isError && <ErrorBanner message={extractErrorMessage(resultsQ.error)} />}

        {resultsQ.isLoading ? (
          <TableSkeleton rows={5} />
        ) : results.length === 0 ? (
          <EmptyState
            title="No validation checks executed yet"
            description='Click "Run All 8 Checks" above to audit database integrity.'
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#0D1016] text-slate-400 border-b border-[#222836]">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Check Name</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">Records Examined</th>
                  <th className="px-4 py-2.5 font-medium">Issues Detected</th>
                  <th className="px-4 py-2.5 font-medium">Duration</th>
                  <th className="px-4 py-2.5 font-medium">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1D2330]">
                {results.map((r) => (
                  <tr key={r.id} className="hover:bg-[#161C27]">
                    <td className="px-4 py-2.5">
                      <p className="font-medium text-slate-200">{r.check_name}</p>
                      {r.details && r.details.length > 0 && (
                        <pre className="text-[10px] font-mono text-red-300 mt-1 bg-red-500/10 p-1.5 rounded overflow-x-auto">
                          {JSON.stringify(r.details, null, 2)}
                        </pre>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <StatusBadge value={r.execution_status} />
                    </td>
                    <td className="px-4 py-2.5 font-mono text-slate-300">{r.records_examined}</td>
                    <td className="px-4 py-2.5 font-mono">
                      <span className={r.issues_detected > 0 ? 'text-red-400 font-semibold' : 'text-emerald-400'}>
                        {r.issues_detected}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-slate-400">{r.execution_duration_ms.toFixed(2)} ms</td>
                    <td className="px-4 py-2.5 text-slate-400">{formatDateTime(r.executed_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

