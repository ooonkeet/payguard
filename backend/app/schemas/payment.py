"""Pydantic schemas for Payment Simulator and Transaction Management."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaymentStatus(str, Enum):
    CREATED = "CREATED"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PENDING = "PENDING"
    REFUNDED = "REFUNDED"


class PaymentMethod(str, Enum):
    UPI = "UPI"
    CARD = "CARD"
    NET_BANKING = "NET_BANKING"
    WALLET = "WALLET"


class SupportedCurrency(str, Enum):
    INR = "INR"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    SGD = "SGD"


class PaymentScenario(str, Enum):
    SUCCESSFUL_PAYMENT = "successful_payment"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    INVALID_PAYMENT_DETAILS = "invalid_payment_details"
    GATEWAY_TIMEOUT = "gateway_timeout"
    GATEWAY_UNAVAILABLE = "gateway_unavailable"
    PENDING_TRANSACTION = "pending_transaction"
    DELAYED_WEBHOOK = "delayed_webhook"
    DUPLICATE_PAYMENT_REQUEST = "duplicate_payment_request"
    PAYMENT_FAILURE = "payment_failure"
    PROCESSING_ERROR = "processing_error"


class PaymentCreateRequest(BaseModel):
    order_id: str = Field(..., min_length=3, max_length=64, description="Merchant order reference")
    amount: Decimal = Field(..., gt=Decimal("0.00"), le=Decimal("10000000.00"), decimal_places=2)
    currency: SupportedCurrency = Field(default=SupportedCurrency.INR)
    payment_method: PaymentMethod = Field(default=PaymentMethod.UPI)
    customer_reference: Optional[str] = Field(default=None, max_length=128)
    idempotency_key: str = Field(..., min_length=4, max_length=128)
    scenario: PaymentScenario = Field(default=PaymentScenario.SUCCESSFUL_PAYMENT)
    metadata: Optional[Dict[str, Any]] = Field(default=None)

    @field_validator("order_id", "idempotency_key")
    @classmethod
    def strip_and_validate_non_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be blank or whitespace only.")
        return cleaned

    @field_validator("customer_reference")
    @classmethod
    def sanitize_customer_ref(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class TimelineEvent(BaseModel):
    stage: str
    status: str
    timestamp: str
    detail: str
    elapsed_ms: int = 0


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_id: str
    order_id: str
    amount: Decimal
    currency: str
    payment_method: str
    customer_reference: Optional[str] = None
    scenario: str
    status: str
    idempotency_key: str
    gateway_reference: Optional[str] = None
    response_code: str
    failure_reason: Optional[str] = None
    processing_duration_ms: int
    is_seeded: bool
    created_at: datetime
    updated_at: datetime
    idempotent_replay: bool = False
    timeline: Optional[List[Dict[str, Any]]] = None


class TransactionDetailOut(TransactionOut):
    request_payload: Optional[Dict[str, Any]] = None
    response_payload: Optional[Dict[str, Any]] = None
    webhooks: List[Dict[str, Any]] = Field(default_factory=list)
    related_bugs: List[Dict[str, Any]] = Field(default_factory=list)
    related_tests: List[Dict[str, Any]] = Field(default_factory=list)


class PaymentStatusOut(BaseModel):
    transaction_id: str
    order_id: str
    status: str
    response_code: str
    failure_reason: Optional[str] = None
    gateway_reference: Optional[str] = None
    updated_at: datetime


class RefundRequest(BaseModel):
    reason: str = Field(default="Requested by merchant QA verification", min_length=3, max_length=255)


class ReconcileRequest(BaseModel):
    resolved_status: PaymentStatus = Field(..., description="Target status: SUCCESS or FAILED")
    note: Optional[str] = Field(default="Reconciled via gateway status inquiry", max_length=255)

