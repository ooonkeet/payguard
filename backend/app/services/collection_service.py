"""API Testing Console Collections Service."""

from datetime import datetime, timezone
from typing import List

from sqlalchemy import asc, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.api_collection import ApiCollection
from app.schemas.api_collection import (
    ApiCollectionCreateRequest,
    ApiCollectionOut,
    ApiCollectionUpdateRequest,
)


def list_collections(db: Session) -> List[ApiCollectionOut]:
    rows = db.scalars(select(ApiCollection).order_by(asc(ApiCollection.id))).all()
    return [ApiCollectionOut.model_validate(r) for r in rows]


def create_collection(db: Session, payload: ApiCollectionCreateRequest) -> ApiCollectionOut:
    col = ApiCollection(
        collection_name=payload.collection_name.strip(),
        description=payload.description,
        configuration={"requests": [r.model_dump() for r in payload.requests]},
        is_seeded=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(col)
    db.commit()
    db.refresh(col)
    return ApiCollectionOut.model_validate(col)


def update_collection(db: Session, collection_id: int, payload: ApiCollectionUpdateRequest) -> ApiCollectionOut:
    col = db.scalar(select(ApiCollection).where(ApiCollection.id == collection_id))
    if col is None:
        raise NotFoundError("ApiCollection", str(collection_id))

    if payload.collection_name is not None:
        col.collection_name = payload.collection_name.strip()
    if payload.description is not None:
        col.description = payload.description
    if payload.requests is not None:
        col.configuration = {"requests": [r.model_dump() for r in payload.requests]}

    col.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(col)
    return ApiCollectionOut.model_validate(col)


def delete_collection(db: Session, collection_id: int) -> None:
    col = db.scalar(select(ApiCollection).where(ApiCollection.id == collection_id))
    if col is None:
        raise NotFoundError("ApiCollection", str(collection_id))
    db.delete(col)
    db.commit()

