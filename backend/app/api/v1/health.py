"""Health check endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_db

router = APIRouter(tags=["Health"])


def _check_health(db: Session) -> dict:
    settings = get_settings()
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"

    return {
        "success": True,
        "data": {
            "status": "healthy" if db_status == "connected" else "degraded",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
            "simulation_mode": True,
            "database": db_status,
            "database_engine": "sqlite" if settings.is_sqlite else "postgresql",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }


@router.get("/health")
def root_health(db: Session = Depends(get_db)) -> dict:
    return _check_health(db)


@router.get("/api/v1/health")
def api_v1_health(db: Session = Depends(get_db)) -> dict:
    return _check_health(db)

