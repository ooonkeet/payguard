"""Webhook Receiver, Verification, Simulation, and Retry REST Endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import PayGuardException
from app.database.session import get_db
from app.schemas.webhook import WebhookPayloadIn, WebhookSimulateRequest
from app.services import webhook_service

router = APIRouter(prefix="/api/v1/webhooks", tags=["Webhooks"])


@router.post("/payment")
async def receive_payment_webhook(
    request: Request,
    x_payguard_signature: Optional[str] = Header(default=None, alias="X-PayGuard-Signature"),
    x_simulate_failure: Optional[str] = Header(default=None, alias="X-Simulate-Delivery-Failure"),
    db: Session = Depends(get_db),
) -> JSONResponse:
    raw_body = await request.body()
    try:
        payload_data = WebhookPayloadIn.model_validate_json(raw_body)
    except ValidationError as exc:
        raise PayGuardException(
            message="Invalid webhook payload schema.",
            code="INVALID_WEBHOOK_PAYLOAD",
            status_code=422,
            details={"errors": exc.errors()},
        )

    sim_fail = (x_simulate_failure or "").lower() in ("1", "true", "yes")
    event_out, http_code = webhook_service.process_incoming_webhook(
        db=db,
        raw_body=raw_body,
        provided_signature=x_payguard_signature,
        payload_data=payload_data,
        simulate_delivery_failure=sim_fail,
    )

    if http_code == 401:
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": {
                    "code": "INVALID_WEBHOOK_SIGNATURE",
                    "message": "HMAC-SHA256 webhook signature verification failed.",
                    "details": {"event_id": event_out.event_id},
                },
                "data": event_out.model_dump(mode="json"),
            },
        )

    return JSONResponse(
        status_code=http_code,
        content={
            "success": True,
            "data": event_out.model_dump(mode="json"),
            "meta": {"deduplicated": event_out.deduplicated},
        },
    )


@router.post("/simulate")
def simulate_webhook(payload: WebhookSimulateRequest, db: Session = Depends(get_db)) -> JSONResponse:
    event_out, http_code = webhook_service.simulate_webhook_delivery(db, payload)
    if http_code == 401:
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": {
                    "code": "INVALID_WEBHOOK_SIGNATURE",
                    "message": "Simulated invalid HMAC-SHA256 signature was properly rejected.",
                    "details": {"event_id": event_out.event_id},
                },
                "data": event_out.model_dump(mode="json"),
            },
        )
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": event_out.model_dump(mode="json"),
            "meta": {"deduplicated": event_out.deduplicated},
        },
    )


@router.get("/events")
def list_webhook_events(
    delivery_status: Optional[str] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    transaction_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    events = webhook_service.list_webhook_events(
        db=db,
        delivery_status=delivery_status,
        event_type=event_type,
        transaction_id=transaction_id,
        limit=limit,
    )
    return {"success": True, "data": [e.model_dump(mode="json") for e in events]}


@router.get("/events/{event_id}")
def get_webhook_event(event_id: str, db: Session = Depends(get_db)) -> dict:
    event = webhook_service.get_webhook_event(db, event_id)
    return {"success": True, "data": event.model_dump(mode="json")}


@router.post("/events/{event_id}/retry")
def retry_webhook_event(event_id: str, db: Session = Depends(get_db)) -> dict:
    event = webhook_service.retry_webhook_event(db, event_id)
    return {"success": True, "data": event.model_dump(mode="json")}

