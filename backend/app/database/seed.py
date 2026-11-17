"""Initial sandbox demo dataset seeder and reset helper.

All seeded records are explicitly flagged with `is_seeded=True` so the UI
can clearly distinguish synthetic seed data from live executions.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import compute_payload_hash
from app.models.api_collection import ApiCollection
from app.models.bug import Bug
from app.models.test_run import TestResult, TestRun
from app.models.transaction import Transaction
from app.models.validation_result import ValidationResult
from app.models.webhook import WebhookEvent


def _build_seeded_transactions(now: datetime) -> List[Transaction]:
    txs: List[Transaction] = []

    methods = ["UPI", "CARD", "NET_BANKING", "WALLET"]
    currencies = ["INR", "INR", "INR", "USD", "EUR"]

    # 20 successful transactions spread across last 14 days
    for idx in range(1, 21):
        created = now - timedelta(days=14 - (idx * 14 // 20), hours=(idx * 3) % 23, minutes=(idx * 17) % 59)
        method = methods[idx % len(methods)]
        currency = currencies[idx % len(currencies)]
        amount = Decimal(f"{(idx * 425 + 199):.2f}")
        order_id = f"ORD-SEED-{1000 + idx}"
        tx_id = f"TXN-SEED-OK-{idx:03d}"
        idem_key = f"idem-seed-ok-{idx:03d}"
        gw_ref = f"GW-SEED-{9000 + idx}"
        duration = 120 + (idx * 19) % 210
        req_payload = {
            "order_id": order_id,
            "amount": f"{amount:.2f}",
            "currency": currency,
            "payment_method": method,
            "customer_reference": f"cust_synth_{100 + idx}",
            "idempotency_key": idem_key,
            "scenario": "successful_payment",
        }
        fingerprint = {
            "order_id": order_id,
            "amount": f"{amount:.2f}",
            "currency": currency,
            "payment_method": method,
            "customer_reference": f"cust_synth_{100 + idx}",
            "scenario": "successful_payment",
        }
        resp_payload = {
            "transaction_id": tx_id,
            "order_id": order_id,
            "amount": f"{amount:.2f}",
            "currency": currency,
            "payment_method": method,
            "status": "SUCCESS",
            "response_code": "PG_200_APPROVED",
            "failure_reason": None,
            "gateway_reference": gw_ref,
            "processing_duration_ms": duration,
            "scenario": "successful_payment",
        }
        timeline = [
            {"stage": "REQUEST_RECEIVED", "status": "CREATED", "timestamp": created.isoformat(), "detail": "Request accepted by sandbox gateway.", "elapsed_ms": 4},
            {"stage": "VALIDATING", "status": "CREATED", "timestamp": created.isoformat(), "detail": "Validated payload schema and idempotency key.", "elapsed_ms": 18},
            {"stage": "PROCESSING", "status": "PROCESSING", "timestamp": created.isoformat(), "detail": f"Routed via {method} switch ({gw_ref}).", "elapsed_ms": 45},
            {"stage": "GATEWAY_RESPONSE", "status": "SUCCESS", "timestamp": created.isoformat(), "detail": "Acquirer approved payment.", "elapsed_ms": duration - 12},
            {"stage": "TRANSACTION_UPDATED", "status": "SUCCESS", "timestamp": created.isoformat(), "detail": "Persisted SUCCESS state.", "elapsed_ms": duration - 4},
            {"stage": "COMPLETED", "status": "SUCCESS", "timestamp": created.isoformat(), "detail": "Completed.", "elapsed_ms": duration},
        ]
        txs.append(
            Transaction(
                transaction_id=tx_id,
                order_id=order_id,
                amount=amount,
                currency=currency,
                payment_method=method,
                customer_reference=f"cust_synth_{100 + idx}",
                scenario="successful_payment",
                status="SUCCESS",
                idempotency_key=idem_key,
                payload_hash=compute_payload_hash(fingerprint),
                gateway_reference=gw_ref,
                response_code="PG_200_APPROVED",
                failure_reason=None,
                processing_duration_ms=duration,
                request_payload=req_payload,
                response_payload=resp_payload,
                timeline=timeline,
                is_seeded=True,
                created_at=created,
                updated_at=created,
            )
        )

    # 5 failed transactions
    failed_specs = [
        ("insufficient_balance", "PG_402_INSUFFICIENT_FUNDS", "Issuer declined transaction: insufficient available balance.", "UPI", "1499.00", "INR"),
        ("invalid_payment_details", "PG_400_INVALID_INSTRUMENT", "Payment instrument validation failed (synthetic VPA/card token rejected).", "CARD", "899.50", "INR"),
        ("gateway_unavailable", "PG_503_GATEWAY_UNAVAILABLE", "Acquiring gateway temporarily unavailable (HTTP 503 circuit open).", "NET_BANKING", "5200.00", "INR"),
        ("payment_failure", "PG_422_PAYMENT_FAILED", "Transaction failed during acquirer risk and authorization check.", "CARD", "240.00", "USD"),
        ("processing_error", "PG_500_PROCESSING_ERROR", "Simulated processor internal routing exception during settlement.", "WALLET", "750.00", "INR"),
    ]
    for idx, (scenario, code, reason, method, amt_str, curr) in enumerate(failed_specs, start=1):
        created = now - timedelta(days=6 - idx, hours=idx * 2)
        amount = Decimal(amt_str)
        order_id = f"ORD-SEED-FAIL-{idx:02d}"
        tx_id = f"TXN-SEED-FL-{idx:03d}"
        idem_key = f"idem-seed-fail-{idx:03d}"
        gw_ref = f"GW-SEED-FL-{idx:03d}"
        duration = 140 + idx * 35
        fingerprint = {
            "order_id": order_id,
            "amount": f"{amount:.2f}",
            "currency": curr,
            "payment_method": method,
            "customer_reference": f"cust_synth_fl_{idx}",
            "scenario": scenario,
        }
        req_payload = {**fingerprint, "idempotency_key": idem_key}
        resp_payload = {
            "transaction_id": tx_id,
            "order_id": order_id,
            "amount": f"{amount:.2f}",
            "currency": curr,
            "payment_method": method,
            "status": "FAILED",
            "response_code": code,
            "failure_reason": reason,
            "gateway_reference": gw_ref,
            "processing_duration_ms": duration,
            "scenario": scenario,
        }
        timeline = [
            {"stage": "REQUEST_RECEIVED", "status": "CREATED", "timestamp": created.isoformat(), "detail": "Request accepted.", "elapsed_ms": 5},
            {"stage": "VALIDATING", "status": "CREATED", "timestamp": created.isoformat(), "detail": "Input validated.", "elapsed_ms": 20},
            {"stage": "PROCESSING", "status": "PROCESSING", "timestamp": created.isoformat(), "detail": f"Dispatched to {method} switch.", "elapsed_ms": 60},
            {"stage": "GATEWAY_RESPONSE", "status": "FAILED", "timestamp": created.isoformat(), "detail": reason, "elapsed_ms": duration - 10},
            {"stage": "TRANSACTION_UPDATED", "status": "FAILED", "timestamp": created.isoformat(), "detail": f"Recorded FAILED ({code}).", "elapsed_ms": duration - 3},
            {"stage": "COMPLETED", "status": "FAILED", "timestamp": created.isoformat(), "detail": "Completed with failure.", "elapsed_ms": duration},
        ]
        txs.append(
            Transaction(
                transaction_id=tx_id,
                order_id=order_id,
                amount=amount,
                currency=curr,
                payment_method=method,
                customer_reference=f"cust_synth_fl_{idx}",
                scenario=scenario,
                status="FAILED",
                idempotency_key=idem_key,
                payload_hash=compute_payload_hash(fingerprint),
                gateway_reference=gw_ref,
                response_code=code,
                failure_reason=reason,
                processing_duration_ms=duration,
                request_payload=req_payload,
                response_payload=resp_payload,
                timeline=timeline,
                is_seeded=True,
                created_at=created,
                updated_at=created,
            )
        )

    # 3 pending transactions (including timeout awaiting reconciliation and delayed webhook)
    pending_specs = [
        ("gateway_timeout", "PG_504_GATEWAY_TIMEOUT", "Upstream gateway timed out before confirmation; awaiting reconciliation.", "UPI", "3250.00", "INR"),
        ("pending_transaction", "PG_202_AWAITING_CONFIRMATION", None, "NET_BANKING", "1890.00", "INR"),
        ("delayed_webhook", "PG_202_WEBHOOK_DELAYED", None, "CARD", "125.00", "USD"),
    ]
    for idx, (scenario, code, reason, method, amt_str, curr) in enumerate(pending_specs, start=1):
        created = now - timedelta(hours=18 - idx * 4)
        amount = Decimal(amt_str)
        order_id = f"ORD-SEED-PND-{idx:02d}"
        tx_id = f"TXN-SEED-PN-{idx:03d}"
        idem_key = f"idem-seed-pnd-{idx:03d}"
        gw_ref = f"GW-SEED-PN-{idx:03d}"
        duration = 280 + idx * 55
        fingerprint = {
            "order_id": order_id,
            "amount": f"{amount:.2f}",
            "currency": curr,
            "payment_method": method,
            "customer_reference": f"cust_synth_pn_{idx}",
            "scenario": scenario,
        }
        req_payload = {**fingerprint, "idempotency_key": idem_key}
        resp_payload = {
            "transaction_id": tx_id,
            "order_id": order_id,
            "amount": f"{amount:.2f}",
            "currency": curr,
            "payment_method": method,
            "status": "PENDING",
            "response_code": code,
            "failure_reason": reason,
            "gateway_reference": gw_ref,
            "processing_duration_ms": duration,
            "scenario": scenario,
        }
        timeline = [
            {"stage": "REQUEST_RECEIVED", "status": "CREATED", "timestamp": created.isoformat(), "detail": "Request accepted.", "elapsed_ms": 5},
            {"stage": "VALIDATING", "status": "CREATED", "timestamp": created.isoformat(), "detail": "Input validated.", "elapsed_ms": 18},
            {"stage": "PROCESSING", "status": "PROCESSING", "timestamp": created.isoformat(), "detail": f"Dispatched to {method} switch.", "elapsed_ms": 75},
            {"stage": "GATEWAY_RESPONSE", "status": "PENDING", "timestamp": created.isoformat(), "detail": "Awaiting final settlement / reconciliation.", "elapsed_ms": duration - 8},
            {"stage": "TRANSACTION_UPDATED", "status": "PENDING", "timestamp": created.isoformat(), "detail": f"Recorded PENDING ({code}).", "elapsed_ms": duration},
        ]
        txs.append(
            Transaction(
                transaction_id=tx_id,
                order_id=order_id,
                amount=amount,
                currency=curr,
                payment_method=method,
                customer_reference=f"cust_synth_pn_{idx}",
                scenario=scenario,
                status="PENDING",
                idempotency_key=idem_key,
                payload_hash=compute_payload_hash(fingerprint),
                gateway_reference=gw_ref,
                response_code=code,
                failure_reason=reason,
                processing_duration_ms=duration,
                request_payload=req_payload,
                response_payload=resp_payload,
                timeline=timeline,
                is_seeded=True,
                created_at=created,
                updated_at=created,
            )
        )

    return txs


def _build_seeded_webhooks(now: datetime) -> List[WebhookEvent]:
    specs = [
        ("EVT-SEED-001", "TXN-SEED-OK-001", "payment.success", True, "DELIVERED", 1, 0, 72),
        ("EVT-SEED-002", "TXN-SEED-OK-005", "payment.success", True, "DELIVERED", 2, 1, 48),
        ("EVT-SEED-003", "TXN-SEED-FL-001", "payment.failed", True, "DELIVERED", 1, 0, 30),
        ("EVT-SEED-004", "TXN-SEED-PN-001", "payment.pending", True, "FAILED", 2, 0, 12),
        ("EVT-SEED-005", "TXN-SEED-OK-010", "payment.success", False, "INVALID_SIGNATURE", 1, 0, 5),
    ]
    events: List[WebhookEvent] = []
    for ev_id, tx_id, ev_type, sig_valid, d_status, attempts, dup_cnt, hrs_ago in specs:
        created = now - timedelta(hours=hrs_ago)
        delivered = created + timedelta(seconds=2) if d_status == "DELIVERED" else None
        events.append(
            WebhookEvent(
                event_id=ev_id,
                transaction_id=tx_id,
                event_type=ev_type,
                payload={
                    "event_id": ev_id,
                    "event_type": ev_type,
                    "transaction_id": tx_id,
                    "timestamp": created.isoformat(),
                },
                signature_valid=sig_valid,
                delivery_status=d_status,
                attempt_count=attempts,
                duplicate_attempts=dup_cnt,
                processing_logs=[
                    {
                        "timestamp": created.isoformat(),
                        "level": "INFO" if sig_valid else "ERROR",
                        "message": f"Seeded demo webhook event ({d_status}).",
                    }
                ],
                is_seeded=True,
                created_at=created,
                delivered_at=delivered,
            )
        )
    return events


def _build_seeded_test_runs(now: datetime) -> tuple[List[TestRun], List[TestResult]]:
    runs: List[TestRun] = []
    results: List[TestResult] = []

    run_specs = [
        (
            "RUN-SEED-SMOKE-01",
            "smoke",
            5,
            5,
            0,
            0,
            1.42,
            78.4,
            "PASSED",
            48,
            [
                ("test_health_endpoint_available", "PASSED", None, 0.14),
                ("test_create_valid_upi_payment", "PASSED", None, 0.31),
                ("test_get_transaction_by_id", "PASSED", None, 0.22),
                ("test_payment_status_endpoint", "PASSED", None, 0.19),
                ("test_list_transactions_paginated", "PASSED", None, 0.25),
            ],
        ),
        (
            "RUN-SEED-REG-02",
            "regression",
            6,
            5,
            1,
            0,
            2.86,
            82.1,
            "FAILED",
            24,
            [
                ("test_successful_card_payment_persists", "PASSED", None, 0.38),
                ("test_insufficient_balance_declines", "PASSED", None, 0.34),
                ("test_idempotency_replay_returns_original", "PASSED", None, 0.42),
                ("test_idempotency_conflict_returns_409", "PASSED", None, 0.41),
                ("test_pending_reconciliation_flow", "PASSED", None, 0.39),
                (
                    "test_seeded_sample_delayed_webhook_sla",
                    "FAILED",
                    "AssertionError: Seeded demo failure — simulated webhook SLA exceeded 1500ms threshold (observed 1840ms).",
                    0.92,
                ),
            ],
        ),
        (
            "RUN-SEED-DB-03",
            "database",
            4,
            4,
            0,
            0,
            1.15,
            84.6,
            "PASSED",
            6,
            [
                ("test_unique_transaction_id_constraint", "PASSED", None, 0.28),
                ("test_unique_idempotency_key_constraint", "PASSED", None, 0.29),
                ("test_decimal_amount_precision_preserved", "PASSED", None, 0.24),
                ("test_webhook_foreign_key_integrity", "PASSED", None, 0.34),
            ],
        ),
    ]

    for run_id, suite, total, passed, failed, skipped, dur, cov, status, hrs_ago, cases in run_specs:
        started = now - timedelta(hours=hrs_ago)
        runs.append(
            TestRun(
                run_id=run_id,
                suite_name=suite,
                total_tests=total,
                passed=passed,
                failed=failed,
                skipped=skipped,
                duration=dur,
                code_coverage=cov,
                execution_status=status,
                report_path=None,
                stdout_summary=f"[SEEDED DEMO RUN] Suite '{suite}': {passed} passed, {failed} failed in {dur}s.",
                is_seeded=True,
                started_at=started,
                completed_at=started + timedelta(seconds=dur),
            )
        )
        for test_name, test_status, fail_msg, c_dur in cases:
            results.append(
                TestResult(
                    run_id=run_id,
                    test_name=test_name,
                    node_id=f"tests/seeded::{test_name}",
                    test_status=test_status,
                    failure_message=fail_msg,
                    duration=c_dur,
                    created_at=started,
                )
            )

    return runs, results


def _build_seeded_bugs(now: datetime) -> List[Bug]:
    return [
        Bug(
            bug_id="BUG-SEED-001",
            title="Gateway timeout transaction remains PENDING without auto-reconciliation reminder",
            description="When simulating gateway_timeout on UPI payments, transaction properly stays PENDING, but operator needs explicit reconciliation SLA alert.",
            severity="High",
            priority="P1",
            status="OPEN",
            module="Payment Simulator",
            reproduction_steps="1. Open Payment Simulator\n2. Select UPI + gateway_timeout\n3. Submit payment\n4. Inspect transaction detail drawer",
            expected_result="Transaction stays PENDING and displays reconciliation action with timeout code PG_504_GATEWAY_TIMEOUT.",
            actual_result="Reconciliation button works, SLA badge still pending verification in QA cycle.",
            environment="SANDBOX",
            transaction_id="TXN-SEED-PN-001",
            associated_test_case="test_gateway_timeout_remains_pending",
            is_seeded=True,
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=1),
        ),
        Bug(
            bug_id="BUG-SEED-002",
            title="Invalid webhook HMAC signature event should highlight tampered header in audit logs",
            description="Rejected webhook with invalid signature is logged cleanly, requesting clearer visual highlight for invalid HMAC attempts.",
            severity="Medium",
            priority="P2",
            status="IN_PROGRESS",
            module="Webhook Monitor",
            reproduction_steps="1. Open Webhook Monitor\n2. Simulate webhook with Invalid Signature enabled\n3. Verify 401 response and audit log",
            expected_result="HTTP 401 returned, signature_valid=false persisted, transaction untouched.",
            actual_result="Backend enforces 401 cleanly; audit row formatting being enhanced.",
            environment="SANDBOX",
            transaction_id="TXN-SEED-OK-010",
            associated_test_case="test_webhook_invalid_signature_rejected",
            is_seeded=True,
            created_at=now - timedelta(days=1, hours=6),
            updated_at=now - timedelta(hours=12),
        ),
        Bug(
            bug_id="BUG-SEED-003",
            title="Verify CSV transaction export escapes commas in failure_reason field",
            description="Ensure downloadable transaction CSV properly quotes failure_reason text containing commas or punctuation.",
            severity="Low",
            priority="P3",
            status="VERIFIED",
            module="Test Reports",
            reproduction_steps="1. Navigate to Test Reports\n2. Click Download Transactions CSV\n3. Open file in spreadsheet viewer",
            expected_result="All columns align cleanly across rows with embedded punctuation.",
            actual_result="Verified working with Python csv.writer quoting.",
            environment="SANDBOX",
            transaction_id="TXN-SEED-FL-001",
            associated_test_case="test_transactions_csv_export",
            is_seeded=True,
            created_at=now - timedelta(days=3),
            updated_at=now - timedelta(hours=4),
        ),
    ]


def _build_seeded_collections(now: datetime) -> List[ApiCollection]:
    settings = get_settings()
    return [
        ApiCollection(
            collection_name="PAYMENT APIs",
            description="Core payment creation, retrieval, status verification, and refund endpoints.",
            is_seeded=True,
            created_at=now,
            updated_at=now,
            configuration={
                "requests": [
                    {
                        "id": "pay-create",
                        "name": "Create Payment",
                        "method": "POST",
                        "endpoint": "/api/v1/payments",
                        "headers": {"Content-Type": "application/json"},
                        "query_params": {},
                        "body": {
                            "order_id": "ORD-CONSOLE-1001",
                            "amount": "1250.00",
                            "currency": "INR",
                            "payment_method": "UPI",
                            "customer_reference": "cust_api_console",
                            "idempotency_key": "idem-console-1001",
                            "scenario": "successful_payment",
                        },
                        "description": "Simulate a valid UPI payment creation.",
                    },
                    {
                        "id": "pay-get",
                        "name": "Get Payment",
                        "method": "GET",
                        "endpoint": "/api/v1/payments/TXN-SEED-OK-001",
                        "headers": {},
                        "query_params": {},
                        "body": None,
                        "description": "Retrieve full transaction details by transaction_id.",
                    },
                    {
                        "id": "pay-list",
                        "name": "List Transactions",
                        "method": "GET",
                        "endpoint": "/api/v1/payments",
                        "headers": {},
                        "query_params": {"page": "1", "page_size": "10"},
                        "body": None,
                        "description": "List paginated transactions.",
                    },
                    {
                        "id": "pay-refund",
                        "name": "Refund Payment",
                        "method": "POST",
                        "endpoint": "/api/v1/payments/TXN-SEED-OK-002/refund",
                        "headers": {"Content-Type": "application/json"},
                        "query_params": {},
                        "body": {"reason": "API console refund verification"},
                        "description": "Transition a SUCCESS transaction to REFUNDED.",
                    },
                    {
                        "id": "pay-status",
                        "name": "Check Payment Status",
                        "method": "GET",
                        "endpoint": "/api/v1/payments/TXN-SEED-OK-001/status",
                        "headers": {},
                        "query_params": {},
                        "body": None,
                        "description": "Fetch lightweight status envelope for a transaction.",
                    },
                ]
            },
        ),
        ApiCollection(
            collection_name="AUTHENTICATION",
            description="Verify bearer token validation, invalid credentials, missing header, and expired tokens.",
            is_seeded=True,
            created_at=now,
            updated_at=now,
            configuration={
                "requests": [
                    {
                        "id": "auth-valid",
                        "name": "Valid Authentication",
                        "method": "GET",
                        "endpoint": "/api/v1/auth/verify",
                        "headers": {"Authorization": f"Bearer {settings.API_AUTH_TOKEN}"},
                        "query_params": {},
                        "body": None,
                        "description": "Verify sandbox API access with a valid bearer token.",
                    },
                    {
                        "id": "auth-invalid",
                        "name": "Invalid Authentication",
                        "method": "GET",
                        "endpoint": "/api/v1/auth/verify",
                        "headers": {"Authorization": "Bearer invalid_sandbox_token_xyz"},
                        "query_params": {},
                        "body": None,
                        "description": "Expect 401 Unauthorized for an unrecognized token.",
                    },
                    {
                        "id": "auth-missing",
                        "name": "Missing Token",
                        "method": "GET",
                        "endpoint": "/api/v1/auth/verify",
                        "headers": {},
                        "query_params": {},
                        "body": None,
                        "description": "Expect 401 Unauthorized when Authorization header is omitted.",
                    },
                    {
                        "id": "auth-expired",
                        "name": "Expired Token",
                        "method": "GET",
                        "endpoint": "/api/v1/auth/verify",
                        "headers": {"Authorization": f"Bearer {settings.EXPIRED_AUTH_TOKEN}"},
                        "query_params": {},
                        "body": None,
                        "description": "Expect 401 Unauthorized with TOKEN_EXPIRED error code.",
                    },
                ]
            },
        ),
        ApiCollection(
            collection_name="NEGATIVE TESTING",
            description="Boundary, schema validation, missing field, and idempotency conflict negative test cases.",
            is_seeded=True,
            created_at=now,
            updated_at=now,
            configuration={
                "requests": [
                    {
                        "id": "neg-missing",
                        "name": "Missing Required Fields",
                        "method": "POST",
                        "endpoint": "/api/v1/payments",
                        "headers": {"Content-Type": "application/json"},
                        "query_params": {},
                        "body": {"currency": "INR"},
                        "description": "Expect 422 validation error when order_id, amount, and idempotency_key are omitted.",
                    },
                    {
                        "id": "neg-amount",
                        "name": "Invalid Amount",
                        "method": "POST",
                        "endpoint": "/api/v1/payments",
                        "headers": {"Content-Type": "application/json"},
                        "query_params": {},
                        "body": {
                            "order_id": "ORD-NEG-AMT",
                            "amount": "-250.00",
                            "currency": "INR",
                            "payment_method": "UPI",
                            "idempotency_key": "idem-neg-amt-01",
                            "scenario": "successful_payment",
                        },
                        "description": "Expect 422 when monetary amount is negative.",
                    },
                    {
                        "id": "neg-currency",
                        "name": "Invalid Currency",
                        "method": "POST",
                        "endpoint": "/api/v1/payments",
                        "headers": {"Content-Type": "application/json"},
                        "query_params": {},
                        "body": {
                            "order_id": "ORD-NEG-CUR",
                            "amount": "100.00",
                            "currency": "XYZ",
                            "payment_method": "UPI",
                            "idempotency_key": "idem-neg-cur-01",
                            "scenario": "successful_payment",
                        },
                        "description": "Expect 422 for unsupported currency code.",
                    },
                    {
                        "id": "neg-txid",
                        "name": "Invalid Transaction ID",
                        "method": "GET",
                        "endpoint": "/api/v1/payments/TXN-DOES-NOT-EXIST-999",
                        "headers": {},
                        "query_params": {},
                        "body": None,
                        "description": "Expect 404 Not Found for non-existent transaction ID.",
                    },
                    {
                        "id": "neg-idem-key",
                        "name": "Invalid Idempotency Key",
                        "method": "POST",
                        "endpoint": "/api/v1/payments",
                        "headers": {"Content-Type": "application/json"},
                        "query_params": {},
                        "body": {
                            "order_id": "ORD-NEG-IDEM",
                            "amount": "500.00",
                            "currency": "INR",
                            "payment_method": "UPI",
                            "idempotency_key": "ab",
                            "scenario": "successful_payment",
                        },
                        "description": "Expect 422 when idempotency_key fails minimum length validation.",
                    },
                    {
                        "id": "neg-duplicate",
                        "name": "Duplicate Payment Request (Conflict)",
                        "method": "POST",
                        "endpoint": "/api/v1/payments",
                        "headers": {"Content-Type": "application/json"},
                        "query_params": {},
                        "body": {
                            "order_id": "ORD-CONFLICT-MODIFIED",
                            "amount": "9999.00",
                            "currency": "INR",
                            "payment_method": "UPI",
                            "idempotency_key": "idem-seed-ok-001",
                            "scenario": "successful_payment",
                        },
                        "description": "Reuses existing key with different payload — expect 409 IDEMPOTENCY_CONFLICT.",
                    },
                ]
            },
        ),
        ApiCollection(
            collection_name="WEBHOOKS",
            description="Test signed webhooks, invalid HMAC signatures, duplicate event deduplication, and delayed delivery.",
            is_seeded=True,
            created_at=now,
            updated_at=now,
            configuration={
                "requests": [
                    {
                        "id": "wh-valid",
                        "name": "Valid Webhook",
                        "method": "POST",
                        "endpoint": "/api/v1/webhooks/payment",
                        "headers": {"Content-Type": "application/json"},
                        "query_params": {},
                        "body": {
                            "event_id": "EVT-CONSOLE-VALID-01",
                            "event_type": "payment.success",
                            "transaction_id": "TXN-SEED-PN-002",
                            "amount": "1890.00",
                            "currency": "INR",
                        },
                        "sign_webhook": True,
                        "invalid_signature": False,
                        "description": "Server-signed valid HMAC-SHA256 webhook resolving a PENDING transaction.",
                    },
                    {
                        "id": "wh-invalid-sig",
                        "name": "Invalid Webhook Signature",
                        "method": "POST",
                        "endpoint": "/api/v1/webhooks/payment",
                        "headers": {"Content-Type": "application/json"},
                        "query_params": {},
                        "body": {
                            "event_id": "EVT-CONSOLE-BADSIG-01",
                            "event_type": "payment.success",
                            "transaction_id": "TXN-SEED-OK-001",
                        },
                        "sign_webhook": False,
                        "invalid_signature": True,
                        "description": "Sends tampered HMAC signature — expect 401 rejection.",
                    },
                    {
                        "id": "wh-duplicate",
                        "name": "Duplicate Webhook",
                        "method": "POST",
                        "endpoint": "/api/v1/webhooks/payment",
                        "headers": {"Content-Type": "application/json"},
                        "query_params": {},
                        "body": {
                            "event_id": "EVT-SEED-001",
                            "event_type": "payment.success",
                            "transaction_id": "TXN-SEED-OK-001",
                        },
                        "sign_webhook": True,
                        "invalid_signature": False,
                        "description": "Replays an already processed event_id — expect deduplicated=true.",
                    },
                    {
                        "id": "wh-delayed",
                        "name": "Delayed Webhook",
                        "method": "POST",
                        "endpoint": "/api/v1/webhooks/simulate",
                        "headers": {"Content-Type": "application/json"},
                        "query_params": {},
                        "body": {
                            "transaction_id": "TXN-SEED-PN-003",
                            "event_type": "payment.success",
                            "delay_ms": 600,
                        },
                        "description": "Simulates a delayed settlement webhook for a PENDING transaction.",
                    },
                ]
            },
        ),
    ]


def seed_initial_data(db: Session) -> bool:
    """Seed demo data only when the database is empty. Returns True if seeded."""
    existing_tx = db.scalar(select(func.count(Transaction.id))) or 0
    existing_cols = db.scalar(select(func.count(ApiCollection.id))) or 0
    if existing_tx > 0 and existing_cols > 0:
        return False

    now = datetime.now(timezone.utc)

    if existing_tx == 0:
        txs = _build_seeded_transactions(now)
        db.add_all(txs)
        db.flush()

        webhooks = _build_seeded_webhooks(now)
        db.add_all(webhooks)

        runs, results = _build_seeded_test_runs(now)
        db.add_all(runs)
        db.flush()
        db.add_all(results)

        bugs = _build_seeded_bugs(now)
        db.add_all(bugs)

    if existing_cols == 0:
        cols = _build_seeded_collections(now)
        db.add_all(cols)

    db.commit()
    return True


def reset_demo_data(db: Session) -> dict[str, int]:
    """Clear all runtime & demo tables and re-seed a fresh baseline dataset."""
    db.execute(delete(ValidationResult))
    db.execute(delete(TestResult))
    db.execute(delete(TestRun))
    db.execute(delete(WebhookEvent))
    db.execute(delete(Bug))
    db.execute(delete(Transaction))
    db.execute(delete(ApiCollection))
    db.commit()

    seed_initial_data(db)
    return {
        "transactions": db.scalar(select(func.count(Transaction.id))) or 0,
        "webhooks": db.scalar(select(func.count(WebhookEvent.id))) or 0,
        "test_runs": db.scalar(select(func.count(TestRun.id))) or 0,
        "bugs": db.scalar(select(func.count(Bug.id))) or 0,
        "api_collections": db.scalar(select(func.count(ApiCollection.id))) or 0,
    }

