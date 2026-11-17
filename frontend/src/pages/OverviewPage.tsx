import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  CheckCircle2,
  Clock,
  FlaskConical,
  Gauge,
  RefreshCw,
  XCircle,
} from 'lucide-react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { CardSkeleton, EmptyState, ErrorBanner } from '../components/FeedbackStates';
import { SeededBadge, StatusBadge } from '../components/StatusBadge';
import { TransactionDetailDrawer } from '../components/TransactionDetailDrawer';
import { extractErrorMessage, payguardApi } from '../services/api';
import { formatCurrency, formatDateTime, formatDurationMs } from '../utils/format';

type RangeKey = '24h' | '7d' | '30d' | 'custom';

export const OverviewPage: React.FC = () => {
  const [range, setRange] = useState<RangeKey>('30d');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [activityTab, setActivityTab] = useState<'transactions' | 'tests' | 'failures' | 'webhooks'>('transactions');
  const [selectedTxId, setSelectedTxId] = useState<string | null>(null);

  const queryParams = {
    range,
    start_date: range === 'custom' && startDate ? startDate : undefined,
    end_date: range === 'custom' && endDate ? endDate : undefined,
  };

  const metricsQ = useQuery({
    queryKey: ['dashboard', 'metrics', queryParams],
    queryFn: () => payguardApi.getDashboardMetrics(queryParams),
  });
  const txQ = useQuery({
    queryKey: ['dashboard', 'transactions', queryParams],
    queryFn: () => payguardApi.getDashboardTransactions(queryParams),
  });
  const testQ = useQuery({
    queryKey: ['dashboard', 'test-activity', queryParams],
    queryFn: () => payguardApi.getDashboardTestActivity(queryParams),
  });

  const m = metricsQ.data;
  const volumeSeries = txQ.data?.volume_series || [];
  const testTrends = testQ.data?.test_trends || [];
  const distribution = (m?.distribution || []).filter((d: { value: number }) => d.value > 0);

  const refetchAll = () => {
    metricsQ.refetch();
    txQ.refetch();
    testQ.refetch();
  };

  return (
    <div className="space-y-6">
      {/* Header & Date Filter Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-100">Overview</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time payment reliability & automated test execution metrics derived from persisted database records.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-md bg-[#11141B] border border-[#222836] p-0.5">
            {(
              [
                ['24h', 'Last 24h'],
                ['7d', 'Last 7d'],
                ['30d', 'Last 30d'],
                ['custom', 'Custom'],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setRange(key)}
                className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
                  range === key ? 'bg-[#1F2736] text-emerald-400' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {range === 'custom' && (
            <div className="flex items-center gap-1.5">
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="pg-input py-1 text-xs w-36"
                aria-label="Start date"
              />
              <span className="text-xs text-slate-500">to</span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="pg-input py-1 text-xs w-36"
                aria-label="End date"
              />
            </div>
          )}

          <button onClick={refetchAll} className="pg-btn-secondary py-1.5 px-2.5 text-xs">
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {metricsQ.isError && <ErrorBanner message={extractErrorMessage(metricsQ.error)} onRetry={refetchAll} />}

      {/* KPI Metrics Row */}
      {metricsQ.isLoading || !m ? (
        <CardSkeleton count={4} />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3.5">
          <div className="pg-card p-4">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Total Transactions</span>
              <Activity className="h-3.5 w-3.5 text-slate-500" />
            </div>
            <p className="text-2xl font-semibold font-mono text-slate-100 mt-2">{m.total_transactions}</p>
            <p className="text-[11px] text-slate-500 mt-1">
              {m.successful_transactions} ok • {m.failed_transactions} fail • {m.pending_transactions} pending
            </p>
          </div>

          <div className="pg-card p-4">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Payment Success Rate</span>
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
            </div>
            <p className="text-2xl font-semibold font-mono text-emerald-400 mt-2">{m.success_rate}%</p>
            <div className="w-full bg-[#1B212E] h-1.5 rounded-full mt-2 overflow-hidden">
              <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${m.success_rate}%` }} />
            </div>
          </div>

          <div className="pg-card p-4">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Failure Rate</span>
              <XCircle className="h-3.5 w-3.5 text-red-400" />
            </div>
            <p className="text-2xl font-semibold font-mono text-red-400 mt-2">{m.failure_rate}%</p>
            <p className="text-[11px] text-slate-500 mt-1">{m.failed_transactions} declined / errored</p>
          </div>

          <div className="pg-card p-4">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Automated Test Runs</span>
              <FlaskConical className="h-3.5 w-3.5 text-sky-400" />
            </div>
            <p className="text-2xl font-semibold font-mono text-slate-100 mt-2">{m.total_test_executions}</p>
            <p className="text-[11px] text-slate-500 mt-1">
              <span className="text-emerald-400">{m.passed_test_cases} passed</span> •{' '}
              <span className="text-red-400">{m.failed_test_cases} failed</span>
            </p>
          </div>

          <div className="pg-card p-4 col-span-2 md:col-span-1">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Avg Processing Time</span>
              <Gauge className="h-3.5 w-3.5 text-amber-400" />
            </div>
            <p className="text-2xl font-semibold font-mono text-slate-100 mt-2">
              {formatDurationMs(m.avg_processing_time_ms)}
            </p>
            <p className="text-[11px] text-slate-500 mt-1">Simulated gateway latency</p>
          </div>
        </div>
      )}

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* A. Transaction Volume Chart */}
        <div className="pg-card p-4 lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-200">Transaction Volume</h2>
              <p className="text-xs text-slate-500">Daily successful, failed, and pending payment outcomes</p>
            </div>
          </div>
          {volumeSeries.length === 0 ? (
            <EmptyState
              title="No transactions in selected window"
              description="Simulate a payment in the Payment Simulator or widen the date filter."
            />
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={volumeSeries} margin={{ top: 5, right: 12, left: -16, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1E2533" />
                  <XAxis dataKey="date" tick={{ fill: '#64748B', fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fill: '#64748B', fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#12161F',
                      border: '1px solid #2A3244',
                      borderRadius: 6,
                      fontSize: 12,
                    }}
                  />
                  <Area type="monotone" dataKey="success" name="Success" stroke="#10B981" fill="#10B981" fillOpacity={0.18} />
                  <Area type="monotone" dataKey="failed" name="Failed" stroke="#EF4444" fill="#EF4444" fillOpacity={0.15} />
                  <Area type="monotone" dataKey="pending" name="Pending" stroke="#F59E0B" fill="#F59E0B" fillOpacity={0.12} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* C. Transaction Distribution */}
        <div className="pg-card p-4">
          <h2 className="text-sm font-semibold text-slate-200">Transaction Distribution</h2>
          <p className="text-xs text-slate-500 mb-3">Breakdown by persisted payment state</p>
          {distribution.length === 0 ? (
            <EmptyState title="No distribution data" description="No transactions found in the selected range." />
          ) : (
            <>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={distribution}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={48}
                      outerRadius={76}
                      paddingAngle={2}
                    >
                      {distribution.map((entry: { name: string; color: string }) => (
                        <Cell key={entry.name} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#12161F',
                        border: '1px solid #2A3244',
                        borderRadius: 6,
                        fontSize: 12,
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="grid grid-cols-2 gap-2 mt-2 text-xs">
                {distribution.map((d: { name: string; value: number; color: string }) => (
                  <div key={d.name} className="flex items-center justify-between px-2 py-1 rounded bg-[#0D1016]">
                    <span className="flex items-center gap-1.5 text-slate-300">
                      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: d.color }} />
                      {d.name}
                    </span>
                    <span className="font-mono text-slate-200">{d.value}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* D. Test Execution Trends */}
      <div className="pg-card p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-sm font-semibold text-slate-200">Test Execution Trends</h2>
            <p className="text-xs text-slate-500">Passed vs failed test cases across recorded Pytest runs</p>
          </div>
        </div>
        {testTrends.length === 0 ? (
          <EmptyState
            title="No test executions recorded"
            description="Run an automated Pytest suite from the Test Suites module."
          />
        ) : (
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={testTrends} margin={{ top: 5, right: 12, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E2533" />
                <XAxis dataKey="date" tick={{ fill: '#64748B', fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fill: '#64748B', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#12161F',
                    border: '1px solid #2A3244',
                    borderRadius: 6,
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="passed" name="Passed" stackId="a" fill="#10B981" radius={[0, 0, 0, 0]} />
                <Bar dataKey="failed" name="Failed" stackId="a" fill="#EF4444" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* E. Recent Activity Tabs */}
      <div className="pg-card overflow-hidden">
        <div className="px-4 pt-3 border-b border-[#222836] flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-slate-200 pb-3">Recent Activity</h2>
          <div className="flex gap-4 text-xs">
            {(
              [
                ['transactions', 'Recent Transactions'],
                ['tests', 'Test Runs'],
                ['failures', 'Recent Failures'],
                ['webhooks', 'Webhook Events'],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setActivityTab(key)}
                className={`pb-3 border-b-2 font-medium transition-colors ${
                  activityTab === key
                    ? 'border-emerald-500 text-emerald-400'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          {activityTab === 'transactions' && (
            <table className="w-full text-left text-xs">
              <thead className="bg-[#0D1016] text-slate-400 border-b border-[#222836]">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Transaction ID</th>
                  <th className="px-4 py-2.5 font-medium">Order ID</th>
                  <th className="px-4 py-2.5 font-medium">Amount</th>
                  <th className="px-4 py-2.5 font-medium">Method</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">Latency</th>
                  <th className="px-4 py-2.5 font-medium">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1D2330]">
                {(txQ.data?.recent_transactions || []).map((t: any) => (
                  <tr
                    key={t.transaction_id}
                    onClick={() => setSelectedTxId(t.transaction_id)}
                    className="hover:bg-[#161C27] cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-2.5 font-mono text-slate-200 flex items-center gap-1.5">
                      {t.transaction_id}
                      <SeededBadge isSeeded={t.is_seeded} />
                    </td>
                    <td className="px-4 py-2.5 font-mono text-slate-400">{t.order_id}</td>
                    <td className="px-4 py-2.5 font-mono text-slate-200">{formatCurrency(t.amount, t.currency)}</td>
                    <td className="px-4 py-2.5 text-slate-300">{t.payment_method}</td>
                    <td className="px-4 py-2.5">
                      <StatusBadge value={t.status} />
                    </td>
                    <td className="px-4 py-2.5 font-mono text-slate-400">{formatDurationMs(t.processing_duration_ms)}</td>
                    <td className="px-4 py-2.5 text-slate-400">{formatDateTime(t.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {activityTab === 'tests' && (
            <table className="w-full text-left text-xs">
              <thead className="bg-[#0D1016] text-slate-400 border-b border-[#222836]">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Run ID</th>
                  <th className="px-4 py-2.5 font-medium">Suite</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">Passed / Failed</th>
                  <th className="px-4 py-2.5 font-medium">Duration</th>
                  <th className="px-4 py-2.5 font-medium">Started</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1D2330]">
                {(testQ.data?.recent_test_runs || []).map((r: any) => (
                  <tr key={r.run_id} className="hover:bg-[#161C27]">
                    <td className="px-4 py-2.5 font-mono text-slate-200 flex items-center gap-1.5">
                      {r.run_id}
                      <SeededBadge isSeeded={r.is_seeded} />
                    </td>
                    <td className="px-4 py-2.5 font-mono uppercase text-slate-300">{r.suite_name}</td>
                    <td className="px-4 py-2.5">
                      <StatusBadge value={r.execution_status} />
                    </td>
                    <td className="px-4 py-2.5 font-mono">
                      <span className="text-emerald-400">{r.passed}</span> /{' '}
                      <span className="text-red-400">{r.failed}</span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-slate-400">{r.duration}s</td>
                    <td className="px-4 py-2.5 text-slate-400">{formatDateTime(r.started_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {activityTab === 'failures' && (
            <table className="w-full text-left text-xs">
              <thead className="bg-[#0D1016] text-slate-400 border-b border-[#222836]">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Transaction ID</th>
                  <th className="px-4 py-2.5 font-medium">Amount</th>
                  <th className="px-4 py-2.5 font-medium">Response Code</th>
                  <th className="px-4 py-2.5 font-medium">Failure Reason</th>
                  <th className="px-4 py-2.5 font-medium">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1D2330]">
                {(txQ.data?.recent_failures || []).map((f: any) => (
                  <tr
                    key={f.transaction_id}
                    onClick={() => setSelectedTxId(f.transaction_id)}
                    className="hover:bg-[#161C27] cursor-pointer"
                  >
                    <td className="px-4 py-2.5 font-mono text-red-400">{f.transaction_id}</td>
                    <td className="px-4 py-2.5 font-mono text-slate-200">{formatCurrency(f.amount, f.currency)}</td>
                    <td className="px-4 py-2.5 font-mono text-slate-300">{f.response_code}</td>
                    <td className="px-4 py-2.5 text-slate-400 max-w-md truncate">{f.failure_reason}</td>
                    <td className="px-4 py-2.5 text-slate-400">{formatDateTime(f.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {activityTab === 'webhooks' && (
            <table className="w-full text-left text-xs">
              <thead className="bg-[#0D1016] text-slate-400 border-b border-[#222836]">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Event ID</th>
                  <th className="px-4 py-2.5 font-medium">Type</th>
                  <th className="px-4 py-2.5 font-medium">Transaction</th>
                  <th className="px-4 py-2.5 font-medium">Delivery Status</th>
                  <th className="px-4 py-2.5 font-medium">Attempts</th>
                  <th className="px-4 py-2.5 font-medium">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1D2330]">
                {(testQ.data?.recent_webhooks || []).map((w: any) => (
                  <tr key={w.event_id} className="hover:bg-[#161C27]">
                    <td className="px-4 py-2.5 font-mono text-slate-200 flex items-center gap-1.5">
                      {w.event_id}
                      <SeededBadge isSeeded={w.is_seeded} />
                    </td>
                    <td className="px-4 py-2.5 font-mono text-slate-300">{w.event_type}</td>
                    <td className="px-4 py-2.5 font-mono text-slate-400">{w.transaction_id || '—'}</td>
                    <td className="px-4 py-2.5">
                      <StatusBadge value={w.delivery_status} />
                    </td>
                    <td className="px-4 py-2.5 font-mono text-slate-300">{w.attempt_count}</td>
                    <td className="px-4 py-2.5 text-slate-400">{formatDateTime(w.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <TransactionDetailDrawer transactionId={selectedTxId} onClose={() => setSelectedTxId(null)} />
    </div>
  );
};

