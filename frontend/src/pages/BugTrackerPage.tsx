import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bug as BugIcon, Plus, Search, Trash2, X } from 'lucide-react';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { EmptyState, ErrorBanner, TableSkeleton } from '../components/FeedbackStates';
import { SeededBadge, StatusBadge } from '../components/StatusBadge';
import { useToast } from '../components/ToastProvider';
import { extractErrorMessage, payguardApi } from '../services/api';
import type { Bug } from '../types';
import { formatDateTime } from '../utils/format';

const SEVERITIES: Bug['severity'][] = ['Critical', 'High', 'Medium', 'Low'];
const PRIORITIES: Bug['priority'][] = ['P0', 'P1', 'P2', 'P3'];
const STATUSES: Bug['status'][] = ['OPEN', 'IN_PROGRESS', 'FIXED', 'VERIFIED', 'CLOSED'];

export const BugTrackerPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const [search, setSearch] = useState('');
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedBug, setSelectedBug] = useState<Bug | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Bug | null>(null);

  // Create form state
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [severity, setSeverity] = useState<Bug['severity']>('High');
  const [priority, setPriority] = useState<Bug['priority']>('P1');
  const [moduleName, setModuleName] = useState('Payment Simulator');
  const [reproSteps, setReproSteps] = useState('');
  const [expectedResult, setExpectedResult] = useState('');
  const [actualResult, setActualResult] = useState('');
  const [transactionId, setTransactionId] = useState('');
  const [associatedTestCase, setAssociatedTestCase] = useState('');

  // Auto-open pre-populated modal when navigated from a failed test case
  useEffect(() => {
    const prefillTitle = searchParams.get('prefillTitle');
    if (prefillTitle) {
      setTitle(prefillTitle);
      setAssociatedTestCase(searchParams.get('prefillTest') || '');
      setActualResult(searchParams.get('prefillActual') || '');
      setModuleName(searchParams.get('prefillModule') || 'Automated Test Suites');
      setDescription(`Defect logged directly from automated test failure: ${searchParams.get('prefillTest') || ''}`);
      setExpectedResult('Automated test assertion should pass without regression.');
      setShowCreateModal(true);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const bugsQ = useQuery({
    queryKey: ['bugs', search, severityFilter, statusFilter],
    queryFn: () =>
      payguardApi.listBugs({
        search: search.trim() || undefined,
        severity: severityFilter !== 'ALL' ? severityFilter : undefined,
        status: statusFilter !== 'ALL' ? statusFilter : undefined,
      }),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      payguardApi.createBug({
        title,
        description,
        severity,
        priority,
        module: moduleName,
        reproduction_steps: reproSteps || undefined,
        expected_result: expectedResult || undefined,
        actual_result: actualResult || undefined,
        environment: 'SANDBOX',
        transaction_id: transactionId.trim() || undefined,
        associated_test_case: associatedTestCase.trim() || undefined,
      }),
    onSuccess: (bug) => {
      addToast('success', 'Bug Created', `${bug.bug_id}: ${bug.title}`);
      setShowCreateModal(false);
      setTitle('');
      setDescription('');
      setReproSteps('');
      setExpectedResult('');
      setActualResult('');
      setTransactionId('');
      setAssociatedTestCase('');
      queryClient.invalidateQueries({ queryKey: ['bugs'] });
      queryClient.invalidateQueries({ queryKey: ['reports'] });
    },
    onError: (err) => addToast('error', 'Failed to Create Bug', extractErrorMessage(err)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ bugId, patch }: { bugId: string; patch: Partial<Bug> }) => payguardApi.updateBug(bugId, patch),
    onSuccess: (updated) => {
      addToast('success', 'Defect Updated', `${updated.bug_id} is now ${updated.status}.`);
      setSelectedBug(updated);
      queryClient.invalidateQueries({ queryKey: ['bugs'] });
      queryClient.invalidateQueries({ queryKey: ['reports'] });
    },
    onError: (err) => addToast('error', 'Update Failed', extractErrorMessage(err)),
  });

  const deleteMutation = useMutation({
    mutationFn: (bugId: string) => payguardApi.deleteBug(bugId),
    onSuccess: () => {
      addToast('info', 'Bug Deleted', `${deleteTarget?.bug_id} removed from tracker.`);
      setDeleteTarget(null);
      setSelectedBug(null);
      queryClient.invalidateQueries({ queryKey: ['bugs'] });
      queryClient.invalidateQueries({ queryKey: ['reports'] });
    },
    onError: (err) => addToast('error', 'Delete Failed', extractErrorMessage(err)),
  });

  const bugs = bugsQ.data || [];

  return (
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-100">Bug Tracker</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Track payment defects, link failed Pytest cases and transaction IDs, and verify fixes across release cycles.
          </p>
        </div>
        <button onClick={() => setShowCreateModal(true)} className="pg-btn-primary text-xs self-start">
          <Plus className="h-3.5 w-3.5" />
          New Bug Report
        </button>
      </div>

      {/* Filters */}
      <div className="pg-card p-3.5 grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="relative">
          <Search className="h-3.5 w-3.5 text-slate-500 absolute left-3 top-2.5" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search Bug ID, title, or test case..."
            className="pg-input pl-8 text-xs"
          />
        </div>
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="pg-select text-xs"
          aria-label="Filter by severity"
        >
          <option value="ALL">All Severities</option>
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="pg-select text-xs"
          aria-label="Filter by bug status"
        >
          <option value="ALL">All Statuses</option>
          {STATUSES.map((st) => (
            <option key={st} value={st}>
              {st}
            </option>
          ))}
        </select>
      </div>

      {bugsQ.isError && <ErrorBanner message={extractErrorMessage(bugsQ.error)} />}

      {/* Bug Table */}
      <div className="pg-card overflow-hidden">
        {bugsQ.isLoading ? (
          <TableSkeleton rows={5} />
        ) : bugs.length === 0 ? (
          <EmptyState title="No defects found" description="Create a new defect report or adjust your search filters." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#0D1016] text-slate-400 border-b border-[#222836]">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Bug ID</th>
                  <th className="px-4 py-2.5 font-medium">Title</th>
                  <th className="px-4 py-2.5 font-medium">Module</th>
                  <th className="px-4 py-2.5 font-medium">Severity</th>
                  <th className="px-4 py-2.5 font-medium">Priority</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">Linked TXN / Test</th>
                  <th className="px-4 py-2.5 font-medium">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1D2330]">
                {bugs.map((bug) => (
                  <tr
                    key={bug.bug_id}
                    onClick={() => setSelectedBug(bug)}
                    className="hover:bg-[#161C27] cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-2.5 font-mono text-slate-100 whitespace-nowrap">
                      <span className="inline-flex items-center gap-1.5">
                        {bug.bug_id}
                        <SeededBadge isSeeded={bug.is_seeded} />
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-slate-200 font-medium max-w-sm truncate">{bug.title}</td>
                    <td className="px-4 py-2.5 text-slate-400 whitespace-nowrap">{bug.module}</td>
                    <td className="px-4 py-2.5">
                      <StatusBadge value={bug.severity} />
                    </td>
                    <td className="px-4 py-2.5 font-mono text-slate-300">{bug.priority}</td>
                    <td className="px-4 py-2.5">
                      <StatusBadge value={bug.status} />
                    </td>
                    <td className="px-4 py-2.5 font-mono text-[11px] text-slate-400 max-w-[160px] truncate">
                      {bug.transaction_id || bug.associated_test_case || '—'}
                    </td>
                    <td className="px-4 py-2.5 text-slate-400 whitespace-nowrap">{formatDateTime(bug.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create Bug Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="dialog">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              createMutation.mutate();
            }}
            className="w-full max-w-xl rounded-lg bg-[#12161F] border border-[#2A3244] shadow-2xl overflow-hidden"
          >
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-[#222836]">
              <h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
                <BugIcon className="h-4 w-4 text-red-400" />
                Log Defect Report
              </h3>
              <button type="button" onClick={() => setShowCreateModal(false)} className="text-slate-400">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="p-5 space-y-3 max-h-[75vh] overflow-y-auto text-xs">
              <div>
                <label className="block text-slate-300 mb-1">Title *</label>
                <input
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="pg-input text-xs"
                  placeholder="Concise summary of the defect"
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Description *</label>
                <textarea
                  required
                  rows={2}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="pg-input text-xs"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-slate-300 mb-1">Severity</label>
                  <select value={severity} onChange={(e) => setSeverity(e.target.value as any)} className="pg-select w-full text-xs">
                    {SEVERITIES.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-slate-300 mb-1">Priority</label>
                  <select value={priority} onChange={(e) => setPriority(e.target.value as any)} className="pg-select w-full text-xs">
                    {PRIORITIES.map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-slate-300 mb-1">Module</label>
                  <input value={moduleName} onChange={(e) => setModuleName(e.target.value)} className="pg-input text-xs" />
                </div>
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Steps to Reproduce</label>
                <textarea rows={2} value={reproSteps} onChange={(e) => setReproSteps(e.target.value)} className="pg-input text-xs" />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 mb-1">Expected Result</label>
                  <textarea rows={2} value={expectedResult} onChange={(e) => setExpectedResult(e.target.value)} className="pg-input text-xs" />
                </div>
                <div>
                  <label className="block text-slate-300 mb-1">Actual Result</label>
                  <textarea rows={2} value={actualResult} onChange={(e) => setActualResult(e.target.value)} className="pg-input text-xs" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 mb-1">Associated Transaction ID (optional)</label>
                  <input
                    value={transactionId}
                    onChange={(e) => setTransactionId(e.target.value)}
                    placeholder="TXN-..."
                    className="pg-input font-mono text-xs"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 mb-1">Associated Test Case (optional)</label>
                  <input
                    value={associatedTestCase}
                    onChange={(e) => setAssociatedTestCase(e.target.value)}
                    placeholder="test_..."
                    className="pg-input font-mono text-xs"
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 px-5 py-3 bg-[#0D1016] border-t border-[#222836]">
              <button type="button" onClick={() => setShowCreateModal(false)} className="pg-btn-secondary text-xs">
                Cancel
              </button>
              <button type="submit" disabled={createMutation.isPending} className="pg-btn-primary text-xs">
                {createMutation.isPending ? 'Saving...' : 'Create Bug'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Bug Detail & Workflow Update Modal */}
      {selectedBug && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="dialog">
          <div className="w-full max-w-2xl rounded-lg bg-[#12161F] border border-[#2A3244] shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-[#222836]">
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm font-semibold text-slate-100">{selectedBug.bug_id}</span>
                <StatusBadge value={selectedBug.severity} />
                <StatusBadge value={selectedBug.status} />
              </div>
              <button onClick={() => setSelectedBug(null)} className="text-slate-400 hover:text-slate-200">
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="p-5 space-y-4 max-h-[75vh] overflow-y-auto text-xs">
              <div>
                <h3 className="text-base font-semibold text-slate-100">{selectedBug.title}</h3>
                <p className="text-slate-300 mt-1.5 leading-relaxed">{selectedBug.description}</p>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                <div className="p-2.5 rounded bg-[#0D1016] border border-[#222836]">
                  <p className="text-slate-500">Module</p>
                  <p className="text-slate-200 font-medium mt-0.5">{selectedBug.module}</p>
                </div>
                <div className="p-2.5 rounded bg-[#0D1016] border border-[#222836]">
                  <p className="text-slate-500">Environment</p>
                  <p className="font-mono text-slate-200 mt-0.5">{selectedBug.environment}</p>
                </div>
                <div className="p-2.5 rounded bg-[#0D1016] border border-[#222836]">
                  <p className="text-slate-500">Transaction ID</p>
                  <p className="font-mono text-slate-200 mt-0.5 truncate">{selectedBug.transaction_id || '—'}</p>
                </div>
                <div className="p-2.5 rounded bg-[#0D1016] border border-[#222836]">
                  <p className="text-slate-500">Test Case</p>
                  <p className="font-mono text-slate-200 mt-0.5 truncate">{selectedBug.associated_test_case || '—'}</p>
                </div>
              </div>

              {selectedBug.reproduction_steps && (
                <div>
                  <p className="font-medium text-slate-300 mb-1">Steps to Reproduce</p>
                  <pre className="p-2.5 rounded bg-[#0D1016] border border-[#222836] text-slate-300 whitespace-pre-wrap font-sans">
                    {selectedBug.reproduction_steps}
                  </pre>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="p-2.5 rounded bg-[#0D1016] border border-[#222836]">
                  <p className="font-medium text-emerald-400 mb-1">Expected Result</p>
                  <p className="text-slate-300">{selectedBug.expected_result || '—'}</p>
                </div>
                <div className="p-2.5 rounded bg-[#0D1016] border border-[#222836]">
                  <p className="font-medium text-red-400 mb-1">Actual Result</p>
                  <p className="text-slate-300">{selectedBug.actual_result || '—'}</p>
                </div>
              </div>

              {/* Status Workflow Transition */}
              <div className="pt-2 border-t border-[#222836] flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-slate-400">Update Status:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {STATUSES.map((st) => (
                      <button
                        key={st}
                        type="button"
                        disabled={updateMutation.isPending || selectedBug.status === st}
                        onClick={() => updateMutation.mutate({ bugId: selectedBug.bug_id, patch: { status: st } })}
                        className={`px-2 py-1 rounded text-[11px] font-mono border transition-colors ${
                          selectedBug.status === st
                            ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300'
                            : 'bg-[#171C26] border-[#2A3244] text-slate-300 hover:bg-[#222A3A]'
                        }`}
                      >
                        {st}
                      </button>
                    ))}
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => setDeleteTarget(selectedBug)}
                  className="inline-flex items-center gap-1 text-red-400 hover:text-red-300 text-xs"
                >
                  <Trash2 className="h-3.5 w-3.5" /> Delete
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Delete Defect Report"
        description={`Permanently delete ${deleteTarget?.bug_id} (${deleteTarget?.title})?`}
        confirmLabel="Delete Bug"
        loading={deleteMutation.isPending}
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.bug_id)}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
};

