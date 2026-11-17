"""Overview Dashboard Analytics Service — 100% derived from persisted database records."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.test_run import TestRun
from app.models.transaction import Transaction
from app.models.webhook import WebhookEvent


def resolve_date_range(
    range_key: str = "30d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    now = datetime.now(timezone.utc)
    if range_key == "custom" and (start_date or end_date):
        start_dt = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc) if start_date else None
        end_dt = (
            datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            if end_date
            else now
        )
        return start_dt, end_dt
    if range_key == "24h":
        return now - timedelta(hours=24), now
    if range_key == "7d":
        return now - timedelta(days=7), now
    if range_key == "30d":
        return now - timedelta(days=30), now
    return None, None


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_dashboard_metrics(
    db: Session,
    range_key: str = "30d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    start_dt, end_dt = resolve_date_range(range_key, start_date, end_date)

    tx_stmt = select(Transaction)
    run_stmt = select(TestRun)
    if start_dt:
        tx_stmt = tx_stmt.where(Transaction.created_at >= start_dt)
        run_stmt = run_stmt.where(TestRun.started_at >= start_dt)
    if end_dt:
        tx_stmt = tx_stmt.where(Transaction.created_at <= end_dt)
        run_stmt = run_stmt.where(TestRun.started_at <= end_dt)

    transactions = db.scalars(tx_stmt).all()
    test_runs = db.scalars(run_stmt).all()

    total_tx = len(transactions)
    success_tx = sum(1 for t in transactions if t.status == "SUCCESS")
    failed_tx = sum(1 for t in transactions if t.status == "FAILED")
    pending_tx = sum(1 for t in transactions if t.status == "PENDING")
    refunded_tx = sum(1 for t in transactions if t.status == "REFUNDED")

    success_rate = round((success_tx / total_tx) * 100.0, 2) if total_tx > 0 else 0.0
    failure_rate = round((failed_tx / total_tx) * 100.0, 2) if total_tx > 0 else 0.0
    avg_processing_ms = (
        round(sum(t.processing_duration_ms for t in transactions) / total_tx, 1) if total_tx > 0 else 0.0
    )

    total_test_executions = len(test_runs)
    passed_cases = sum(r.passed for r in test_runs)
    failed_cases = sum(r.failed for r in test_runs)
    skipped_cases = sum(r.skipped for r in test_runs)
    total_cases = passed_cases + failed_cases + skipped_cases
    test_pass_rate = round((passed_cases / total_cases) * 100.0, 2) if total_cases > 0 else 0.0

    distribution = [
        {"name": "SUCCESS", "value": success_tx, "color": "#10B981"},
        {"name": "FAILED", "value": failed_tx, "color": "#EF4444"},
        {"name": "PENDING", "value": pending_tx, "color": "#F59E0B"},
        {"name": "REFUNDED", "value": refunded_tx, "color": "#6366F1"},
    ]

    return {
        "range": range_key,
        "total_transactions": total_tx,
        "successful_transactions": success_tx,
        "failed_transactions": failed_tx,
        "pending_transactions": pending_tx,
        "refunded_transactions": refunded_tx,
        "success_rate": success_rate,
        "failure_rate": failure_rate,
        "total_test_executions": total_test_executions,
        "passed_test_cases": passed_cases,
        "failed_test_cases": failed_cases,
        "skipped_test_cases": skipped_cases,
        "test_pass_rate": test_pass_rate,
        "avg_processing_time_ms": avg_processing_ms,
        "distribution": distribution,
    }


def get_transaction_volume_series(
    db: Session,
    range_key: str = "30d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    start_dt, end_dt = resolve_date_range(range_key, start_date, end_date)
    stmt = select(Transaction)
    if start_dt:
        stmt = stmt.where(Transaction.created_at >= start_dt)
    if end_dt:
        stmt = stmt.where(Transaction.created_at <= end_dt)
    transactions = db.scalars(stmt.order_by(Transaction.created_at)).all()

    buckets: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"date": "", "total": 0, "success": 0, "failed": 0, "pending": 0, "refunded": 0}
    )

    for tx in transactions:
        dt = _ensure_utc(tx.created_at)
        label = dt.strftime("%Y-%m-%d %H:00") if range_key == "24h" else dt.strftime("%Y-%m-%d")
        bucket = buckets[label]
        bucket["date"] = label
        bucket["total"] += 1
        if tx.status == "SUCCESS":
            bucket["success"] += 1
        elif tx.status == "FAILED":
            bucket["failed"] += 1
        elif tx.status == "PENDING":
            bucket["pending"] += 1
        elif tx.status == "REFUNDED":
            bucket["refunded"] += 1

    series = [buckets[k] for k in sorted(buckets.keys())]

    recent_transactions = db.scalars(
        select(Transaction).order_by(desc(Transaction.created_at), desc(Transaction.id)).limit(8)
    ).all()
    recent_failures = db.scalars(
        select(Transaction)
        .where(Transaction.status == "FAILED")
        .order_by(desc(Transaction.created_at), desc(Transaction.id))
        .limit(6)
    ).all()

    return {
        "volume_series": series,
        "recent_transactions": [
            {
                "transaction_id": t.transaction_id,
                "order_id": t.order_id,
                "amount": f"{t.amount:.2f}",
                "currency": t.currency,
                "payment_method": t.payment_method,
                "status": t.status,
                "processing_duration_ms": t.processing_duration_ms,
                "is_seeded": t.is_seeded,
                "created_at": t.created_at.isoformat(),
            }
            for t in recent_transactions
        ],
        "recent_failures": [
            {
                "transaction_id": t.transaction_id,
                "order_id": t.order_id,
                "amount": f"{t.amount:.2f}",
                "currency": t.currency,
                "response_code": t.response_code,
                "failure_reason": t.failure_reason,
                "created_at": t.created_at.isoformat(),
            }
            for t in recent_failures
        ],
    }


def get_test_activity_series(
    db: Session,
    range_key: str = "30d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    start_dt, end_dt = resolve_date_range(range_key, start_date, end_date)
    stmt = select(TestRun)
    if start_dt:
        stmt = stmt.where(TestRun.started_at >= start_dt)
    if end_dt:
        stmt = stmt.where(TestRun.started_at <= end_dt)
    runs = db.scalars(stmt.order_by(TestRun.started_at)).all()

    trends = [
        {
            "run_id": r.run_id,
            "suite_name": r.suite_name,
            "date": _ensure_utc(r.started_at).strftime("%m-%d %H:%M"),
            "passed": r.passed,
            "failed": r.failed,
            "skipped": r.skipped,
            "total": r.total_tests,
            "duration": round(r.duration, 2),
            "is_seeded": r.is_seeded,
        }
        for r in runs[-20:]
    ]

    recent_runs = db.scalars(select(TestRun).order_by(desc(TestRun.started_at), desc(TestRun.id)).limit(6)).all()
    recent_webhooks = db.scalars(
        select(WebhookEvent).order_by(desc(WebhookEvent.created_at), desc(WebhookEvent.id)).limit(6)
    ).all()

    return {
        "test_trends": trends,
        "recent_test_runs": [
            {
                "run_id": r.run_id,
                "suite_name": r.suite_name,
                "total_tests": r.total_tests,
                "passed": r.passed,
                "failed": r.failed,
                "skipped": r.skipped,
                "duration": round(r.duration, 2),
                "execution_status": r.execution_status,
                "is_seeded": r.is_seeded,
                "started_at": r.started_at.isoformat(),
            }
            for r in recent_runs
        ],
        "recent_webhooks": [
            {
                "event_id": wh.event_id,
                "event_type": wh.event_type,
                "transaction_id": wh.transaction_id,
                "delivery_status": wh.delivery_status,
                "signature_valid": wh.signature_valid,
                "attempt_count": wh.attempt_count,
                "is_seeded": wh.is_seeded,
                "created_at": wh.created_at.isoformat(),
            }
            for wh in recent_webhooks
        ],
    }

