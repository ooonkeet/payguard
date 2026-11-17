"""SQLAlchemy engine and session management supporting PostgreSQL and SQLite fallback."""

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def build_engine(database_url: str | None = None) -> Engine:
    settings = get_settings()
    url = database_url or settings.DATABASE_URL
    is_sqlite = url.startswith("sqlite")

    connect_args: dict[str, Any] = {}
    engine_kwargs: dict[str, Any] = {
        "pool_pre_ping": True,
        "future": True,
    }

    if is_sqlite:
        connect_args = {"check_same_thread": False, "timeout": 30}
    else:
        engine_kwargs["pool_size"] = 10
        engine_kwargs["max_overflow"] = 20

    eng = create_engine(url, connect_args=connect_args, **engine_kwargs)

    if is_sqlite:

        @event.listens_for(eng, "connect")
        def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

    return eng


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

