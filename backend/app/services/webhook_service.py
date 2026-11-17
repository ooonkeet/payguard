"""Webhook Receiver, HMAC-SHA256 Verification, Deduplication, and Retry Simulation Service."""

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, PayGuardException
from app.core.logging import logger
from app.core.security import canonical_payload_bytes, compute_webhook_signature, verify_webhook_signature
from app.models.transaction import Transaction
from app.models.webhook import WebhookEvent
from app.schemas.payment import PaymentStatus
from app.schemas.webhook import WebhookEventOut, WebhookEventType, WebhookPayloadIn, WebhookSimulateRequest
from app.services.payment_state_machine import can_transition

EVENT_TYPE_TO_STATUS = {
    WebhookEventType.PAYMENT_SUCCESS.value: PaymentStatus.SUCCESS.value,
    WebhookEventType.PAYMENT_FAILED.value: PaymentStatus.FAILED.value,
    WebhookEventType.PAYMENT_PENDING.value: PaymentStatus.PENDING.value,
    WebhookEventType.PAYMENT_REFUNDED.value: PaymentStatus.REFUNDED.value,
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _apply_webhook_to_transaction(
    db: Session, tx: Optional[Transaction], event_type: str, failure_reason: Optional[str], logs: List[Dict[str, Any]]
) -> None:
    if tx is None:
        logs.append(
            {
                "timestamp": _iso_now(),
                "level": "WARNING",
                "message": "No matching transaction found in database; webhook recorded as unlinked.",
            }
        )
        return

    target_status = EVENT_TYPE_TO_STATUS.get(event_type)
    if not target_status:
        return

    if tx.status == target_status:
        logs.append(
            {
                "timestamp": _iso_now(),
                "level": "INFO",
                "message": f"Transaction {tx.transaction_id} is already in status {target_status}; no state mutation needed.",
            }
        )
        return

    if can_transition(tx.status, target_status):
        previous_status = tx.status
        tx.status = target_status
        if target_status == PaymentStatus.SUCCESS.value:
            tx.response_code = "PG_200_WEBHOOK_CONFIRMED"
            tx.failure_reason = None
        elif target_status == PaymentStatus.FAILED.value:
            tx.response_code = "PG_422_WEBHOOK_FAILED"
            tx.failure_reason = failure_reason or "Marked failed via payment webhook."
        elif target_status == PaymentStatus.REFUNDED.value:
            tx.response_code = "PG_200_WEBHOOK_REFUNDED"

        tx.updated_at = datetime.now(timezone.utc)
        timeline = list(tx.timeline or [])
        timeline.append(
            {
                "stage": "WEBHOOK_PROCESSED",
                "status": tx.status,
                "timestamp": _iso_now(),
                "detail": f"Webhook {event_type} transitioned transaction {previous_status} -> {target_status}.",
                "elapsed_ms": tx.processing_duration_ms,
            }
        )
        tx.timeline = timeline

        resp = dict(tx.response_payload or {})
        resp["status"] = tx.status
        resp["response_code"] = tx.response_code
        resp["failure_reason"] = tx.failure_reason
        tx.response_payload = resp

        logs.append(
            {
                "timestamp": _iso_now(),
                "level": "INFO",
                "message": f"Transitioned transaction {tx.transaction_id}: {previous_status} -> {target_status}.",
            }
        )
    else:
        logs.append(
            {
                "timestamp": _iso_now(),
                "level": "WARNING",
                "message": (
                    f"Ignored invalid state transition {tx.status} -> {target_status} "
                    f"for transaction {tx.transaction_id}."
                ),
            }
        )


def process_incoming_webhook(
    db: Session,
    raw_body: bytes,
    provided_signature: Optional[str],
    payload_data: WebhookPayloadIn,
    simulate_delivery_failure: bool = False,
) -> Tuple[WebhookEventOut, int]:
    """
    Process a signed payment webhook.
    Returns (WebhookEventOut, http_status_code).
    - Invalid signature -> persists failed audit event and returns 401.
    - Duplicate event_id -> deduplicates without reprocessing transaction and returns 200 with deduplicated=True.
    - Valid new event -> verifies signature, updates transaction state safely, persists DELIVERED (or FAILED if simulated).
    """
    signature_valid = verify_webhook_signature(raw_body, provided_signature)
    payload_dict = payload_data.model_dump(mode="json")

    # Check duplicate event_id first (database-level deduplication)
    existing = db.scalar(select(WebhookEvent).where(WebhookEvent.event_id == payload_data.event_id))
    if existing is not None:
        existing.duplicate_attempts += 1
        existing.attempt_count += 1
        logs = list(existing.processing_logs or [])
        logs.append(
            {
                "timestamp": _iso_now(),
                "level": "WARNING",
                "message": (
                    f"Duplicate webhook event '{payload_data.event_id}' ignored "
                    f"(duplicate attempt #{existing.duplicate_attempts}). Transaction was NOT processed twice."
                ),
            }
        )
        existing.processing_logs = logs
        db.commit()
        db.refresh(existing)
        out = WebhookEventOut.model_validate(existing)
        out.deduplicated = True
        return out, 200

    tx = db.scalar(select(Transaction).where(Transaction.transaction_id == payload_data.transaction_id))
    linked_tx_id = tx.transaction_id if tx is not None else None
    logs: List[Dict[str, Any]] = [
        {
            "timestamp": _iso_now(),
            "level": "INFO",
            "message": f"Received webhook event {payload_data.event_id} ({payload_data.event_type.value}).",
        }
    ]

    if not signature_valid:
        logs.append(
            {
                "timestamp": _iso_now(),
                "level": "ERROR",
                "message": "HMAC-SHA256 signature verification failed. Webhook rejected without mutating transaction.",
            }
        )
        event = WebhookEvent(
            event_id=payload_data.event_id,
            transaction_id=linked_tx_id,
            event_type=payload_data.event_type.value,
            payload=payload_dict,
            signature_valid=False,
            delivery_status="INVALID_SIGNATURE",
            attempt_count=1,
            duplicate_attempts=0,
            processing_logs=logs,
            is_seeded=False,
            created_at=datetime.now(timezone.utc),
            delivered_at=None,
        )
        try:
            db.add(event)
            db.commit()
            db.refresh(event)
        except IntegrityError:
            db.rollback()
            raise PayGuardException("Duplicate webhook event conflict.", code="WEBHOOK_CONFLICT", status_code=409)

        return WebhookEventOut.model_validate(event), 401

    logs.append(
        {
            "timestamp": _iso_now(),
            "level": "INFO",
            "message": "HMAC-SHA256 signature verified successfully.",
        }
    )

    if simulate_delivery_failure:
        logs.append(
            {
                "timestamp": _iso_now(),
                "level": "ERROR",
                "message": "Simulated downstream webhook consumer timeout (HTTP 500). Queued for retry.",
            }
        )
        delivery_status = "FAILED"
        delivered_at = None
    else:
        _apply_webhook_to_transaction(db, tx, payload_data.event_type.value, payload_data.failure_reason, logs)
        delivery_status = "DELIVERED"
        delivered_at = datetime.now(timezone.utc)

    event = WebhookEvent(
        event_id=payload_data.event_id,
        transaction_id=linked_tx_id,
        event_type=payload_data.event_type.value,
        payload=payload_dict,
        signature_valid=True,
        delivery_status=delivery_status,
        attempt_count=1,
        duplicate_attempts=0,
        processing_logs=logs,
        is_seeded=False,
        created_at=datetime.now(timezone.utc),
        delivered_at=delivered_at,
    )

    try:
        db.add(event)
        db.commit()
        db.refresh(event)
    except IntegrityError:
        db.rollback()
        existing_race = db.scalar(select(WebhookEvent).where(WebhookEvent.event_id == payload_data.event_id))
        if existing_race is not None:
            existing_race.duplicate_attempts += 1
            existing_race.attempt_count += 1
            db.commit()
            db.refresh(existing_race)
            out = WebhookEventOut.model_validate(existing_race)
            out.deduplicated = True
            return out, 200
        raise

    logger.info(
        "Webhook event processed",
        extra={
            "extra_data": {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "delivery_status": event.delivery_status,
            }
        },
    )
    return WebhookEventOut.model_validate(event), 200


def simulate_webhook_delivery(db: Session, req: WebhookSimulateRequest) -> Tuple[WebhookEventOut, int]:
    """
    Server-side webhook simulator so the frontend NEVER needs access to WEBHOOK_SECRET.
    """
    if req.delay_ms > 0:
        time.sleep(min(req.delay_ms, 3000) / 1000.0)

    tx = db.scalar(select(Transaction).where(Transaction.transaction_id == req.transaction_id))
    if tx is None:
        raise NotFoundError("Transaction", req.transaction_id)

    event_id = req.event_id
    if req.simulate_duplicate and not event_id:
        latest_wh = db.scalar(
            select(WebhookEvent)
            .where(WebhookEvent.transaction_id == req.transaction_id)
            .order_by(desc(WebhookEvent.created_at))
        )
        if latest_wh is not None:
            event_id = latest_wh.event_id

    if not event_id:
        event_id = f"EVT-{uuid.uuid4().hex[:12].upper()}"

    payload_obj = WebhookPayloadIn(
        event_id=event_id,
        event_type=req.event_type,
        transaction_id=tx.transaction_id,
        gateway_reference=tx.gateway_reference,
        amount=f"{tx.amount:.2f}",
        currency=tx.currency,
        failure_reason="Simulated webhook failure notification" if req.event_type == WebhookEventType.PAYMENT_FAILED else None,
        timestamp=_iso_now(),
    )
    raw_body = canonical_payload_bytes(payload_obj.model_dump(mode="json"))

    if req.simulate_invalid_signature:
        signature = "sha256=000000000000000000000000000000000000000000000000000000000000dead"
    else:
        signature = f"sha256={compute_webhook_signature(raw_body)}"

    return process_incoming_webhook(
        db=db,
        raw_body=raw_body,
        provided_signature=signature,
        payload_data=payload_obj,
        simulate_delivery_failure=req.simulate_delivery_failure,
    )


def retry_webhook_event(db: Session, event_id: str) -> WebhookEventOut:
    event = db.scalar(select(WebhookEvent).where(WebhookEvent.event_id == event_id))
    if event is None:
        raise NotFoundError("WebhookEvent", event_id)

    event.attempt_count += 1
    logs = list(event.processing_logs or [])

    if not event.signature_valid:
        logs.append(
            {
                "timestamp": _iso_now(),
                "level": "ERROR",
                "message": f"Retry attempt #{event.attempt_count} blocked: original event failed HMAC signature verification.",
            }
        )
        event.processing_logs = logs
        db.commit()
        db.refresh(event)
        raise PayGuardException(
            message="Cannot deliver a webhook with an invalid HMAC signature.",
            code="INVALID_WEBHOOK_SIGNATURE",
            status_code=400,
        )

    if event.delivery_status == "DELIVERED":
        logs.append(
            {
                "timestamp": _iso_now(),
                "level": "INFO",
                "message": f"Retry attempt #{event.attempt_count} acknowledged: event was already DELIVERED (idempotent no-op).",
            }
        )
        event.processing_logs = logs
        db.commit()
        db.refresh(event)
        out = WebhookEventOut.model_validate(event)
        out.deduplicated = True
        return out

    tx = (
        db.scalar(select(Transaction).where(Transaction.transaction_id == event.transaction_id))
        if event.transaction_id
        else None
    )
    failure_reason = event.payload.get("failure_reason") if isinstance(event.payload, dict) else None
    _apply_webhook_to_transaction(db, tx, event.event_type, failure_reason, logs)

    event.delivery_status = "DELIVERED"
    event.delivered_at = datetime.now(timezone.utc)
    logs.append(
        {
            "timestamp": _iso_now(),
            "level": "INFO",
            "message": f"Retry attempt #{event.attempt_count} succeeded; webhook marked DELIVERED.",
        }
    )
    event.processing_logs = logs
    db.commit()
    db.refresh(event)
    return WebhookEventOut.model_validate(event)


def list_webhook_events(
    db: Session,
    delivery_status: Optional[str] = None,
    event_type: Optional[str] = None,
    transaction_id: Optional[str] = None,
    limit: int = 100,
) -> List[WebhookEventOut]:
    stmt = select(WebhookEvent)
    if delivery_status and delivery_status != "ALL":
        stmt = stmt.where(WebhookEvent.delivery_status == delivery_status)
    if event_type and event_type != "ALL":
        stmt = stmt.where(WebhookEvent.event_type == event_type)
    if transaction_id:
        stmt = stmt.where(WebhookEvent.transaction_id == transaction_id)
    stmt = stmt.order_by(desc(WebhookEvent.created_at), desc(WebhookEvent.id)).limit(limit)
    rows = db.scalars(stmt).all()
    return [WebhookEventOut.model_validate(row) for row in rows]


def get_webhook_event(db: Session, event_id: str) -> WebhookEventOut:
    event = db.scalar(select(WebhookEvent).where(WebhookEvent.event_id == event_id))
    if event is None:
        raise NotFoundError("WebhookEvent", event_id)
    return WebhookEventOut.model_validate(event)

