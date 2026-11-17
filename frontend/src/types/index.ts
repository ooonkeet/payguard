export type PaymentStatus = 'CREATED' | 'PROCESSING' | 'SUCCESS' | 'FAILED' | 'PENDING' | 'REFUNDED';
export type PaymentMethod = 'UPI' | 'CARD' | 'NET_BANKING' | 'WALLET';
export type SupportedCurrency = 'INR' | 'USD' | 'EUR' | 'GBP' | 'SGD';

export type PaymentScenario =
  | 'successful_payment'
  | 'insufficient_balance'
  | 'invalid_payment_details'
  | 'gateway_timeout'
  | 'gateway_unavailable'
  | 'pending_transaction'
  | 'delayed_webhook'
  | 'duplicate_payment_request'
  | 'payment_failure'
  | 'processing_error';

export interface TimelineEvent {
  stage: string;
  status: string;
  timestamp: string;
  detail: string;
  elapsed_ms: number;
}

export interface Transaction {
  id: number;
  transaction_id: string;
  order_id: string;
  amount: string;
  currency: SupportedCurrency;
  payment_method: PaymentMethod;
  customer_reference?: string | null;
  scenario: PaymentScenario;
  status: PaymentStatus;
  idempotency_key: string;
  gateway_reference?: string | null;
  response_code: string;
  failure_reason?: string | null;
  processing_duration_ms: number;
  is_seeded: boolean;
  created_at: string;
  updated_at: string;
  idempotent_replay?: boolean;
  timeline?: TimelineEvent[];
}

export interface TransactionDetail extends Transaction {
  request_payload?: Record<string, unknown> | null;
  response_payload?: Record<string, unknown> | null;
  webhooks: Array<{
    event_id: string;
    event_type: string;
    delivery_status: string;
    signature_valid: boolean;
    attempt_count: number;
    duplicate_attempts: number;
    created_at: string;
    delivered_at?: string | null;
  }>;
  related_bugs: Array<{
    bug_id: string;
    title: string;
    severity: string;
    status: string;
    created_at: string;
  }>;
  related_tests: Array<{
    run_id: string;
    test_name: string;
    test_status: string;
    duration: number;
    created_at: string;
  }>;
}

export interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface WebhookEvent {
  id: number;
  event_id: string;
  transaction_id?: string | null;
  event_type: 'payment.success' | 'payment.failed' | 'payment.pending' | 'payment.refunded';
  payload: Record<string, unknown>;
  signature_valid: boolean;
  delivery_status: string;
  attempt_count: number;
  duplicate_attempts: number;
  processing_logs?: Array<{ timestamp: string; level: string; message: string }>;
  is_seeded: boolean;
  created_at: string;
  delivered_at?: string | null;
  deduplicated?: boolean;
}

export type TestSuiteName = 'all' | 'smoke' | 'regression' | 'edge_cases' | 'api_contract' | 'database';

export interface TestResult {
  id: number;
  run_id: string;
  test_name: string;
  node_id?: string | null;
  test_status: 'PASSED' | 'FAILED' | 'SKIPPED';
  failure_message?: string | null;
  duration: number;
  created_at: string;
}

export interface TestRun {
  id: number;
  run_id: string;
  suite_name: string;
  total_tests: number;
  passed: number;
  failed: number;
  skipped: number;
  duration: number;
  code_coverage?: number | null;
  execution_status: string;
  report_path?: string | null;
  stdout_summary?: string | null;
  is_seeded: boolean;
  started_at: string;
  completed_at?: string | null;
  pass_rate: number;
  results?: TestResult[];
}

export interface Bug {
  id: number;
  bug_id: string;
  title: string;
  description: string;
  severity: 'Critical' | 'High' | 'Medium' | 'Low';
  priority: 'P0' | 'P1' | 'P2' | 'P3';
  status: 'OPEN' | 'IN_PROGRESS' | 'FIXED' | 'VERIFIED' | 'CLOSED';
  module: string;
  reproduction_steps?: string | null;
  expected_result?: string | null;
  actual_result?: string | null;
  environment: string;
  transaction_id?: string | null;
  associated_test_case?: string | null;
  is_seeded: boolean;
  created_at: string;
  updated_at: string;
}

export interface ValidationCheckDefinition {
  check_key: string;
  check_name: string;
  description: string;
  category: string;
}

export interface ValidationResult {
  id: number;
  check_key: string;
  check_name: string;
  execution_status: 'PASS' | 'WARN' | 'FAIL';
  records_examined: number;
  issues_detected: number;
  details?: Array<Record<string, unknown>> | null;
  execution_duration_ms: number;
  executed_at: string;
}

export interface ConsistencyReport {
  transaction_id: string;
  consistent: boolean;
  api_response_status?: string | null;
  db_status?: string | null;
  latest_webhook_event?: string | null;
  latest_webhook_status?: string | null;
  final_payment_state?: string | null;
  amount_consistent: boolean;
  discrepancies: string[];
  details: Record<string, unknown>;
}

export interface ApiRequestItem {
  id: string;
  name: string;
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  endpoint: string;
  headers: Record<string, string>;
  query_params: Record<string, string>;
  body: unknown;
  description?: string;
  sign_webhook?: boolean;
  invalid_signature?: boolean;
}

export interface ApiCollection {
  id: number;
  collection_name: string;
  description?: string | null;
  configuration: { requests: ApiRequestItem[] };
  is_seeded: boolean;
  created_at: string;
  updated_at: string;
}

export interface ConsoleExecutionResult {
  status_code: number;
  reason_phrase: string;
  duration_ms: number;
  headers: Record<string, string>;
  body: unknown;
  request_path: string;
  method: string;
}

