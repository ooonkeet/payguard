"""Transaction ORM model."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Index, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")
    payment_method: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    customer_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    scenario: Mapped[str] = mapped_column(String(64), nullable=False, default="successful_payment")
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    gateway_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    response_code: Mapped[str] = mapped_column(String(32), nullable=False, default="200")
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processing_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    response_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    timeline: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    is_seeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    webhooks = relationship("WebhookEvent", back_populates="transaction", cascade="all, delete-orphan")
    bugs = relationship("Bug", back_populates="transaction")

    __table_args__ = (
        Index("ix_transactions_status_created", "status", "created_at"),
        Index("ix_transactions_method_status", "payment_method", "status"),
    )

