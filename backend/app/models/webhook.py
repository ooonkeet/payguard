"""WebhookEvent ORM model."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    transaction_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("transactions.transaction_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    signature_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    delivery_status: Mapped[str] = mapped_column(String(32), nullable=False, default="RECEIVED", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    duplicate_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processing_logs: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    is_seeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    transaction = relationship("Transaction", back_populates="webhooks")

    __table_args__ = (
        Index("ix_webhook_events_status_created", "delivery_status", "created_at"),
    )

