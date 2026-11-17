"""Overview Dashboard Analytics REST Endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services import dashboard_service

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


@router.get("/metrics")
def dashboard_metrics(
    range_key: str = Query(default="30d", alias="range", pattern="^(24h|7d|30d|all|custom)$"),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    data = dashboard_service.get_dashboard_metrics(db, range_key=range_key, start_date=start_date, end_date=end_date)
    return {"success": True, "data": data}


@router.get("/transactions")
def dashboard_transactions(
    range_key: str = Query(default="30d", alias="range", pattern="^(24h|7d|30d|all|custom)$"),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    data = dashboard_service.get_transaction_volume_series(
        db, range_key=range_key, start_date=start_date, end_date=end_date
    )
    return {"success": True, "data": data}


@router.get("/test-activity")
def dashboard_test_activity(
    range_key: str = Query(default="30d", alias="range", pattern="^(24h|7d|30d|all|custom)$"),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    data = dashboard_service.get_test_activity_series(
        db, range_key=range_key, start_date=start_date, end_date=end_date
    )
    return {"success": True, "data": data}

