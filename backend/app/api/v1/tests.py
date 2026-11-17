"""Automated Test Suite Execution REST Endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.test_run import TestRunRequest
from app.services import test_runner_service

router = APIRouter(prefix="/api/v1/tests", tags=["Automated Testing"])


@router.post("/run")
def run_test_suite(payload: TestRunRequest, db: Session = Depends(get_db)) -> dict:
    run_detail = test_runner_service.execute_test_suite(
        db=db,
        suite=payload.suite_name,
        with_coverage=payload.with_coverage,
    )
    return {"success": True, "data": run_detail.model_dump(mode="json")}


@router.get("/runs")
def list_test_runs(
    suite_name: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    runs = test_runner_service.list_test_runs(db=db, suite_name=suite_name, limit=limit)
    return {"success": True, "data": [r.model_dump(mode="json") for r in runs]}


@router.get("/runs/{run_id}")
def get_test_run(run_id: str, db: Session = Depends(get_db)) -> dict:
    run_detail = test_runner_service.get_test_run(db, run_id)
    return {"success": True, "data": run_detail.model_dump(mode="json")}


@router.get("/runs/{run_id}/results")
def get_test_run_results(run_id: str, db: Session = Depends(get_db)) -> dict:
    results = test_runner_service.get_test_run_results(db, run_id)
    return {"success": True, "data": [r.model_dump(mode="json") for r in results]}


@router.get("/runs/{run_id}/report")
def download_html_report(run_id: str, db: Session = Depends(get_db)) -> FileResponse:
    report_path = test_runner_service.get_report_file_path(db, run_id)
    return FileResponse(path=str(report_path), media_type="text/html", filename=report_path.name)

