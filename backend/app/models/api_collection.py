"""API Collection ORM model for the API Testing Console."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ApiCollection(Base):
    __tablename__ = "api_collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    configuration: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_seeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

