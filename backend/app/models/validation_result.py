"""ValidationResult ORM model for Database Validation checks."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ValidationResult(Base):
    __tablename__ = "validation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    check_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    check_name: Mapped[str] = mapped_column(String(128), nullable=False)
    execution_status: Mapped[str] = mapped_column(String(32), nullable=False)  # PASS, WARN, FAIL
    records_examined: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    issues_detected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    details: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    execution_duration_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)

