"""Payment Simulation & Transaction Management REST Endpoints."""

import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.payment import (
    PaymentCreateRequest,
    PaymentStatusOut,
    ReconcileRequest,
    RefundRequest,
)
from app.services import payment_service

router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: PaymentCreateRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    fast_mode = os.environ.get("PAYGUARD_FAST_SIMULATION") == "1"
    tx, is_replay = payment_service.create_payment(db, payload, simulate_delay=not fast_mode)
    if is_replay:
        response.status_code = status.HTTP_200_OK
        response.headers["X-Idempotent-Replay"] = "true"
    return {
        "success": True,
        "data": tx.model_dump(mode="json"),
        "meta": {"idempotent_replay": is_replay},
    }


@router.get("")
def list_payments(
    search: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    payment_method: Optional[str] = Query(default=None),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
    sort_by: str = Query(default="created_at", pattern="^(created_at|amount)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    result = payment_service.list_transactions(
        db=db,
        search=search,
        status_filter=status_filter,
        payment_method=payment_method,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    return {
        "success": True,
        "data": [item.model_dump(mode="json") for item in result["items"]],
        "pagination": result["pagination"],
    }


@router.get("/{transaction_id}")
def get_payment(transaction_id: str, db: Session = Depends(get_db)) -> dict:
    detail = payment_service.get_transaction_detail(db, transaction_id)
    return {"success": True, "data": detail}


@router.get("/{transaction_id}/status")
def get_payment_status(transaction_id: str, db: Session = Depends(get_db)) -> dict:
    tx = payment_service.get_transaction_status(db, transaction_id)
    out = PaymentStatusOut(
        transaction_id=tx.transaction_id,
        order_id=tx.order_id,
        status=tx.status,
        response_code=tx.response_code,
        failure_reason=tx.failure_reason,
        gateway_reference=tx.gateway_reference,
        updated_at=tx.updated_at,
    )
    return {"success": True, "data": out.model_dump(mode="json")}


@router.post("/{transaction_id}/refund")
def refund_payment(transaction_id: str, payload: RefundRequest, db: Session = Depends(get_db)) -> dict:
    tx = payment_service.refund_transaction(db, transaction_id, payload)
    return {"success": True, "data": tx.model_dump(mode="json")}


@router.post("/{transaction_id}/reconcile")
def reconcile_payment(transaction_id: str, payload: ReconcileRequest, db: Session = Depends(get_db)) -> dict:
    tx = payment_service.reconcile_transaction(db, transaction_id, payload)
    return {"success": True, "data": tx.model_dump(mode="json")}

