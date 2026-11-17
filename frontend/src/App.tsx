import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ToastProvider } from './components/ToastProvider';
import { AppLayout } from './layouts/AppLayout';
import { ApiTestingPage } from './pages/ApiTestingPage';
import { BugTrackerPage } from './pages/BugTrackerPage';
import { DatabaseValidationPage } from './pages/DatabaseValidationPage';
import { OverviewPage } from './pages/OverviewPage';
import { PaymentSimulatorPage } from './pages/PaymentSimulatorPage';
import { SettingsPage } from './pages/SettingsPage';
import { TestReportsPage } from './pages/TestReportsPage';
import { TestSuitesPage } from './pages/TestSuitesPage';
import { TransactionsPage } from './pages/TransactionsPage';
import { WebhookMonitorPage } from './pages/WebhookMonitorPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10000,
      refetchOnWindowFocus: false,
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<AppLayout />}>
              <Route path="/" element={<OverviewPage />} />
              <Route path="/transactions" element={<TransactionsPage />} />
              <Route path="/simulator" element={<PaymentSimulatorPage />} />
              <Route path="/api-console" element={<ApiTestingPage />} />
              <Route path="/test-suites" element={<TestSuitesPage />} />
              <Route path="/webhooks" element={<WebhookMonitorPage />} />
              <Route path="/validation" element={<DatabaseValidationPage />} />
              <Route path="/bugs" element={<BugTrackerPage />} />
              <Route path="/reports" element={<TestReportsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
};

export default App;

