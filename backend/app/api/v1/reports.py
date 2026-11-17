"""Test Reporting & Quality Metrics REST Endpoints."""

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.services import reporting_service

router = APIRouter(prefix="/api/v1/reports", tags=["Reporting"])


@router.get("/metrics")
def quality_metrics(db: Session = Depends(get_db)) -> dict:
    data = reporting_service.get_quality_metrics(db)
    return {"success": True, "data": data}


@router.get("/transactions.csv")
def download_transactions_csv(db: Session = Depends(get_db)) -> Response:
    csv_text = reporting_service.export_transactions_csv(db)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="payguard_transactions_report.csv"'},
    )


@router.get("/tests.csv")
def download_tests_csv(db: Session = Depends(get_db)) -> Response:
    csv_text = reporting_service.export_tests_csv(db)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="payguard_test_runs_report.csv"'},
    )

