"""Payment Simulation Engine, Idempotency Enforcement, and Transaction Management Service."""

import math
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import IdempotencyConflictError, NotFoundError, PayGuardException
from app.core.logging import logger
from app.core.security import compute_payload_hash
from app.models.bug import Bug
from app.models.test_run import TestResult
from app.models.transaction import Transaction
from app.models.webhook import WebhookEvent
from app.schemas.payment import (
    PaymentCreateRequest,
    PaymentScenario,
    PaymentStatus,
    ReconcileRequest,
    RefundRequest,
    TransactionOut,
)
from app.services.payment_state_machine import validate_transition

SCENARIO_OUTCOMES: Dict[str, Dict[str, Any]] = {
    PaymentScenario.SUCCESSFUL_PAYMENT.value: {
        "final_status": PaymentStatus.SUCCESS.value,
        "response_code": "PG_200_APPROVED",
        "failure_reason": None,
        "sim_delay_ms": 180,
        "gateway_message": "Payment authorized and captured by sandbox acquirer.",
    },
    PaymentScenario.INSUFFICIENT_BALANCE.value: {
        "final_status": PaymentStatus.FAILED.value,
        "response_code": "PG_402_INSUFFICIENT_FUNDS",
        "failure_reason": "Issuer declined transaction: insufficient available balance.",
        "sim_delay_ms": 160,
        "gateway_message": "Issuer returned decline code 51 (Insufficient Funds).",
    },
    PaymentScenario.INVALID_PAYMENT_DETAILS.value: {
        "final_status": PaymentStatus.FAILED.value,
        "response_code": "PG_400_INVALID_INSTRUMENT",
        "failure_reason": "Payment instrument validation failed (synthetic VPA/card token rejected).",
        "sim_delay_ms": 110,
        "gateway_message": "Gateway rejected synthetic payment instrument checksum.",
    },
    PaymentScenario.GATEWAY_TIMEOUT.value: {
        "final_status": PaymentStatus.PENDING.value,
        "response_code": "PG_504_GATEWAY_TIMEOUT",
        "failure_reason": (
            "Upstream gateway timed out before confirmation. Transaction left in PENDING state "
            "for reconciliation (timeout does not guarantee failure)."
        ),
        "sim_delay_ms": 380,
        "gateway_message": "Upstream read timeout after 30000ms (simulated); outcome uncertain.",
    },
    PaymentScenario.GATEWAY_UNAVAILABLE.value: {
        "final_status": PaymentStatus.FAILED.value,
        "response_code": "PG_503_GATEWAY_UNAVAILABLE",
        "failure_reason": "Acquiring gateway temporarily unavailable (HTTP 503 circuit open).",
        "sim_delay_ms": 140,
        "gateway_message": "Upstream gateway returned 503 Service Unavailable.",
    },
    PaymentScenario.PENDING_TRANSACTION.value: {
        "final_status": PaymentStatus.PENDING.value,
        "response_code": "PG_202_AWAITING_CONFIRMATION",
        "failure_reason": None,
        "sim_delay_ms": 200,
        "gateway_message": "Awaiting asynchronous issuer/UPI collect confirmation.",
    },
    PaymentScenario.DELAYED_WEBHOOK.value: {
        "final_status": PaymentStatus.PENDING.value,
        "response_code": "PG_202_WEBHOOK_DELAYED",
        "failure_reason": None,
        "sim_delay_ms": 210,
        "gateway_message": "Payment accepted; final settlement confirmation awaiting delayed webhook.",
    },
    PaymentScenario.DUPLICATE_PAYMENT_REQUEST.value: {
        "final_status": PaymentStatus.SUCCESS.value,
        "response_code": "PG_200_APPROVED",
        "failure_reason": None,
        "sim_delay_ms": 150,
        "gateway_message": "Primary request approved; subsequent replays with same idempotency key return cached result.",
    },
    PaymentScenario.PAYMENT_FAILURE.value: {
        "final_status": PaymentStatus.FAILED.value,
        "response_code": "PG_422_PAYMENT_FAILED",
        "failure_reason": "Transaction failed during acquirer risk and authorization check.",
        "sim_delay_ms": 170,
        "gateway_message": "Acquirer returned generic authorization failure.",
    },
    PaymentScenario.PROCESSING_ERROR.value: {
        "final_status": PaymentStatus.FAILED.value,
        "response_code": "PG_500_PROCESSING_ERROR",
        "failure_reason": "Simulated processor internal routing exception during settlement.",
        "sim_delay_ms": 190,
        "gateway_message": "Downstream switch returned ISO-8583 processing error 96.",
    },
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_payment_fingerprint(payload: PaymentCreateRequest) -> Dict[str, Any]:
    """Fields that define payload equivalence for idempotency conflict detection."""
    return {
        "order_id": payload.order_id,
        "amount": f"{payload.amount:.2f}",
        "currency": payload.currency.value,
        "payment_method": payload.payment_method.value,
        "customer_reference": payload.customer_reference or "",
        "scenario": payload.scenario.value,
    }


def _to_transaction_out(tx: Transaction, idempotent_replay: bool = False) -> TransactionOut:
    data = TransactionOut.model_validate(tx)
    data.idempotent_replay = idempotent_replay
    return data


def _wait_for_settled_transaction(
    db: Session,
    tx: Transaction,
    max_wait_seconds: float = 3.0,
    poll_interval: float = 0.04,
) -> Transaction:
    """
    If a concurrent primary request is still transitioning CREATED -> PROCESSING -> terminal state,
    wait briefly and refresh from DB so idempotent replays return the settled state instead of
    exposing an intermediate PROCESSING snapshot.
    """
    deadline = time.perf_counter() + max_wait_seconds
    current = tx
    while current.status in (PaymentStatus.CREATED.value, PaymentStatus.PROCESSING.value):
        if time.perf_counter() >= deadline:
            break
        time.sleep(poll_interval)
        db.expire_all()
        refreshed = db.scalar(select(Transaction).where(Transaction.id == current.id))
        if refreshed is None:
            break
        current = refreshed
    return current


def create_payment(
    db: Session,
    payload: PaymentCreateRequest,
    simulate_delay: bool = True,
) -> Tuple[TransactionOut, bool]:
    """
    Create and process a simulated payment with strict idempotency & state transitions.
    Returns (TransactionOut, is_idempotent_replay).
    """
    started = time.perf_counter()
    fingerprint = _canonical_payment_fingerprint(payload)
    payload_hash = compute_payload_hash(fingerprint)

    # 1. Fast-path idempotency lookup
    existing = db.scalar(select(Transaction).where(Transaction.idempotency_key == payload.idempotency_key))
    if existing is not None:
        if existing.payload_hash != payload_hash:
            raise IdempotencyConflictError(
                idempotency_key=payload.idempotency_key,
                existing_transaction_id=existing.transaction_id,
            )
        settled = _wait_for_settled_transaction(db, existing)
        logger.info(
            "Idempotent replay served from persisted transaction",
            extra={"extra_data": {"transaction_id": settled.transaction_id, "idempotency_key": payload.idempotency_key}},
        )
        return _to_transaction_out(settled, idempotent_replay=True), True

    # 2. Construct initial CREATED transaction record and persist immediately to claim idempotency lock
    tx_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"
    gw_ref = f"GW-{uuid.uuid4().hex[:10].upper()}"
    now = datetime.now(timezone.utc)
    request_dict = {
        "order_id": payload.order_id,
        "amount": f"{payload.amount:.2f}",
        "currency": payload.currency.value,
        "payment_method": payload.payment_method.value,
        "customer_reference": payload.customer_reference,
        "idempotency_key": payload.idempotency_key,
        "scenario": payload.scenario.value,
        "metadata": payload.metadata or {},
    }

    timeline: List[Dict[str, Any]] = [
        {
            "stage": "REQUEST_RECEIVED",
            "status": PaymentStatus.CREATED.value,
            "timestamp": _iso_now(),
            "detail": f"Accepted payment request for order {payload.order_id} ({payload.currency.value} {payload.amount:.2f}).",
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }
    ]

    tx = Transaction(
        transaction_id=tx_id,
        order_id=payload.order_id,
        amount=payload.amount,
        currency=payload.currency.value,
        payment_method=payload.payment_method.value,
        customer_reference=payload.customer_reference,
        scenario=payload.scenario.value,
        status=PaymentStatus.CREATED.value,
        idempotency_key=payload.idempotency_key,
        payload_hash=payload_hash,
        gateway_reference=gw_ref,
        response_code="PG_100_CREATED",
        failure_reason=None,
        processing_duration_ms=0,
        request_payload=request_dict,
        response_payload=None,
        timeline=timeline,
        is_seeded=False,
        created_at=now,
        updated_at=now,
    )

    try:
        db.add(tx)
        db.commit()
        db.refresh(tx)
    except IntegrityError:
        # Concurrent request won the unique idempotency_key constraint
        db.rollback()
        concurrent_existing = db.scalar(
            select(Transaction).where(Transaction.idempotency_key == payload.idempotency_key)
        )
        if concurrent_existing is None:
            raise
        if concurrent_existing.payload_hash != payload_hash:
            raise IdempotencyConflictError(
                idempotency_key=payload.idempotency_key,
                existing_transaction_id=concurrent_existing.transaction_id,
            )
        settled = _wait_for_settled_transaction(db, concurrent_existing)
        return _to_transaction_out(settled, idempotent_replay=True), True

    # 3. Validate & transition CREATED -> PROCESSING
    timeline.append(
        {
            "stage": "VALIDATING",
            "status": PaymentStatus.CREATED.value,
            "timestamp": _iso_now(),
            "detail": "Validated schema, decimal precision, idempotency lock, and payment instrument.",
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }
    )

    validate_transition(tx.status, PaymentStatus.PROCESSING.value)
    tx.status = PaymentStatus.PROCESSING.value
    timeline.append(
        {
            "stage": "PROCESSING",
            "status": PaymentStatus.PROCESSING.value,
            "timestamp": _iso_now(),
            "detail": f"Dispatched to simulated {payload.payment_method.value} gateway switch ({gw_ref}).",
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }
    )
    tx.timeline = list(timeline)
    db.commit()

    # 4. Execute payment scenario
    outcome = SCENARIO_OUTCOMES[payload.scenario.value]
    if simulate_delay:
        time.sleep(min(outcome["sim_delay_ms"], 400) / 1000.0)

    final_status = outcome["final_status"]
    timeline.append(
        {
            "stage": "GATEWAY_RESPONSE",
            "status": final_status,
            "timestamp": _iso_now(),
            "detail": outcome["gateway_message"],
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }
    )

    # 5. Enforce state machine transition PROCESSING -> final_status
    validate_transition(tx.status, final_status)
    elapsed_ms = max(int((time.perf_counter() - started) * 1000), outcome["sim_delay_ms"] // 2)

    tx.status = final_status
    tx.response_code = outcome["response_code"]
    tx.failure_reason = outcome["failure_reason"]
    tx.processing_duration_ms = elapsed_ms
    tx.updated_at = datetime.now(timezone.utc)

    timeline.append(
        {
            "stage": "TRANSACTION_UPDATED",
            "status": final_status,
            "timestamp": _iso_now(),
            "detail": f"Persisted status {final_status} with response code {tx.response_code}.",
            "elapsed_ms": elapsed_ms,
        }
    )
    timeline.append(
        {
            "stage": "COMPLETED",
            "status": final_status,
            "timestamp": _iso_now(),
            "detail": "Simulation lifecycle finalized and committed to database.",
            "elapsed_ms": elapsed_ms,
        }
    )

    response_payload = {
        "transaction_id": tx.transaction_id,
        "order_id": tx.order_id,
        "amount": f"{tx.amount:.2f}",
        "currency": tx.currency,
        "payment_method": tx.payment_method,
        "status": tx.status,
        "response_code": tx.response_code,
        "failure_reason": tx.failure_reason,
        "gateway_reference": tx.gateway_reference,
        "processing_duration_ms": tx.processing_duration_ms,
        "scenario": tx.scenario,
    }
    tx.response_payload = response_payload
    tx.timeline = list(timeline)
    db.commit()
    db.refresh(tx)

    logger.info(
        "Payment simulation processed",
        extra={
            "extra_data": {
                "transaction_id": tx.transaction_id,
                "status": tx.status,
                "scenario": tx.scenario,
                "duration_ms": tx.processing_duration_ms,
            }
        },
    )
    return _to_transaction_out(tx, idempotent_replay=False), False


def list_transactions(
    db: Session,
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    payment_method: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    stmt = select(Transaction)
    count_stmt = select(func.count(Transaction.id))

    filters = []
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                Transaction.transaction_id.ilike(pattern),
                Transaction.order_id.ilike(pattern),
                Transaction.idempotency_key.ilike(pattern),
            )
        )
    if status_filter and status_filter != "ALL":
        filters.append(Transaction.status == status_filter)
    if payment_method and payment_method != "ALL":
        filters.append(Transaction.payment_method == payment_method)
    if date_from:
        filters.append(Transaction.created_at >= date_from)
    if date_to:
        filters.append(Transaction.created_at <= date_to)

    for condition in filters:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = db.scalar(count_stmt) or 0

    sort_col = Transaction.amount if sort_by == "amount" else Transaction.created_at
    order_fn = asc if sort_order.lower() == "asc" else desc
    stmt = stmt.order_by(order_fn(sort_col), desc(Transaction.id))

    offset = (page - 1) * page_size
    rows = db.scalars(stmt.offset(offset).limit(page_size)).all()

    return {
        "items": [_to_transaction_out(row) for row in rows],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, math.ceil(total / page_size)),
        },
    }


def get_transaction_detail(db: Session, transaction_id: str) -> Dict[str, Any]:
    tx = db.scalar(select(Transaction).where(Transaction.transaction_id == transaction_id))
    if tx is None:
        raise NotFoundError("Transaction", transaction_id)

    webhooks = db.scalars(
        select(WebhookEvent)
        .where(WebhookEvent.transaction_id == transaction_id)
        .order_by(desc(WebhookEvent.created_at))
    ).all()

    bugs = db.scalars(
        select(Bug).where(Bug.transaction_id == transaction_id).order_by(desc(Bug.created_at))
    ).all()

    # Related automated tests mentioning payment / transaction scenario
    scenario_keyword = tx.scenario.split("_")[0] if tx.scenario else "payment"
    tests = db.scalars(
        select(TestResult)
        .where(
            or_(
                TestResult.test_name.ilike(f"%{scenario_keyword}%"),
                TestResult.test_name.ilike("%payment%"),
            )
        )
        .order_by(desc(TestResult.created_at))
        .limit(8)
    ).all()

    base = _to_transaction_out(tx).model_dump()
    base["request_payload"] = tx.request_payload
    base["response_payload"] = tx.response_payload
    base["webhooks"] = [
        {
            "event_id": wh.event_id,
            "event_type": wh.event_type,
            "delivery_status": wh.delivery_status,
            "signature_valid": wh.signature_valid,
            "attempt_count": wh.attempt_count,
            "duplicate_attempts": wh.duplicate_attempts,
            "created_at": wh.created_at.isoformat(),
            "delivered_at": wh.delivered_at.isoformat() if wh.delivered_at else None,
        }
        for wh in webhooks
    ]
    base["related_bugs"] = [
        {
            "bug_id": b.bug_id,
            "title": b.title,
            "severity": b.severity,
            "status": b.status,
            "created_at": b.created_at.isoformat(),
        }
        for b in bugs
    ]
    base["related_tests"] = [
        {
            "run_id": tr.run_id,
            "test_name": tr.test_name,
            "test_status": tr.test_status,
            "duration": tr.duration,
            "created_at": tr.created_at.isoformat(),
        }
        for tr in tests
    ]
    return base


def get_transaction_status(db: Session, transaction_id: str) -> Transaction:
    tx = db.scalar(select(Transaction).where(Transaction.transaction_id == transaction_id))
    if tx is None:
        raise NotFoundError("Transaction", transaction_id)
    return tx


def refund_transaction(db: Session, transaction_id: str, req: RefundRequest) -> TransactionOut:
    tx = db.scalar(select(Transaction).where(Transaction.transaction_id == transaction_id))
    if tx is None:
        raise NotFoundError("Transaction", transaction_id)

    validate_transition(tx.status, PaymentStatus.REFUNDED.value)
    tx.status = PaymentStatus.REFUNDED.value
    tx.response_code = "PG_200_REFUNDED"
    tx.updated_at = datetime.now(timezone.utc)

    timeline = list(tx.timeline or [])
    timeline.append(
        {
            "stage": "REFUNDED",
            "status": PaymentStatus.REFUNDED.value,
            "timestamp": _iso_now(),
            "detail": f"Refund completed: {req.reason}",
            "elapsed_ms": tx.processing_duration_ms,
        }
    )
    tx.timeline = timeline

    resp = dict(tx.response_payload or {})
    resp["status"] = tx.status
    resp["response_code"] = tx.response_code
    resp["refund_reason"] = req.reason
    tx.response_payload = resp

    db.commit()
    db.refresh(tx)
    return _to_transaction_out(tx)


def reconcile_transaction(db: Session, transaction_id: str, req: ReconcileRequest) -> TransactionOut:
    """Reconcile a PENDING (e.g., timed-out) transaction to SUCCESS or FAILED."""
    tx = db.scalar(select(Transaction).where(Transaction.transaction_id == transaction_id))
    if tx is None:
        raise NotFoundError("Transaction", transaction_id)

    if req.resolved_status not in (PaymentStatus.SUCCESS, PaymentStatus.FAILED):
        raise PayGuardException(
            message="Reconciliation target status must be SUCCESS or FAILED.",
            code="INVALID_RECONCILE_STATUS",
            status_code=422,
        )

    validate_transition(tx.status, req.resolved_status.value)
    tx.status = req.resolved_status.value
    if req.resolved_status == PaymentStatus.SUCCESS:
        tx.response_code = "PG_200_RECONCILED_SUCCESS"
        tx.failure_reason = None
    else:
        tx.response_code = "PG_422_RECONCILED_FAILED"
        tx.failure_reason = req.note or "Reconciled as failed after gateway status inquiry."
    tx.updated_at = datetime.now(timezone.utc)

    timeline = list(tx.timeline or [])
    timeline.append(
        {
            "stage": "RECONCILED",
            "status": tx.status,
            "timestamp": _iso_now(),
            "detail": f"Reconciliation resolved transaction to {tx.status}. {req.note or ''}".strip(),
            "elapsed_ms": tx.processing_duration_ms,
        }
    )
    tx.timeline = timeline

    resp = dict(tx.response_payload or {})
    resp["status"] = tx.status
    resp["response_code"] = tx.response_code
    resp["failure_reason"] = tx.failure_reason
    tx.response_payload = resp

    db.commit()
    db.refresh(tx)
    return _to_transaction_out(tx)

