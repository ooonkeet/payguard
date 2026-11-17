"""Pydantic schemas for Webhook Monitor & Delivery Simulation."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class WebhookEventType(str, Enum):
    PAYMENT_SUCCESS = "payment.success"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_PENDING = "payment.pending"
    PAYMENT_REFUNDED = "payment.refunded"


class WebhookPayloadIn(BaseModel):
    event_id: str = Field(..., min_length=3, max_length=64)
    event_type: WebhookEventType
    transaction_id: str = Field(..., min_length=3, max_length=64)
    gateway_reference: Optional[str] = None
    amount: Optional[str] = None
    currency: Optional[str] = None
    failure_reason: Optional[str] = None
    timestamp: Optional[str] = None


class WebhookSimulateRequest(BaseModel):
    transaction_id: str = Field(..., min_length=3, max_length=64)
    event_type: WebhookEventType
    event_id: Optional[str] = Field(default=None, max_length=64)
    simulate_invalid_signature: bool = False
    simulate_duplicate: bool = False
    simulate_delivery_failure: bool = False
    delay_ms: int = Field(default=0, ge=0, le=3000)


class WebhookEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: str
    transaction_id: Optional[str] = None
    event_type: str
    payload: Dict[str, Any]
    signature_valid: bool
    delivery_status: str
    attempt_count: int
    duplicate_attempts: int
    processing_logs: Optional[List[Dict[str, Any]]] = None
    is_seeded: bool
    created_at: datetime
    delivered_at: Optional[datetime] = None
    deduplicated: bool = False

