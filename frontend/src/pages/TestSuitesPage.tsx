import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bug, ExternalLink, FlaskConical, Loader2, Play, RefreshCw } from 'lucide-react';
import { EmptyState, ErrorBanner, TableSkeleton } from '../components/FeedbackStates';
import { SeededBadge, StatusBadge } from '../components/StatusBadge';
import { useToast } from '../components/ToastProvider';
import { extractErrorMessage, payguardApi } from '../services/api';
import type { TestSuiteName } from '../types';
import { formatDateTime } from '../utils/format';

const SUITES: Array<{ key: TestSuiteName; label: string; desc: string }> = [
  { key: 'all', label: 'RUN ALL TESTS', desc: 'Execute complete backend automation suite (API + Payment + Webhook + DB + Integration)' },
  { key: 'smoke', label: 'RUN SMOKE TESTS', desc: 'Fast critical-path API & payment health checks' },
  { key: 'regression', label: 'RUN REGRESSION TESTS', desc: 'Core payment flows, idempotency & negative validation' },
  { key: 'edge_cases', label: 'RUN EDGE CASE TESTS', desc: 'Concurrency, timeouts, state machine & webhook edge cases' },
  { key: 'api_contract', label: 'RUN API CONTRACT TESTS', desc: 'HTTP status, JSON schema, auth & error envelope contracts' },
  { key: 'database', label: 'RUN DATABASE TESTS', desc: 'Uniqueness, decimal precision, FK & DB validation checks' },
];

export const TestSuitesPage: React.FC = () => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [runningSuite, setRunningSuite] = useState<TestSuiteName | null>(null);

  const runsQ = useQuery({
    queryKey: ['test-runs'],
    queryFn: () => payguardApi.listTestRuns(),
  });

  const activeRunId = selectedRunId || runsQ.data?.[0]?.run_id || null;

  const detailQ = useQuery({
    queryKey: ['test-run', activeRunId],
    queryFn: () => payguardApi.getTestRun(activeRunId!),
    enabled: Boolean(activeRunId),
  });

  const runMutation = useMutation({
    mutationFn: (suite: TestSuiteName) => {
      setRunningSuite(suite);
      return payguardApi.runTestSuite(suite, true);
    },
    onSuccess: (run) => {
      setRunningSuite(null);
      setSelectedRunId(run.run_id);
      queryClient.invalidateQueries({ queryKey: ['test-runs'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['reports'] });
      addToast(
        run.failed > 0 ? 'warning' : 'success',
        `Suite "${run.suite_name}" Completed`,
        `${run.passed}/${run.total_tests} passed (${run.pass_rate}%) in ${run.duration.toFixed(2)}s`,
      );
    },
    onError: (err) => {
      setRunningSuite(null);
      addToast('error', 'Test Execution Failed', extractErrorMessage(err));
    },
  });

  const activeRun = detailQ.data;

  const handleCreateBugFromFailure = (testName: string, failureMessage: string | null | undefined) => {
    const params = new URLSearchParams({
      prefillTitle: `Automated test failure: ${testName}`,
      prefillTest: testName,
      prefillActual: failureMessage || 'Test assertion failed during Pytest execution.',
      prefillModule: 'Automated Test Suites',
    });
    navigate(`/bugs?${params.toString()}`);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-100">Automated Test Suites</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Execute real Pytest suites against an isolated test database, capture per-case outcomes, and generate HTML reports.
          </p>
        </div>
        <button onClick={() => runsQ.refetch()} className="pg-btn-secondary text-xs self-start">
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh History
        </button>
      </div>

      {/* Suite Launch Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {SUITES.map((s) => {
          const isRunningThis = runMutation.isPending && runningSuite === s.key;
          return (
            <div key={s.key} className="pg-card p-4 flex flex-col justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <FlaskConical className="h-4 w-4 text-emerald-400 shrink-0" />
                  <span className="text-xs font-semibold font-mono text-slate-100">{s.label}</span>
                </div>
                <p className="text-[11px] text-slate-400 mt-1.5 leading-relaxed">{s.desc}</p>
              </div>
              <button
                type="button"
                onClick={() => runMutation.mutate(s.key)}
                disabled={runMutation.isPending}
                className={s.key === 'all' ? 'pg-btn-primary text-xs w-full' : 'pg-btn-secondary text-xs w-full'}
              >
                {isRunningThis ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Executing Pytest...
                  </>
                ) : (
                  <>
                    <Play className="h-3.5 w-3.5" />
                    {s.label}
                  </>
                )}
              </button>
            </div>
          );
        })}
      </div>

      {runsQ.isError && <ErrorBanner message={extractErrorMessage(runsQ.error)} />}

      {/* Run History + Selected Run Results */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Run History */}
        <div className="pg-card lg:col-span-4 overflow-hidden">
          <div className="px-4 py-3 border-b border-[#222836] bg-[#0D1016]">
            <h2 className="text-xs font-semibold text-slate-200 uppercase tracking-wider">Execution History</h2>
          </div>
          <div className="divide-y divide-[#1D2330] max-h-[560px] overflow-y-auto">
            {runsQ.isLoading ? (
              <TableSkeleton rows={5} />
            ) : (runsQ.data || []).length === 0 ? (
              <EmptyState title="No runs yet" description="Trigger any test suite above." />
            ) : (
              (runsQ.data || []).map((run) => (
                <button
                  key={run.run_id}
                  onClick={() => setSelectedRunId(run.run_id)}
                  className={`w-full text-left px-4 py-3 hover:bg-[#161C27] transition-colors ${
                    activeRunId === run.run_id ? 'bg-[#171E2C] border-l-2 border-emerald-500' : ''
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs font-medium text-slate-200 flex items-center gap-1.5">
                      {run.run_id}
                      <SeededBadge isSeeded={run.is_seeded} />
                    </span>
                    <StatusBadge value={run.execution_status} />
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-slate-400 mt-1">
                    <span className="font-mono uppercase">{run.suite_name}</span>
                    <span className="font-mono">
                      <span className="text-emerald-400">{run.passed}P</span> /{' '}
                      <span className="text-red-400">{run.failed}F</span> • {run.duration.toFixed(2)}s
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-500 mt-1">{formatDateTime(run.started_at)}</p>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Selected Run Detail */}
        <div className="pg-card lg:col-span-8 overflow-hidden flex flex-col">
          {!activeRun ? (
            <EmptyState title="Select a test execution" description="Click a run on the left or run a new Pytest suite." />
          ) : (
            <>
              <div className="p-4 border-b border-[#222836] bg-[#0D1016] flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-semibold text-slate-100">{activeRun.run_id}</span>
                    <StatusBadge value={activeRun.execution_status} />
                    <SeededBadge isSeeded={activeRun.is_seeded} />
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Suite: <strong className="font-mono uppercase text-slate-200">{activeRun.suite_name}</strong> •
                    Started {formatDateTime(activeRun.started_at)}
                  </p>
                </div>

                {activeRun.report_path && (
                  <a
                    href={payguardApi.getHtmlReportUrl(activeRun.run_id)}
                    target="_blank"
                    rel="noreferrer"
                    className="pg-btn-secondary text-xs"
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                    Open HTML Report
                  </a>
                )}
              </div>

              {/* Run KPI Bar */}
              <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 p-4 border-b border-[#222836] bg-[#11141B] text-center">
                <div className="p-2 rounded bg-[#0D1016]">
                  <p className="text-[10px] text-slate-500 uppercase">Total</p>
                  <p className="font-mono text-sm font-semibold text-slate-100">{activeRun.total_tests}</p>
                </div>
                <div className="p-2 rounded bg-[#0D1016]">
                  <p className="text-[10px] text-slate-500 uppercase">Passed</p>
                  <p className="font-mono text-sm font-semibold text-emerald-400">{activeRun.passed}</p>
                </div>
                <div className="p-2 rounded bg-[#0D1016]">
                  <p className="text-[10px] text-slate-500 uppercase">Failed</p>
                  <p className="font-mono text-sm font-semibold text-red-400">{activeRun.failed}</p>
                </div>
                <div className="p-2 rounded bg-[#0D1016]">
                  <p className="text-[10px] text-slate-500 uppercase">Skipped</p>
                  <p className="font-mono text-sm font-semibold text-slate-400">{activeRun.skipped}</p>
                </div>
                <div className="p-2 rounded bg-[#0D1016]">
                  <p className="text-[10px] text-slate-500 uppercase">Pass Rate</p>
                  <p className="font-mono text-sm font-semibold text-emerald-400">{activeRun.pass_rate}%</p>
                </div>
                <div className="p-2 rounded bg-[#0D1016]">
                  <p className="text-[10px] text-slate-500 uppercase">Code Cov</p>
                  <p className="font-mono text-sm font-semibold text-sky-400">
                    {activeRun.code_coverage !== null && activeRun.code_coverage !== undefined
                      ? `${activeRun.code_coverage}%`
                      : '—'}
                  </p>
                </div>
              </div>

              {/* Individual Test Case Results */}
              <div className="overflow-x-auto flex-1">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#0D1016] text-slate-400 border-b border-[#222836]">
                    <tr>
                      <th className="px-4 py-2 font-medium">Test Case</th>
                      <th className="px-4 py-2 font-medium">Status</th>
                      <th className="px-4 py-2 font-medium">Duration</th>
                      <th className="px-4 py-2 font-medium text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1D2330]">
                    {(activeRun.results || []).map((tc) => (
                      <tr key={tc.id} className="hover:bg-[#161C27]">
                        <td className="px-4 py-2.5">
                          <p className="font-mono text-slate-200">{tc.test_name}</p>
                          {tc.failure_message && (
                            <p className="text-[11px] font-mono text-red-300/90 mt-1 bg-red-500/10 border border-red-500/20 rounded p-2 whitespace-pre-wrap">
                              {tc.failure_message}
                            </p>
                          )}
                        </td>
                        <td className="px-4 py-2.5 whitespace-nowrap">
                          <StatusBadge value={tc.test_status} />
                        </td>
                        <td className="px-4 py-2.5 font-mono text-slate-400 whitespace-nowrap">
                          {tc.duration.toFixed(3)}s
                        </td>
                        <td className="px-4 py-2.5 text-right whitespace-nowrap">
                          {tc.test_status === 'FAILED' && (
                            <button
                              onClick={() => handleCreateBugFromFailure(tc.test_name, tc.failure_message)}
                              className="inline-flex items-center gap-1 px-2 py-1 rounded bg-red-500/15 hover:bg-red-500/25 border border-red-500/30 text-red-300 text-[11px] font-medium"
                            >
                              <Bug className="h-3 w-3" />
                              CREATE BUG REPORT
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

