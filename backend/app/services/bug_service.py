"""Bug / Defect Tracker Service."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.bug import Bug
from app.models.transaction import Transaction
from app.schemas.bug import BugCreateRequest, BugOut, BugUpdateRequest


def create_bug(db: Session, payload: BugCreateRequest) -> BugOut:
    # Validate linked transaction_id if provided
    linked_tx_id = payload.transaction_id
    if linked_tx_id:
        tx = db.scalar(select(Transaction).where(Transaction.transaction_id == linked_tx_id))
        if tx is None:
            raise NotFoundError("Transaction", linked_tx_id)

    bug = Bug(
        bug_id=f"BUG-{uuid.uuid4().hex[:6].upper()}",
        title=payload.title.strip(),
        description=payload.description.strip(),
        severity=payload.severity.value,
        priority=payload.priority.value,
        status="OPEN",
        module=payload.module.strip(),
        reproduction_steps=payload.reproduction_steps,
        expected_result=payload.expected_result,
        actual_result=payload.actual_result,
        environment=payload.environment,
        transaction_id=linked_tx_id,
        associated_test_case=payload.associated_test_case,
        is_seeded=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(bug)
    db.commit()
    db.refresh(bug)
    return BugOut.model_validate(bug)


def list_bugs(
    db: Session,
    search: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    module: Optional[str] = None,
) -> List[BugOut]:
    stmt = select(Bug)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Bug.bug_id.ilike(pattern),
                Bug.title.ilike(pattern),
                Bug.description.ilike(pattern),
                Bug.associated_test_case.ilike(pattern),
            )
        )
    if severity and severity != "ALL":
        stmt = stmt.where(Bug.severity == severity)
    if status and status != "ALL":
        stmt = stmt.where(Bug.status == status)
    if module and module != "ALL":
        stmt = stmt.where(Bug.module == module)

    rows = db.scalars(stmt.order_by(desc(Bug.created_at), desc(Bug.id))).all()
    return [BugOut.model_validate(row) for row in rows]


def get_bug(db: Session, bug_id: str) -> BugOut:
    bug = db.scalar(select(Bug).where(Bug.bug_id == bug_id))
    if bug is None:
        raise NotFoundError("Bug", bug_id)
    return BugOut.model_validate(bug)


def update_bug(db: Session, bug_id: str, payload: BugUpdateRequest) -> BugOut:
    bug = db.scalar(select(Bug).where(Bug.bug_id == bug_id))
    if bug is None:
        raise NotFoundError("Bug", bug_id)

    update_data = payload.model_dump(exclude_unset=True)
    if "transaction_id" in update_data and update_data["transaction_id"]:
        tx = db.scalar(select(Transaction).where(Transaction.transaction_id == update_data["transaction_id"]))
        if tx is None:
            raise NotFoundError("Transaction", update_data["transaction_id"])

    for field, value in update_data.items():
        if hasattr(value, "value"):
            value = value.value
        setattr(bug, field, value)

    bug.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(bug)
    return BugOut.model_validate(bug)


def delete_bug(db: Session, bug_id: str) -> None:
    bug = db.scalar(select(Bug).where(Bug.bug_id == bug_id))
    if bug is None:
        raise NotFoundError("Bug", bug_id)
    db.delete(bug)
    db.commit()

