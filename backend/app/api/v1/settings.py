"""Settings & Demo Data Reset REST Endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.seed import reset_demo_data
from app.database.session import get_db
from app.models.api_collection import ApiCollection
from app.models.bug import Bug
from app.models.test_run import TestRun
from app.models.transaction import Transaction
from app.models.webhook import WebhookEvent

router = APIRouter(prefix="/api/v1/settings", tags=["Settings"])


@router.get("")
def get_system_settings(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    return {
        "success": True,
        "data": {
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
            "simulation_mode": True,
            "database_engine": "SQLite (Local Fallback)" if settings.is_sqlite else "PostgreSQL",
            "webhook_hmac_algorithm": "HMAC-SHA256",
            "webhook_secret_configured": bool(settings.WEBHOOK_SECRET),
            "cors_origins": settings.cors_origin_list,
            "record_counts": {
                "transactions": db.scalar(select(func.count(Transaction.id))) or 0,
                "seeded_transactions": db.scalar(select(func.count(Transaction.id)).where(Transaction.is_seeded.is_(True))) or 0,
                "webhooks": db.scalar(select(func.count(WebhookEvent.id))) or 0,
                "test_runs": db.scalar(select(func.count(TestRun.id))) or 0,
                "bugs": db.scalar(select(func.count(Bug.id))) or 0,
                "api_collections": db.scalar(select(func.count(ApiCollection.id))) or 0,
            },
        },
    }


@router.post("/reset-demo")
def reset_demo(db: Session = Depends(get_db)) -> dict:
    counts = reset_demo_data(db)
    return {
        "success": True,
        "data": {
            "message": "Sandbox demo dataset has been reset to initial baseline.",
            "counts": counts,
        },
    }

