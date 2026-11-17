import axios from 'axios';
import type {
  ApiCollection,
  ApiRequestItem,
  Bug,
  ConsistencyReport,
  ConsoleExecutionResult,
  PaginationMeta,
  PaymentMethod,
  PaymentScenario,
  SupportedCurrency,
  TestResult,
  TestRun,
  TestSuiteName,
  Transaction,
  TransactionDetail,
  ValidationCheckDefinition,
  ValidationResult,
  WebhookEvent,
} from '../types';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 180000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export function extractErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const data = err.response?.data as
      | { error?: { message?: string; code?: string }; detail?: string }
      | undefined;
    if (data?.error?.message) {
      return data.error.code ? `[${data.error.code}] ${data.error.message}` : data.error.message;
    }
    if (data?.detail) return data.detail;
    return err.message || 'Network request failed';
  }
  if (err instanceof Error) return err.message;
  return 'Unexpected error occurred';
}

export const payguardApi = {
  // Health
  getHealth: async () => {
    const { data } = await apiClient.get('/api/v1/health');
    return data.data as {
      status: string;
      service: string;
      version: string;
      environment: string;
      simulation_mode: boolean;
      database: string;
      database_engine: string;
      timestamp: string;
    };
  },

  // Dashboard
  getDashboardMetrics: async (params: { range: string; start_date?: string; end_date?: string }) => {
    const { data } = await apiClient.get('/api/v1/dashboard/metrics', { params });
    return data.data;
  },
  getDashboardTransactions: async (params: { range: string; start_date?: string; end_date?: string }) => {
    const { data } = await apiClient.get('/api/v1/dashboard/transactions', { params });
    return data.data;
  },
  getDashboardTestActivity: async (params: { range: string; start_date?: string; end_date?: string }) => {
    const { data } = await apiClient.get('/api/v1/dashboard/test-activity', { params });
    return data.data;
  },

  // Payments & Transactions
  createPayment: async (payload: {
    order_id: string;
    amount: string;
    currency: SupportedCurrency;
    payment_method: PaymentMethod;
    customer_reference?: string;
    idempotency_key: string;
    scenario: PaymentScenario;
  }) => {
    const { data } = await apiClient.post('/api/v1/payments', payload);
    return { transaction: data.data as Transaction, idempotentReplay: Boolean(data.meta?.idempotent_replay) };
  },
  listPayments: async (params: Record<string, string | number | undefined>) => {
    const { data } = await apiClient.get('/api/v1/payments', { params });
    return {
      items: data.data as Transaction[],
      pagination: data.pagination as PaginationMeta,
    };
  },
  getPaymentDetail: async (transactionId: string) => {
    const { data } = await apiClient.get(`/api/v1/payments/${transactionId}`);
    return data.data as TransactionDetail;
  },
  refundPayment: async (transactionId: string, reason: string) => {
    const { data } = await apiClient.post(`/api/v1/payments/${transactionId}/refund`, { reason });
    return data.data as Transaction;
  },
  reconcilePayment: async (transactionId: string, resolved_status: 'SUCCESS' | 'FAILED', note?: string) => {
    const { data } = await apiClient.post(`/api/v1/payments/${transactionId}/reconcile`, {
      resolved_status,
      note,
    });
    return data.data as Transaction;
  },

  // Webhooks
  listWebhookEvents: async (params?: { delivery_status?: string; event_type?: string; transaction_id?: string }) => {
    const { data } = await apiClient.get('/api/v1/webhooks/events', { params });
    return data.data as WebhookEvent[];
  },
  simulateWebhook: async (payload: {
    transaction_id: string;
    event_type: 'payment.success' | 'payment.failed' | 'payment.pending' | 'payment.refunded';
    event_id?: string;
    simulate_invalid_signature?: boolean;
    simulate_duplicate?: boolean;
    simulate_delivery_failure?: boolean;
    delay_ms?: number;
  }) => {
    const resp = await apiClient.post('/api/v1/webhooks/simulate', payload, {
      validateStatus: (s) => s < 500,
    });
    return {
      status: resp.status,
      event: resp.data.data as WebhookEvent,
      deduplicated: Boolean(resp.data.meta?.deduplicated),
      errorMessage: resp.data.error?.message as string | undefined,
    };
  },
  retryWebhookEvent: async (eventId: string) => {
    const { data } = await apiClient.post(`/api/v1/webhooks/events/${eventId}/retry`);
    return data.data as WebhookEvent;
  },

  // Automated Test Suites
  runTestSuite: async (suite_name: TestSuiteName, with_coverage = true) => {
    const { data } = await apiClient.post('/api/v1/tests/run', { suite_name, with_coverage });
    return data.data as TestRun;
  },
  listTestRuns: async (suite_name?: string) => {
    const { data } = await apiClient.get('/api/v1/tests/runs', { params: { suite_name } });
    return data.data as TestRun[];
  },
  getTestRun: async (runId: string) => {
    const { data } = await apiClient.get(`/api/v1/tests/runs/${runId}`);
    return data.data as TestRun;
  },
  getTestRunResults: async (runId: string) => {
    const { data } = await apiClient.get(`/api/v1/tests/runs/${runId}/results`);
    return data.data as TestResult[];
  },
  getHtmlReportUrl: (runId: string) => `${API_BASE_URL}/api/v1/tests/runs/${runId}/report`,

  // Database Validation
  getValidationChecks: async () => {
    const { data } = await apiClient.get('/api/v1/validation/checks');
    return data.data as ValidationCheckDefinition[];
  },
  runValidationChecks: async (check_keys?: string[], transaction_id?: string) => {
    const { data } = await apiClient.post('/api/v1/validation/run', { check_keys, transaction_id });
    return data.data as ValidationResult[];
  },
  listValidationResults: async () => {
    const { data } = await apiClient.get('/api/v1/validation/results');
    return data.data as ValidationResult[];
  },
  checkConsistency: async (transactionId: string) => {
    const { data } = await apiClient.get(`/api/v1/validation/consistency/${transactionId}`);
    return data.data as ConsistencyReport;
  },

  // Bugs
  listBugs: async (params?: { search?: string; severity?: string; status?: string; module?: string }) => {
    const { data } = await apiClient.get('/api/v1/bugs', { params });
    return data.data as Bug[];
  },
  createBug: async (payload: Partial<Bug> & { title: string; description: string }) => {
    const { data } = await apiClient.post('/api/v1/bugs', payload);
    return data.data as Bug;
  },
  updateBug: async (bugId: string, payload: Partial<Bug>) => {
    const { data } = await apiClient.patch(`/api/v1/bugs/${bugId}`, payload);
    return data.data as Bug;
  },
  deleteBug: async (bugId: string) => {
    const { data } = await apiClient.delete(`/api/v1/bugs/${bugId}`);
    return data.data;
  },

  // Reports
  getReportMetrics: async (params?: { suite_name?: string; include_seeded?: boolean }) => {
    const { data } = await apiClient.get('/api/v1/reports/metrics', { params });
    return data.data;
  },
  getTransactionsCsvUrl: () => `${API_BASE_URL}/api/v1/reports/transactions.csv`,
  getTestsCsvUrl: () => `${API_BASE_URL}/api/v1/reports/tests.csv`,

  // API Collections & Console
  listCollections: async () => {
    const { data } = await apiClient.get('/api/v1/collections');
    return data.data as ApiCollection[];
  },
  createCollection: async (payload: { collection_name: string; description?: string; requests: ApiRequestItem[] }) => {
    const { data } = await apiClient.post('/api/v1/collections', payload);
    return data.data as ApiCollection;
  },
  updateCollection: async (
    id: number,
    payload: { collection_name?: string; description?: string; requests?: ApiRequestItem[] },
  ) => {
    const { data } = await apiClient.put(`/api/v1/collections/${id}`, payload);
    return data.data as ApiCollection;
  },
  executeConsoleRequest: async (payload: {
    method: string;
    endpoint: string;
    headers: Record<string, string>;
    query_params: Record<string, string>;
    body: unknown;
    sign_webhook?: boolean;
    invalid_signature?: boolean;
  }) => {
    const { data } = await apiClient.post('/api/v1/collections/execute', payload);
    return data.data as ConsoleExecutionResult;
  },

  // Settings
  getSettings: async () => {
    const { data } = await apiClient.get('/api/v1/settings');
    return data.data;
  },
  resetDemoData: async () => {
    const { data } = await apiClient.post('/api/v1/settings/reset-demo');
    return data.data;
  },
};

