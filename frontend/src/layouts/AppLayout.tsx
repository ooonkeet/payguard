import React, { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  BarChart3,
  Bell,
  Bug,
  ChevronLeft,
  ChevronRight,
  CreditCard,
  Database,
  FlaskConical,
  LayoutDashboard,
  ListOrdered,
  Menu,
  Search,
  Settings,
  ShieldCheck,
  Terminal,
  Webhook,
  X,
} from 'lucide-react';
import { payguardApi } from '../services/api';

const NAV_ITEMS = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/transactions', label: 'Transactions', icon: ListOrdered },
  { to: '/simulator', label: 'Payment Simulator', icon: CreditCard },
  { to: '/api-console', label: 'API Testing', icon: Terminal },
  { to: '/test-suites', label: 'Test Suites', icon: FlaskConical },
  { to: '/webhooks', label: 'Webhook Monitor', icon: Webhook },
  { to: '/validation', label: 'Database Validation', icon: Database },
  { to: '/bugs', label: 'Bug Tracker', icon: Bug },
  { to: '/reports', label: 'Test Reports', icon: BarChart3 },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export const AppLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [notifOpen, setNotifOpen] = useState(false);
  const navigate = useNavigate();

  const { data: health, isError: healthError } = useQuery({
    queryKey: ['health'],
    queryFn: payguardApi.getHealth,
    refetchInterval: 20000,
    retry: 1,
  });

  const { data: txData } = useQuery({
    queryKey: ['notifications-failures'],
    queryFn: () => payguardApi.getDashboardTransactions({ range: '30d' }),
    refetchInterval: 30000,
  });

  const recentFailures: Array<{
    transaction_id: string;
    response_code: string;
    failure_reason: string;
  }> = txData?.recent_failures || [];

  const handleGlobalSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const q = searchQuery.trim();
    if (!q) return;
    navigate(`/transactions?search=${encodeURIComponent(q)}`);
  };

  const renderNavLinks = (onNavigate?: () => void) => (
    <nav className="flex-1 px-2.5 py-3 space-y-0.5 overflow-y-auto" aria-label="Primary navigation">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        return (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-2.5 py-2 rounded-md text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                  : 'text-slate-400 hover:text-slate-100 hover:bg-[#171C26] border border-transparent'
              }`
            }
            title={collapsed ? item.label : undefined}
          >
            <Icon className="h-4 w-4 shrink-0" />
            {!collapsed && <span className="truncate">{item.label}</span>}
          </NavLink>
        );
      })}
    </nav>
  );

  return (
    <div className="min-h-screen flex bg-[#0A0C10] text-slate-100">
      {/* Desktop Sidebar */}
      <aside
        className={`hidden md:flex flex-col shrink-0 bg-[#0D1017] border-r border-[#222836] transition-all duration-200 ${
          collapsed ? 'w-16' : 'w-60'
        }`}
      >
        <div className="h-14 flex items-center justify-between px-3.5 border-b border-[#222836]">
          <div className="flex items-center gap-2 min-w-0">
            <div className="h-7 w-7 rounded-md bg-emerald-500/15 border border-emerald-500/40 flex items-center justify-center shrink-0">
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
            </div>
            {!collapsed && (
              <div className="min-w-0">
                <span className="font-semibold text-sm tracking-tight text-slate-100 block leading-none">
                  PayGuard
                </span>
                <span className="text-[10px] font-mono text-slate-500 tracking-wider">QA PLATFORM</span>
              </div>
            )}
          </div>
          <button
            onClick={() => setCollapsed((c) => !c)}
            className="p-1 rounded text-slate-500 hover:text-slate-200 hover:bg-[#171C26]"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
        </div>

        {renderNavLinks()}

        {!collapsed && (
          <div className="p-3 border-t border-[#222836]">
            <div className="rounded-md bg-[#11151E] border border-[#222836] px-2.5 py-2">
              <p className="text-[10px] font-mono uppercase tracking-wider text-amber-400">
                Simulated Payment Environment
              </p>
              <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">
                Synthetic data only. No live money or real cards.
              </p>
            </div>
          </div>
        )}
      </aside>

      {/* Mobile Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          <div className="fixed inset-0 bg-black/70" onClick={() => setMobileOpen(false)} />
          <aside className="relative w-64 max-w-[80vw] bg-[#0D1017] border-r border-[#222836] flex flex-col z-10">
            <div className="h-14 flex items-center justify-between px-4 border-b border-[#222836]">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-emerald-400" />
                <span className="font-semibold text-sm text-slate-100">PayGuard</span>
              </div>
              <button onClick={() => setMobileOpen(false)} className="text-slate-400" aria-label="Close menu">
                <X className="h-5 w-5" />
              </button>
            </div>
            {renderNavLinks(() => setMobileOpen(false))}
          </aside>
        </div>
      )}

      {/* Main Column */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Bar */}
        <header className="h-14 sticky top-0 z-30 bg-[#0D1017]/95 backdrop-blur border-b border-[#222836] px-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => setMobileOpen(true)}
              className="md:hidden p-1.5 rounded-md text-slate-400 hover:text-slate-100 hover:bg-[#171C26]"
              aria-label="Open navigation menu"
            >
              <Menu className="h-5 w-5" />
            </button>

            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-400 font-mono text-[11px] font-medium">
              SANDBOX
            </span>

            <span className="hidden xl:inline-flex items-center text-[11px] font-mono text-slate-500 uppercase tracking-wider">
              SIMULATED PAYMENT ENVIRONMENT
            </span>

            {/* Global Search */}
            <form onSubmit={handleGlobalSearch} className="hidden sm:flex items-center relative ml-2 w-56 lg:w-72">
              <Search className="h-3.5 w-3.5 text-slate-500 absolute left-2.5 pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search TXN ID, Order ID..."
                className="w-full bg-[#11141B] border border-[#222836] rounded-md pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500/60"
              />
            </form>
          </div>

          <div className="flex items-center gap-3">
            {/* Backend Status */}
            <div
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#11141B] border border-[#222836] text-xs"
              title={health ? `DB: ${health.database_engine} | v${health.version}` : 'Checking API status'}
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  healthError ? 'bg-red-500' : health?.status === 'healthy' ? 'bg-emerald-400' : 'bg-amber-400'
                }`}
              />
              <span className="hidden sm:inline font-mono text-[11px] text-slate-300">
                {healthError ? 'API Offline' : health ? 'API Connected' : 'Connecting'}
              </span>
            </div>

            {/* Notifications */}
            <div className="relative">
              <button
                onClick={() => setNotifOpen((o) => !o)}
                className="relative p-1.5 rounded-md text-slate-400 hover:text-slate-100 hover:bg-[#171C26]"
                aria-label="Recent alerts"
              >
                <Bell className="h-4 w-4" />
                {recentFailures.length > 0 && (
                  <span className="absolute top-1 right-1 h-1.5 w-1.5 rounded-full bg-red-500" />
                )}
              </button>
              {notifOpen && (
                <div className="absolute right-0 mt-2 w-80 rounded-lg bg-[#12161F] border border-[#2A3244] shadow-xl p-3 z-50">
                  <div className="flex items-center justify-between pb-2 border-b border-[#222836]">
                    <span className="text-xs font-semibold text-slate-200">Recent Payment Failures</span>
                    <button onClick={() => setNotifOpen(false)} className="text-slate-500 hover:text-slate-300">
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <div className="mt-2 space-y-2 max-h-64 overflow-y-auto">
                    {recentFailures.length === 0 ? (
                      <p className="text-xs text-slate-500 py-3 text-center">No recent payment failures.</p>
                    ) : (
                      recentFailures.slice(0, 5).map((f) => (
                        <button
                          key={f.transaction_id}
                          onClick={() => {
                            setNotifOpen(false);
                            navigate(`/transactions?search=${encodeURIComponent(f.transaction_id)}`);
                          }}
                          className="w-full text-left p-2 rounded hover:bg-[#19202D] transition-colors"
                        >
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-mono text-red-400">{f.transaction_id}</span>
                            <span className="font-mono text-[10px] text-slate-500">{f.response_code}</span>
                          </div>
                          <p className="text-[11px] text-slate-400 truncate mt-0.5">{f.failure_reason}</p>
                        </button>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* User Profile */}
            <div className="flex items-center gap-2 pl-2 border-l border-[#222836]">
              <div className="h-7 w-7 rounded-full bg-[#1A2130] border border-[#2D374B] flex items-center justify-center text-[11px] font-semibold text-emerald-400">
                QA
              </div>
              <div className="hidden lg:block leading-tight">
                <p className="text-xs font-medium text-slate-200">QA Engineer</p>
                <p className="text-[10px] text-slate-500 font-mono">sandbox-console</p>
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 p-4 sm:p-6 max-w-[1440px] w-full mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

