"""Bug / Defect Tracker REST Endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.bug import BugCreateRequest, BugUpdateRequest
from app.services import bug_service

router = APIRouter(prefix="/api/v1/bugs", tags=["Bug Tracker"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_bug(payload: BugCreateRequest, db: Session = Depends(get_db)) -> dict:
    bug = bug_service.create_bug(db, payload)
    return {"success": True, "data": bug.model_dump(mode="json")}


@router.get("")
def list_bugs(
    search: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    module: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    bugs = bug_service.list_bugs(
        db=db,
        search=search,
        severity=severity,
        status=status_filter,
        module=module,
    )
    return {"success": True, "data": [b.model_dump(mode="json") for b in bugs]}


@router.get("/{bug_id}")
def get_bug(bug_id: str, db: Session = Depends(get_db)) -> dict:
    bug = bug_service.get_bug(db, bug_id)
    return {"success": True, "data": bug.model_dump(mode="json")}


@router.patch("/{bug_id}")
def update_bug(bug_id: str, payload: BugUpdateRequest, db: Session = Depends(get_db)) -> dict:
    bug = bug_service.update_bug(db, bug_id, payload)
    return {"success": True, "data": bug.model_dump(mode="json")}


@router.delete("/{bug_id}", status_code=status.HTTP_200_OK)
def delete_bug(bug_id: str, db: Session = Depends(get_db)) -> dict:
    bug_service.delete_bug(db, bug_id)
    return {"success": True, "data": {"deleted": bug_id}}

