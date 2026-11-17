import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowUpDown, ChevronLeft, ChevronRight, Eye, RefreshCw, Search } from 'lucide-react';
import { EmptyState, ErrorBanner, TableSkeleton } from '../components/FeedbackStates';
import { SeededBadge, StatusBadge } from '../components/StatusBadge';
import { TransactionDetailDrawer } from '../components/TransactionDetailDrawer';
import { extractErrorMessage, payguardApi } from '../services/api';
import { formatCurrency, formatDateTime, formatDurationMs } from '../utils/format';

export const TransactionsPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState(searchParams.get('search') || '');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [methodFilter, setMethodFilter] = useState('ALL');
  const [dateFrom, setDateFrom] = useState('');
  const [sortBy, setSortBy] = useState<'created_at' | 'amount'>('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [page, setPage] = useState(1);
  const [selectedTxId, setSelectedTxId] = useState<string | null>(null);

  useEffect(() => {
    const q = searchParams.get('search');
    if (q !== null) {
      setSearch(q);
      setPage(1);
    }
  }, [searchParams]);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['transactions', search, statusFilter, methodFilter, dateFrom, sortBy, sortOrder, page],
    queryFn: () =>
      payguardApi.listPayments({
        search: search.trim() || undefined,
        status: statusFilter !== 'ALL' ? statusFilter : undefined,
        payment_method: methodFilter !== 'ALL' ? methodFilter : undefined,
        date_from: dateFrom ? `${dateFrom}T00:00:00Z` : undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
        page,
        page_size: 12,
      }),
  });

  const toggleSort = (col: 'created_at' | 'amount') => {
    if (sortBy === col) {
      setSortOrder((o) => (o === 'desc' ? 'asc' : 'desc'));
    } else {
      setSortBy(col);
      setSortOrder('desc');
    }
    setPage(1);
  };

  const items = data?.items || [];
  const pagination = data?.pagination;

  return (
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-slate-100">Transactions</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Persisted payment transaction ledger with lifecycle inspection, refunds, and pending reconciliation.
          </p>
        </div>
        <button onClick={() => refetch()} className="pg-btn-secondary text-xs self-start">
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh Ledger
        </button>
      </div>

      {/* Filters Toolbar */}
      <div className="pg-card p-3.5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        <div className="relative lg:col-span-2">
          <Search className="h-3.5 w-3.5 text-slate-500 absolute left-3 top-2.5" />
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search Transaction ID, Order ID, or Idempotency Key..."
            className="pg-input pl-8 text-xs"
          />
        </div>

        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="pg-select text-xs"
          aria-label="Filter by status"
        >
          <option value="ALL">All Statuses</option>
          <option value="SUCCESS">SUCCESS</option>
          <option value="FAILED">FAILED</option>
          <option value="PENDING">PENDING</option>
          <option value="REFUNDED">REFUNDED</option>
          <option value="PROCESSING">PROCESSING</option>
          <option value="CREATED">CREATED</option>
        </select>

        <select
          value={methodFilter}
          onChange={(e) => {
            setMethodFilter(e.target.value);
            setPage(1);
          }}
          className="pg-select text-xs"
          aria-label="Filter by payment method"
        >
          <option value="ALL">All Methods</option>
          <option value="UPI">UPI</option>
          <option value="CARD">CARD</option>
          <option value="NET_BANKING">NET_BANKING</option>
          <option value="WALLET">WALLET</option>
        </select>

        <input
          type="date"
          value={dateFrom}
          onChange={(e) => {
            setDateFrom(e.target.value);
            setPage(1);
          }}
          className="pg-input text-xs"
          aria-label="Filter from date"
        />
      </div>

      {isError && <ErrorBanner message={extractErrorMessage(error)} onRetry={() => refetch()} />}

      {/* Table */}
      <div className="pg-card overflow-hidden">
        {isLoading ? (
          <TableSkeleton rows={8} />
        ) : items.length === 0 ? (
          <EmptyState
            title="No matching transactions"
            description="Adjust your filters or simulate a new payment in the Payment Simulator."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#0D1016] text-slate-400 border-b border-[#222836]">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Transaction ID</th>
                  <th className="px-4 py-2.5 font-medium">Order ID</th>
                  <th className="px-4 py-2.5 font-medium">
                    <button
                      onClick={() => toggleSort('amount')}
                      className="inline-flex items-center gap-1 hover:text-slate-200"
                    >
                      Amount <ArrowUpDown className="h-3 w-3" />
                    </button>
                  </th>
                  <th className="px-4 py-2.5 font-medium">Currency</th>
                  <th className="px-4 py-2.5 font-medium">Method</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">Idempotency Key</th>
                  <th className="px-4 py-2.5 font-medium">
                    <button
                      onClick={() => toggleSort('created_at')}
                      className="inline-flex items-center gap-1 hover:text-slate-200"
                    >
                      Created At <ArrowUpDown className="h-3 w-3" />
                    </button>
                  </th>
                  <th className="px-4 py-2.5 font-medium">Duration</th>
                  <th className="px-4 py-2.5 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1D2330]">
                {items.map((tx) => (
                  <tr
                    key={tx.transaction_id}
                    onClick={() => setSelectedTxId(tx.transaction_id)}
                    className="hover:bg-[#161C27] cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-2.5 font-mono text-slate-100 whitespace-nowrap">
                      <span className="inline-flex items-center gap-1.5">
                        {tx.transaction_id}
                        <SeededBadge isSeeded={tx.is_seeded} />
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-slate-300 whitespace-nowrap">{tx.order_id}</td>
                    <td className="px-4 py-2.5 font-mono text-slate-100 whitespace-nowrap">
                      {formatCurrency(tx.amount, tx.currency)}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-slate-400">{tx.currency}</td>
                    <td className="px-4 py-2.5 text-slate-300 whitespace-nowrap">{tx.payment_method}</td>
                    <td className="px-4 py-2.5 whitespace-nowrap">
                      <StatusBadge value={tx.status} />
                    </td>
                    <td className="px-4 py-2.5 font-mono text-slate-400 max-w-[150px] truncate" title={tx.idempotency_key}>
                      {tx.idempotency_key}
                    </td>
                    <td className="px-4 py-2.5 text-slate-400 whitespace-nowrap">{formatDateTime(tx.created_at)}</td>
                    <td className="px-4 py-2.5 font-mono text-slate-400 whitespace-nowrap">
                      {formatDurationMs(tx.processing_duration_ms)}
                    </td>
                    <td className="px-4 py-2.5 text-right whitespace-nowrap">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedTxId(tx.transaction_id);
                        }}
                        className="inline-flex items-center gap-1 px-2 py-1 rounded bg-[#181E2A] hover:bg-[#232C3D] text-slate-200 text-[11px]"
                      >
                        <Eye className="h-3 w-3" />
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {pagination && pagination.total > 0 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-[#222836] bg-[#0D1016] text-xs text-slate-400">
            <span>
              Showing page <strong className="text-slate-200">{pagination.page}</strong> of{' '}
              <strong className="text-slate-200">{pagination.total_pages}</strong> ({pagination.total} records)
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={pagination.page <= 1}
                className="pg-btn-secondary py-1 px-2.5 text-xs"
              >
                <ChevronLeft className="h-3.5 w-3.5" /> Prev
              </button>
              <button
                onClick={() => setPage((p) => Math.min(pagination.total_pages, p + 1))}
                disabled={pagination.page >= pagination.total_pages}
                className="pg-btn-secondary py-1 px-2.5 text-xs"
              >
                Next <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>

      <TransactionDetailDrawer transactionId={selectedTxId} onClose={() => setSelectedTxId(null)} />
    </div>
  );
};

