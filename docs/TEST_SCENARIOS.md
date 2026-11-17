# PayGuard Test Scenario Catalog

This catalog documents the automated backend (Pytest) and end-to-end UI (Playwright) test scenarios executed against PayGuard.

## 1. API & Contract Tests (`tests/api/test_api_contracts.py` — 22 cases)
- Root and versioned `/health` & `/api/v1/health` availability and contract fields.
- Payment creation response envelope, required fields, decimal formatting, and lifecycle timeline structure.
- Transaction retrieval (`GET /api/v1/payments/{id}`) and lightweight status lookup (`GET /api/v1/payments/{id}/status`).
- Pagination, search, status filtering, method filtering, and amount sorting.
- Negative boundary testing: missing required fields (`422`), negative & zero amounts (`422`), max amount overflow (`422`), unsupported currency (`422`), invalid payment method (`422`), short idempotency key (`422`), non-existent transaction ID (`404`).
- Authentication endpoint testing: valid Bearer token (`200`), invalid token (`401`), missing header (`401`), expired token (`401`).
- Bug tracker CRUD lifecycle & status transition persistence.
- Dashboard analytics accuracy derived directly from persisted transactions.
- Reporting metrics separation and downloadable CSV report verification.
- API Console SSRF protection (blocks external hosts) & local ASGI execution.
- Test Runner strict suite whitelist validation (blocks arbitrary shell commands).

## 2. Payment Reliability & State Machine Tests (`tests/payment/test_payment_engine.py` — 18 cases)
- Successful payments across `UPI`, `CARD`, `NET_BANKING`, and `WALLET`.
- Failure scenarios: `insufficient_balance`, `invalid_payment_details`, `gateway_unavailable`, `payment_failure`, `processing_error`.
- Pending scenarios: `pending_transaction`, `delayed_webhook`.
- Timeout safety: `gateway_timeout` leaves transaction `PENDING` requiring reconciliation rather than falsely reporting `FAILED`.
- Idempotent replay: identical payload + same key returns HTTP `200`, preserves original `transaction_id`, and creates zero duplicate rows.
- Idempotency conflict: modified payload + same key returns HTTP `409 IDEMPOTENCY_CONFLICT`.
- Concurrency protection: 5 simultaneous threads submitting the same `idempotency_key` produce exactly 1 persisted transaction.
- Refund flow: `SUCCESS -> REFUNDED` succeeds; `FAILED -> REFUNDED` and double refunds return `422 INVALID_STATE_TRANSITION`.
- Pending reconciliation: `PENDING -> SUCCESS` succeeds; post-success transition to `FAILED` is rejected.
- Full payment state transition matrix unit verification.

## 3. Webhook Verification & Deduplication Tests (`tests/webhooks/test_webhooks.py` — 10 cases)
- Valid HMAC-SHA256 signed webhook updates `PENDING` transaction to `SUCCESS`.
- Invalid signature rejected (`401`) and audit logged without mutating transaction state.
- Missing signature header rejected (`401`).
- Duplicate `event_id` deduplicated at DB level (`deduplicated=true`, `duplicate_attempts` incremented, transaction never double-processed).
- Simulated delivery failure (`FAILED`) followed by manual retry (`POST /events/{id}/retry`) succeeds and reconciles transaction.
- Retry blocked on invalid-signature events (`400`).
- Webhook attempting illegal state override (`FAILED -> SUCCESS`) is safely ignored.
- Server-side webhook simulator (`payment.refunded` valid delivery & invalid signature 401 test).
- Webhook event listing, filtering by status, and single-event retrieval.

## 4. Database Persistence & Validation Tests (`tests/database/test_database_validation.py` — 10 cases)
- Transaction persistence and exact field verification in SQLAlchemy.
- Unique constraint enforcement on `transactions.transaction_id`.
- Unique constraint enforcement on `transactions.idempotency_key`.
- Exact `Numeric(14, 2)` Decimal storage with zero floating-point drift (`0.10`, `0.20`, `19.99`, `99999.95`).
- Unique constraint enforcement on `webhook_events.event_id`.
- Foreign key referential integrity on `bugs.transaction_id`.
- All 8 predefined database validation checks pass on clean consistent data.
- Validation engine detects orphan webhook events.
- Validation engine & consistency checker detect amount drift between DB row and stored API response payload.
- Consistency checker confirms clean cross-layer state after webhook settlement.

## 5. Cross-Module Integration Tests (`tests/integration/test_end_to_end_flows.py` — 5 cases)
- Delayed-webhook payment → signed webhook settlement → consistency check → dashboard metrics pipeline.
- API Console server-side HMAC signing updating a pending transaction end-to-end.
- Failed payment → linked bug report → transaction detail linkage.
- Demo data reset populating exact baseline counts (20 success, 5 failed, 3 pending, 5 webhooks, 3 test runs, 3 bugs, 4 collections).
- Persistent API collection create/list/delete lifecycle.

## 6. Playwright End-to-End UI Tests (`tests/ui/payguard.spec.ts` — 12 cases)
1. Overview dashboard renders real DB metrics, `SANDBOX` indicator, and live `API Connected` status.
2. Payment Simulator executes successful UPI payment, displays result modal, and persists across page reload.
3. Payment Simulator handles `insufficient_balance` and renders failure diagnostics.
4. Payment Simulator verifies idempotent replay and HTTP `409 IDEMPOTENCY_CONFLICT` UI rejection.
5. Payment Simulator keeps `gateway_timeout` transaction `PENDING` with reconciliation guidance.
6. Transactions table filters by status and opens Transaction Detail Drawer with visual lifecycle timeline.
7. API Testing Console runs real authenticated request from preset collection and renders HTTP 200 JSON body.
8. Automated Test Suites executes real Pytest Smoke suite in backend subprocess and links generated HTML report.
9. Webhook Monitor rejects invalid HMAC signature (`401`) and delivers valid signed webhook.
10. Database Validation runs all 8 integrity checks and verifies transaction consistency (`EXACT DECIMAL MATCH`).
11. Bug Tracker creates and persists a new defect report.
12. Responsive mobile viewport (`390x844`) opens navigation drawer and navigates cleanly.

