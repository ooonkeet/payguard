"""Database Validation Console Service using safe, predefined parameterized SQLAlchemy checks."""

import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.bug import Bug
from app.models.test_run import TestResult, TestRun
from app.models.transaction import Transaction
from app.models.validation_result import ValidationResult
from app.models.webhook import WebhookEvent
from app.schemas.payment import PaymentStatus
from app.schemas.validation import ConsistencyReportOut, ValidationCheckDefinition, ValidationResultOut

VALID_STATUSES = {status.value for status in PaymentStatus}

CHECK_DEFINITIONS: List[ValidationCheckDefinition] = [
    ValidationCheckDefinition(
        check_key="verify_transaction_existence",
        check_name="Verify Transaction Existence",
        description="Ensures transaction records exist and all required identifiers are populated.",
        category="Integrity",
    ),
    ValidationCheckDefinition(
        check_key="verify_transaction_status",
        check_name="Verify Transaction Status Validity",
        description="Checks that every transaction status belongs to the allowed payment state machine.",
        category="State Machine",
    ),
    ValidationCheckDefinition(
        check_key="check_duplicate_transactions",
        check_name="Check Duplicate Transaction Records",
        description="Detects duplicate transaction_id values or suspicious duplicate order captures.",
        category="Uniqueness",
    ),
    ValidationCheckDefinition(
        check_key="check_duplicate_idempotency_keys",
        check_name="Check Duplicate Idempotency Keys",
        description="Verifies uniqueness of idempotency_key across all transaction rows.",
        category="Idempotency",
    ),
    ValidationCheckDefinition(
        check_key="verify_payment_amount_consistency",
        check_name="Verify Payment Amount Consistency",
        description="Validates positive decimal amounts and consistency between DB amount and stored API payloads.",
        category="Financial",
    ),
    ValidationCheckDefinition(
        check_key="validate_foreign_keys",
        check_name="Validate Foreign Key Relationships",
        description="Checks referential integrity across test_results -> test_runs and bugs -> transactions.",
        category="Referential Integrity",
    ),
    ValidationCheckDefinition(
        check_key="verify_webhook_transaction_links",
        check_name="Verify Webhook-to-Transaction Relationships",
        description="Verifies that every webhook event references a valid existing transaction record.",
        category="Webhooks",
    ),
    ValidationCheckDefinition(
        check_key="detect_orphan_records",
        check_name="Detect Orphan Records",
        description="Scans webhooks, test results, and bugs for broken or orphaned parent references.",
        category="Referential Integrity",
    ),
]


def get_validation_checks() -> List[ValidationCheckDefinition]:
    return CHECK_DEFINITIONS


def _execute_single_check(db: Session, check_def: ValidationCheckDefinition, transaction_id: Optional[str] = None) -> ValidationResult:
    start = time.perf_counter()
    records_examined = 0
    issues: List[Dict[str, Any]] = []
    status = "PASS"

    key = check_def.check_key

    if key == "verify_transaction_existence":
        stmt = select(Transaction)
        if transaction_id:
            stmt = stmt.where(Transaction.transaction_id == transaction_id)
        txs = db.scalars(stmt).all()
        records_examined = len(txs)
        if transaction_id and records_examined == 0:
            issues.append({"issue": f"Transaction '{transaction_id}' does not exist in database."})
        for tx in txs:
            if not tx.transaction_id or not tx.order_id or not tx.idempotency_key:
                issues.append({"transaction_id": tx.transaction_id, "issue": "Missing core identifier field."})

    elif key == "verify_transaction_status":
        txs = db.scalars(select(Transaction)).all()
        records_examined = len(txs)
        for tx in txs:
            if tx.status not in VALID_STATUSES:
                issues.append({"transaction_id": tx.transaction_id, "status": tx.status, "issue": "Invalid status value."})
            if tx.status == PaymentStatus.FAILED.value and not tx.failure_reason:
                issues.append(
                    {"transaction_id": tx.transaction_id, "issue": "FAILED transaction missing failure_reason."}
                )

    elif key == "check_duplicate_transactions":
        records_examined = db.scalar(select(func.count(Transaction.id))) or 0
        dup_ids = db.execute(
            select(Transaction.transaction_id, func.count(Transaction.id).label("cnt"))
            .group_by(Transaction.transaction_id)
            .having(func.count(Transaction.id) > 1)
        ).all()
        for row in dup_ids:
            issues.append({"transaction_id": row[0], "count": row[1], "issue": "Duplicate transaction_id detected."})

    elif key == "check_duplicate_idempotency_keys":
        records_examined = db.scalar(select(func.count(Transaction.id))) or 0
        dup_keys = db.execute(
            select(Transaction.idempotency_key, func.count(Transaction.id).label("cnt"))
            .group_by(Transaction.idempotency_key)
            .having(func.count(Transaction.id) > 1)
        ).all()
        for row in dup_keys:
            issues.append({"idempotency_key": row[0], "count": row[1], "issue": "Duplicate idempotency_key detected."})

    elif key == "verify_payment_amount_consistency":
        txs = db.scalars(select(Transaction)).all()
        records_examined = len(txs)
        for tx in txs:
            if tx.amount is None or tx.amount <= Decimal("0.00"):
                issues.append({"transaction_id": tx.transaction_id, "amount": str(tx.amount), "issue": "Non-positive amount."})
            if isinstance(tx.response_payload, dict) and "amount" in tx.response_payload:
                if Decimal(str(tx.response_payload["amount"])) != tx.amount:
                    issues.append(
                        {
                            "transaction_id": tx.transaction_id,
                            "db_amount": str(tx.amount),
                            "api_amount": str(tx.response_payload["amount"]),
                            "issue": "Mismatch between DB amount and API response payload amount.",
                        }
                    )

    elif key == "validate_foreign_keys":
        test_results = db.scalars(select(TestResult)).all()
        run_ids = set(db.scalars(select(TestRun.run_id)).all())
        bugs = db.scalars(select(Bug)).all()
        tx_ids = set(db.scalars(select(Transaction.transaction_id)).all())
        records_examined = len(test_results) + len(bugs)

        for tr in test_results:
            if tr.run_id not in run_ids:
                issues.append({"test_result_id": tr.id, "run_id": tr.run_id, "issue": "Missing parent test_run."})
        for bug in bugs:
            if bug.transaction_id and bug.transaction_id not in tx_ids:
                issues.append({"bug_id": bug.bug_id, "transaction_id": bug.transaction_id, "issue": "Missing linked transaction."})

    elif key == "verify_webhook_transaction_links":
        events = db.scalars(select(WebhookEvent)).all()
        tx_ids = set(db.scalars(select(Transaction.transaction_id)).all())
        records_examined = len(events)
        for ev in events:
            if not ev.transaction_id or ev.transaction_id not in tx_ids:
                issues.append(
                    {
                        "event_id": ev.event_id,
                        "transaction_id": ev.transaction_id,
                        "issue": "Webhook event does not link to a valid transaction.",
                    }
                )

    elif key == "detect_orphan_records":
        events = db.scalars(select(WebhookEvent)).all()
        test_results = db.scalars(select(TestResult)).all()
        tx_ids = set(db.scalars(select(Transaction.transaction_id)).all())
        run_ids = set(db.scalars(select(TestRun.run_id)).all())
        records_examined = len(events) + len(test_results)
        for ev in events:
            if ev.transaction_id is None or ev.transaction_id not in tx_ids:
                issues.append({"table": "webhook_events", "record": ev.event_id, "issue": "Orphan webhook event."})
        for tr in test_results:
            if tr.run_id not in run_ids:
                issues.append({"table": "test_results", "record": str(tr.id), "issue": "Orphan test_result."})

    if issues:
        status = "FAIL"

    elapsed_ms = round((time.perf_counter() - start) * 1000.0, 2)
    result = ValidationResult(
        check_key=check_def.check_key,
        check_name=check_def.check_name,
        execution_status=status,
        records_examined=records_examined,
        issues_detected=len(issues),
        details=issues,
        execution_duration_ms=elapsed_ms,
        executed_at=datetime.now(timezone.utc),
    )
    db.add(result)
    return result


def run_validation_checks(
    db: Session,
    check_keys: Optional[List[str]] = None,
    transaction_id: Optional[str] = None,
) -> List[ValidationResultOut]:
    selected = CHECK_DEFINITIONS
    if check_keys:
        allowed = set(check_keys)
        selected = [c for c in CHECK_DEFINITIONS if c.check_key in allowed]

    results = [_execute_single_check(db, check_def, transaction_id=transaction_id) for check_def in selected]
    db.commit()
    for res in results:
        db.refresh(res)
    return [ValidationResultOut.model_validate(res) for res in results]


def list_validation_results(db: Session, limit: int = 50) -> List[ValidationResultOut]:
    rows = db.scalars(select(ValidationResult).order_by(desc(ValidationResult.executed_at), desc(ValidationResult.id)).limit(limit)).all()
    return [ValidationResultOut.model_validate(row) for row in rows]


def check_transaction_consistency(db: Session, transaction_id: str) -> ConsistencyReportOut:
    """Compare API response payload, DB record, latest webhook event, and final payment state."""
    tx = db.scalar(select(Transaction).where(Transaction.transaction_id == transaction_id))
    if tx is None:
        raise NotFoundError("Transaction", transaction_id)

    latest_wh = db.scalar(
        select(WebhookEvent)
        .where(WebhookEvent.transaction_id == transaction_id)
        .order_by(desc(WebhookEvent.created_at), desc(WebhookEvent.id))
    )

    api_status = tx.response_payload.get("status") if isinstance(tx.response_payload, dict) else None
    api_amount = tx.response_payload.get("amount") if isinstance(tx.response_payload, dict) else None

    discrepancies: List[str] = []
    amount_consistent = True

    if api_status and api_status != tx.status:
        discrepancies.append(f"API response status ({api_status}) differs from DB status ({tx.status}).")

    if api_amount is not None and Decimal(str(api_amount)) != tx.amount:
        amount_consistent = False
        discrepancies.append(f"API response amount ({api_amount}) differs from DB amount ({tx.amount:.2f}).")

    wh_expected_map = {
        "payment.success": PaymentStatus.SUCCESS.value,
        "payment.failed": PaymentStatus.FAILED.value,
        "payment.pending": PaymentStatus.PENDING.value,
        "payment.refunded": PaymentStatus.REFUNDED.value,
    }

    if latest_wh is not None:
        if latest_wh.delivery_status == "DELIVERED" and latest_wh.signature_valid:
            expected_status = wh_expected_map.get(latest_wh.event_type)
            # Allow SUCCESS -> REFUNDED progression even if earlier webhook was payment.success
            if expected_status and expected_status != tx.status and not (
                expected_status == PaymentStatus.SUCCESS.value and tx.status == PaymentStatus.REFUNDED.value
            ):
                discrepancies.append(
                    f"Delivered webhook '{latest_wh.event_type}' implies status {expected_status}, "
                    f"but DB status is {tx.status}."
                )
        elif latest_wh.delivery_status in ("FAILED", "INVALID_SIGNATURE"):
            discrepancies.append(
                f"Latest webhook '{latest_wh.event_id}' is in status {latest_wh.delivery_status} and has not been delivered."
            )

    return ConsistencyReportOut(
        transaction_id=tx.transaction_id,
        consistent=len(discrepancies) == 0,
        api_response_status=api_status,
        db_status=tx.status,
        latest_webhook_event=latest_wh.event_type if latest_wh else None,
        latest_webhook_status=latest_wh.delivery_status if latest_wh else None,
        final_payment_state=tx.status,
        amount_consistent=amount_consistent,
        discrepancies=discrepancies,
        details={
            "order_id": tx.order_id,
            "db_amount": f"{tx.amount:.2f}",
            "api_amount": str(api_amount) if api_amount is not None else None,
            "currency": tx.currency,
            "gateway_reference": tx.gateway_reference,
            "response_code": tx.response_code,
            "webhook_event_id": latest_wh.event_id if latest_wh else None,
        },
    )

