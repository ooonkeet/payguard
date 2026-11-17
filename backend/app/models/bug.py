"""Bug / Defect ORM model."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Bug(Base):
    __tablename__ = "bugs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bug_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="P2")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN", index=True)
    module: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reproduction_steps: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actual_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    environment: Mapped[str] = mapped_column(String(64), nullable=False, default="SANDBOX")
    transaction_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("transactions.transaction_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    associated_test_case: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_seeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    transaction = relationship("Transaction", back_populates="bugs")

    __table_args__ = (Index("ix_bugs_severity_status", "severity", "status"),)

