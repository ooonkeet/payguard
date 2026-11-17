"""Shared Pytest fixtures using an isolated SQLite test database."""

import os
import sys
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Configure isolated test DB before importing application modules
TEST_DB_FILE = PROJECT_ROOT / "payguard_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE.as_posix()}"
os.environ["TEST_DATABASE_URL"] = f"sqlite:///{TEST_DB_FILE.as_posix()}"
os.environ["PAYGUARD_FAST_SIMULATION"] = "1"
os.environ["PAYGUARD_SKIP_STARTUP_SEED"] = "1"

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.core.security import canonical_payload_bytes, compute_webhook_signature  # noqa: E402
from app.database.base import Base  # noqa: E402
from app.database.session import SessionLocal as TestSessionLocal, engine as test_engine, get_db  # noqa: E402
import app.models  # noqa: F401, E402
from app.main import app as fastapi_app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def init_test_schema() -> Generator[None, None, None]:
    """Create schema once per test session on the isolated test database."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    test_engine.dispose()


@pytest.fixture(autouse=True)
def clean_database() -> Generator[None, None, None]:
    """Delete all rows in FK-safe reverse order while keeping foreign_keys=ON active."""
    with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def payment_payload_factory() -> Callable[..., Dict[str, Any]]:
    def _factory(**overrides: Any) -> Dict[str, Any]:
        uid = uuid.uuid4().hex[:8]
        payload: Dict[str, Any] = {
            "order_id": f"ORD-TEST-{uid}",
            "amount": "499.95",
            "currency": "INR",
            "payment_method": "UPI",
            "customer_reference": f"cust_{uid}",
            "idempotency_key": f"idem-test-{uid}",
            "scenario": "successful_payment",
        }
        payload.update(overrides)
        return payload

    return _factory


@pytest.fixture()
def sign_webhook_payload() -> Callable[[Dict[str, Any]], tuple[bytes, str]]:
    def _sign(payload: Dict[str, Any]) -> tuple[bytes, str]:
        raw = canonical_payload_bytes(payload)
        sig = f"sha256={compute_webhook_signature(raw)}"
        return raw, sig

    return _sign
