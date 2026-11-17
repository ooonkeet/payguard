"""PayGuard FastAPI Application Entrypoint."""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import (
    auth_sim,
    bugs,
    collections,
    dashboard,
    health,
    payments,
    reports,
    settings as settings_router,
    tests,
    validation,
    webhooks,
)
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import logger
from app.database.base import Base
from app.database.seed import seed_initial_data
from app.database.session import SessionLocal, engine

# Ensure all models are imported so SQLAlchemy metadata is populated
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting PayGuard Sandbox API...")
    Base.metadata.create_all(bind=engine)
    if os.environ.get("PAYGUARD_SKIP_STARTUP_SEED") != "1":
        db = SessionLocal()
        try:
            seeded = seed_initial_data(db)
            if seeded:
                logger.info("Initial sandbox demo dataset seeded successfully.")
        finally:
            db.close()
    yield
    logger.info("Shutting down PayGuard Sandbox API.")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="PayGuard — Payment Gateway Testing & Automation Platform",
        description=(
            "Simulated sandbox payment reliability, API contract testing, webhook verification, "
            "database validation, automated Pytest execution, and defect tracking platform."
        ),
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(payments.router)
    app.include_router(webhooks.router)
    app.include_router(tests.router)
    app.include_router(validation.router)
    app.include_router(bugs.router)
    app.include_router(dashboard.router)
    app.include_router(reports.router)
    app.include_router(collections.router)
    app.include_router(auth_sim.router)
    app.include_router(settings_router.router)

    return app


app = create_app()
