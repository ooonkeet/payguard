"""TestRun and TestResult ORM models."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    suite_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    total_tests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    code_coverage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    execution_status: Mapped[str] = mapped_column(String(32), nullable=False, default="RUNNING", index=True)
    report_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stdout_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_seeded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    results = relationship("TestResult", back_populates="test_run", cascade="all, delete-orphan")


class TestResult(Base):
    __tablename__ = "test_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("test_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    test_name: Mapped[str] = mapped_column(String(255), nullable=False)
    node_id: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    test_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    failure_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    test_run = relationship("TestRun", back_populates="results")

    __table_args__ = (Index("ix_test_results_run_status", "run_id", "test_status"),)

