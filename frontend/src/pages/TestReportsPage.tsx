import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download, ExternalLink, Info, RefreshCw } from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { CardSkeleton, EmptyState, ErrorBanner } from '../components/FeedbackStates';
import { SeededBadge, StatusBadge } from '../components/StatusBadge';
import { extractErrorMessage, payguardApi } from '../services/api';
import { formatDateTime } from '../utils/format';

export const TestReportsPage: React.FC = () => {
  const [suiteFilter, setSuiteFilter] = useState<string>('ALL');
  const [includeSeeded, setIncludeSeeded] = useState<boolean>(true);

  const reportQ = useQuery({
    queryKey: ['reports', 'metrics', suiteFilter, includeSeeded],
    queryFn: () =>
      payguardApi.getReportMetrics({
        suite_name: suiteFilter !== 'ALL' ? suiteFilter : undefined,
        include_seeded: includeSeeded,
      }),
  });

  const runsQ = useQuery({
    queryKey: ['test-runs', suiteFilter],
    queryFn: () => payguardApi.listTestRuns(suiteFilter !== 'ALL' ? suiteFilter : undefined),
  });

  const summary = reportQ.data?.summary;
  const defs = reportQ.data?.metric_definitions;
  const defectDist = reportQ.data?.defect_distribution || [];
  const regTrends = reportQ.data?.regression_trends || [];
  const failureAnalysis = reportQ.data?.failure_analysis;

  return (
    <div className="space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-100">Test Reports & Quality Metrics</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Quality engineering telemetry clearly distinguishing automated pass rate, code coverage, test case coverage, and defect density.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a href={payguardApi.getTransactionsCsvUrl()} className="pg-btn-secondary text-xs">
            <Download className="h-3.5 w-3.5" />
            Transactions CSV
          </a>
          <a href={payguardApi.getTestsCsvUrl()} className="pg-btn-secondary text-xs">
            <Download className="h-3.5 w-3.5" />
            Test Runs CSV
          </a>
          <button
            onClick={() => {
              reportQ.refetch();
              runsQ.refetch();
            }}
            className="pg-btn-secondary text-xs"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {/* Report Filters */}
      <div className="pg-card p-3.5 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <label htmlFor="report-suite-filter" className="text-slate-400">
              Test Suite:
            </label>
            <select
              id="report-suite-filter"
              value={suiteFilter}
              onChange={(e) => setSuiteFilter(e.target.value)}
              className="pg-select py-1 text-xs"
            >
              <option value="ALL">All Suites</option>
              <option value="all">all</option>
              <option value="smoke">smoke</option>
              <option value="regression">regression</option>
              <option value="edge_cases">edge_cases</option>
              <option value="api_contract">api_contract</option>
              <option value="database">database</option>
            </select>
          </div>
          <label className="inline-flex items-center gap-2 text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={includeSeeded}
              onChange={(e) => setIncludeSeeded(e.target.checked)}
              className="accent-emerald-500"
            />
            Include seeded demo baseline
          </label>
        </div>
        <span className="text-[11px] font-mono text-slate-500">
          {includeSeeded ? 'Showing Seeded + Live Runs' : 'Live Executions Only'}
        </span>
      </div>

      {reportQ.isError && <ErrorBanner message={extractErrorMessage(reportQ.error)} />}

      {/* 4 Distinct Quality Engineering Metrics */}
      {reportQ.isLoading || !summary ? (
        <CardSkeleton count={4} />
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
            <div className="pg-card p-4">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Automated Test Pass Rate</span>
                <span title={defs?.automated_test_pass_rate}>
                  <Info className="h-3.5 w-3.5 text-slate-500" />
                </span>
              </div>
              <p className="text-2xl font-semibold font-mono text-emerald-400 mt-2">
                {summary.automated_test_pass_rate}%
              </p>
              <p className="text-[11px] text-slate-500 mt-1">
                {summary.total_passed} passed / {summary.total_failed} failed ({summary.total_tests_executed} executed)
              </p>
            </div>

            <div className="pg-card p-4">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Code Coverage (pytest-cov)</span>
                <span title={defs?.code_coverage}>
                  <Info className="h-3.5 w-3.5 text-slate-500" />
                </span>
              </div>
              <p className="text-2xl font-semibold font-mono text-sky-400 mt-2">
                {summary.code_coverage_percent !== null ? `${summary.code_coverage_percent}%` : 'N/A'}
              </p>
              <p className="text-[11px] text-slate-500 mt-1">Backend statement coverage on latest measured run</p>
            </div>

            <div className="pg-card p-4">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Test Case Coverage</span>
                <span title={defs?.test_case_coverage}>
                  <Info className="h-3.5 w-3.5 text-slate-500" />
                </span>
              </div>
              <p className="text-2xl font-semibold font-mono text-indigo-300 mt-2">
                {summary.test_case_coverage_percent}%
              </p>
              <p className="text-[11px] text-slate-500 mt-1">
                {summary.distinct_tests_exercised} distinct tests / {summary.planned_test_catalog_size} planned scenarios
              </p>
            </div>

            <div className="pg-card p-4">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Defect Density</span>
                <span title={defs?.defect_density}>
                  <Info className="h-3.5 w-3.5 text-slate-500" />
                </span>
              </div>
              <p className="text-2xl font-semibold font-mono text-amber-400 mt-2">
                {summary.defect_density_per_100_tests}
              </p>
              <p className="text-[11px] text-slate-500 mt-1">
                defects / 100 test cases ({summary.open_defects} open of {summary.total_defects})
              </p>
            </div>
          </div>

          {/* Performance Metrics Bar */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
            <div className="pg-card p-3.5 flex items-center justify-between">
              <span className="text-xs text-slate-400">Automated Test Failure Rate</span>
              <span className="font-mono text-sm font-semibold text-red-400">{summary.automated_test_failure_rate}%</span>
            </div>
            <div className="pg-card p-3.5 flex items-center justify-between">
              <span className="text-xs text-slate-400">Avg API Simulated Latency</span>
              <span className="font-mono text-sm font-semibold text-slate-100">{summary.avg_api_response_time_ms} ms</span>
            </div>
            <div className="pg-card p-3.5 flex items-center justify-between">
              <span className="text-xs text-slate-400">Avg Suite Execution Time</span>
              <span className="font-mono text-sm font-semibold text-slate-100">{summary.avg_test_execution_time_sec} s</span>
            </div>
          </div>
        </>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="pg-card p-4">
          <h2 className="text-sm font-semibold text-slate-200">Regression Pass Rate Trend</h2>
          <p className="text-xs text-slate-500 mb-3">Pass percentage across sequential test executions</p>
          {regTrends.length === 0 ? (
            <EmptyState title="No trend data" description="Run tests to track regression stability over time." />
          ) : (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={regTrends} margin={{ top: 5, right: 16, left: -16, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1E2533" />
                  <XAxis dataKey="date" tick={{ fill: '#64748B', fontSize: 11 }} />
                  <YAxis domain={[0, 100]} tick={{ fill: '#64748B', fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#12161F',
                      border: '1px solid #2A3244',
                      borderRadius: 6,
                      fontSize: 12,
                    }}
                  />
                  <Line type="monotone" dataKey="pass_rate" name="Pass Rate %" stroke="#10B981" strokeWidth={2} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="pg-card p-4">
          <h2 className="text-sm font-semibold text-slate-200">Defect Distribution by Severity</h2>
          <p className="text-xs text-slate-500 mb-3">Logged defects grouped by severity level</p>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={defectDist} margin={{ top: 5, right: 16, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E2533" />
                <XAxis dataKey="severity" tick={{ fill: '#64748B', fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fill: '#64748B', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#12161F',
                    border: '1px solid #2A3244',
                    borderRadius: 6,
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="count" name="Defects" fill="#F59E0B" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Failure Analysis & HTML Execution History */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="pg-card p-4 space-y-3">
          <h2 className="text-sm font-semibold text-slate-200">Failure Analysis</h2>
          <div className="space-y-2 text-xs">
            <p className="text-[11px] uppercase tracking-wider text-slate-400">Top Transaction Failure Codes</p>
            {(failureAnalysis?.transaction_failure_breakdown || []).length === 0 ? (
              <p className="text-slate-500">No failed transactions recorded.</p>
            ) : (
              (failureAnalysis?.transaction_failure_breakdown || []).map((item: any) => (
                <div key={item.response_code} className="flex items-center justify-between p-2 rounded bg-[#0D1016]">
                  <span className="font-mono text-red-300">{item.response_code}</span>
                  <span className="font-mono text-slate-200">{item.count}</span>
                </div>
              ))
            )}

            <p className="text-[11px] uppercase tracking-wider text-slate-400 pt-2">Recurring Test Failures</p>
            {(failureAnalysis?.top_test_failures || []).length === 0 ? (
              <p className="text-emerald-400">Zero automated test failures detected.</p>
            ) : (
              (failureAnalysis?.top_test_failures || []).map((f: any) => (
                <div key={f.test_name} className="p-2 rounded bg-[#0D1016] border border-red-500/20">
                  <div className="flex justify-between font-mono">
                    <span className="text-red-300">{f.test_name}</span>
                    <span className="text-slate-400">{f.occurrences}x</span>
                  </div>
                  {f.latest_message && <p className="text-[11px] text-slate-400 mt-1 truncate">{f.latest_message}</p>}
                </div>
              ))
            )}
          </div>
        </div>

        <div className="pg-card overflow-hidden">
          <div className="px-4 py-3 border-b border-[#222836] bg-[#0D1016]">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
              HTML Test Execution Reports
            </h2>
          </div>
          <div className="divide-y divide-[#1D2330] max-h-80 overflow-y-auto">
            {(runsQ.data || []).map((run) => (
              <div key={run.run_id} className="px-4 py-2.5 flex items-center justify-between gap-2 text-xs">
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-slate-200">{run.run_id}</span>
                    <SeededBadge isSeeded={run.is_seeded} />
                    <StatusBadge value={run.execution_status} />
                  </div>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    {run.suite_name.toUpperCase()} • {run.passed}/{run.total_tests} passed • {formatDateTime(run.started_at)}
                  </p>
                </div>
                {run.report_path ? (
                  <a
                    href={payguardApi.getHtmlReportUrl(run.run_id)}
                    target="_blank"
                    rel="noreferrer"
                    className="pg-btn-secondary py-1 px-2.5 text-[11px] shrink-0"
                  >
                    <ExternalLink className="h-3 w-3" /> HTML
                  </a>
                ) : (
                  <span className="text-[11px] text-slate-500 font-mono">Seeded</span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

