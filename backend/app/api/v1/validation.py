"""Database Validation & Transaction Consistency REST Endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.validation import ValidationRunRequest
from app.services import validation_service

router = APIRouter(prefix="/api/v1/validation", tags=["Database Validation"])


@router.get("/checks")
def list_validation_checks() -> dict:
    checks = validation_service.get_validation_checks()
    return {"success": True, "data": [c.model_dump(mode="json") for c in checks]}


@router.post("/run")
def run_validation_checks(payload: ValidationRunRequest, db: Session = Depends(get_db)) -> dict:
    results = validation_service.run_validation_checks(
        db=db,
        check_keys=payload.check_keys,
        transaction_id=payload.transaction_id,
    )
    return {"success": True, "data": [r.model_dump(mode="json") for r in results]}


@router.get("/results")
def list_validation_results(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)) -> dict:
    results = validation_service.list_validation_results(db=db, limit=limit)
    return {"success": True, "data": [r.model_dump(mode="json") for r in results]}


@router.get("/consistency/{transaction_id}")
def check_consistency(transaction_id: str, db: Session = Depends(get_db)) -> dict:
    report = validation_service.check_transaction_consistency(db, transaction_id)
    return {"success": True, "data": report.model_dump(mode="json")}

