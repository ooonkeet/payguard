"""Database Persistence, Constraints, Decimal Precision, Integrity, and Validation Console Tests (10 test cases)."""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import compute_payload_hash
from app.models.bug import Bug
from app.models.transaction import Transaction
from app.models.webhook import WebhookEvent


@pytest.mark.database
def test_transaction_record_persisted_in_database(
    client: TestClient, db_session: Session, payment_payload_factory
) -> None:
    payload = payment_payload_factory(order_id="ORD-DB-001", amount="2345.67")
    resp = client.post("/api/v1/payments", json=payload)
    assert resp.status_code == 201
    tx_id = resp.json()["data"]["transaction_id"]

    row = db_session.scalar(select(Transaction).where(Transaction.transaction_id == tx_id))
    assert row is not None
    assert row.order_id == "ORD-DB-001"
    assert row.status == "SUCCESS"
    assert row.amount == Decimal("2345.67")


@pytest.mark.database
def test_unique_transaction_id_constraint_enforced(db_session: Session) -> None:
    h = compute_payload_hash({"a": 1})
    tx1 = Transaction(
        transaction_id="TXN-DUP-ID-001",
        order_id="ORD-1",
        amount=Decimal("100.00"),
        currency="INR",
        payment_method="UPI",
        status="SUCCESS",
        idempotency_key="idem-u1",
        payload_hash=h,
        response_code="PG_200_APPROVED",
    )
    tx2 = Transaction(
        transaction_id="TXN-DUP-ID-001",
        order_id="ORD-2",
        amount=Decimal("200.00"),
        currency="INR",
        payment_method="UPI",
        status="SUCCESS",
        idempotency_key="idem-u2",
        payload_hash=h,
        response_code="PG_200_APPROVED",
    )
    db_session.add(tx1)
    db_session.commit()
    db_session.add(tx2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.database
def test_unique_idempotency_key_constraint_enforced(db_session: Session) -> None:
    h = compute_payload_hash({"a": 1})
    tx1 = Transaction(
        transaction_id="TXN-IDEM-1",
        order_id="ORD-1",
        amount=Decimal("50.00"),
        currency="INR",
        payment_method="CARD",
        status="SUCCESS",
        idempotency_key="idem-shared-constraint",
        payload_hash=h,
        response_code="PG_200_APPROVED",
    )
    tx2 = Transaction(
        transaction_id="TXN-IDEM-2",
        order_id="ORD-2",
        amount=Decimal("50.00"),
        currency="INR",
        payment_method="CARD",
        status="SUCCESS",
        idempotency_key="idem-shared-constraint",
        payload_hash=h,
        response_code="PG_200_APPROVED",
    )
    db_session.add(tx1)
    db_session.commit()
    db_session.add(tx2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.database
def test_decimal_monetary_precision_no_floating_point_drift(
    client: TestClient, db_session: Session, payment_payload_factory
) -> None:
    # 0.1 + 0.2 style float trap values must remain exact Decimal(14,2)
    for amt in ("19.99", "0.10", "0.20", "99999.95"):
        tx_id = client.post("/api/v1/payments", json=payment_payload_factory(amount=amt)).json()["data"]["transaction_id"]
        row = db_session.scalar(select(Transaction).where(Transaction.transaction_id == tx_id))
        assert row is not None
        assert row.amount == Decimal(amt)
        assert f"{row.amount:.2f}" == amt


@pytest.mark.database
def test_webhook_event_id_unique_constraint_enforced(db_session: Session) -> None:
    ev1 = WebhookEvent(
        event_id="EVT-UNIQ-001",
        transaction_id=None,
        event_type="payment.success",
        payload={"event_id": "EVT-UNIQ-001"},
        signature_valid=True,
        delivery_status="DELIVERED",
    )
    ev2 = WebhookEvent(
        event_id="EVT-UNIQ-001",
        transaction_id=None,
        event_type="payment.success",
        payload={"event_id": "EVT-UNIQ-001"},
        signature_valid=True,
        delivery_status="DELIVERED",
    )
    db_session.add(ev1)
    db_session.commit()
    db_session.add(ev2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.database
def test_foreign_key_referential_integrity_on_bug_transaction(db_session: Session) -> None:
    bug = Bug(
        bug_id="BUG-FK-001",
        title="Orphan FK test",
        description="Should fail FK constraint",
        severity="High",
        priority="P1",
        status="OPEN",
        module="Database",
        transaction_id="TXN-NON-EXISTENT-FK",
    )
    db_session.add(bug)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.database
def test_all_eight_validation_checks_pass_on_consistent_data(
    client: TestClient, payment_payload_factory
) -> None:
    tx = client.post("/api/v1/payments", json=payment_payload_factory(scenario="pending_transaction")).json()["data"]
    client.post(
        "/api/v1/webhooks/simulate",
        json={"transaction_id": tx["transaction_id"], "event_type": "payment.success"},
    )

    checks_resp = client.get("/api/v1/validation/checks")
    assert checks_resp.status_code == 200
    assert len(checks_resp.json()["data"]) == 8

    run_resp = client.post("/api/v1/validation/run", json={})
    assert run_resp.status_code == 200
    results = run_resp.json()["data"]
    assert len(results) == 8
    assert all(r["execution_status"] == "PASS" for r in results)
    assert all(r["issues_detected"] == 0 for r in results)


@pytest.mark.database
def test_validation_detects_orphan_webhook_record(client: TestClient, db_session: Session) -> None:
    orphan = WebhookEvent(
        event_id="EVT-ORPHAN-999",
        transaction_id=None,
        event_type="payment.success",
        payload={"event_id": "EVT-ORPHAN-999", "transaction_id": "TXN-MISSING"},
        signature_valid=True,
        delivery_status="DELIVERED",
    )
    db_session.add(orphan)
    db_session.commit()

    run_resp = client.post(
        "/api/v1/validation/run",
        json={"check_keys": ["verify_webhook_transaction_links", "detect_orphan_records"]},
    )
    assert run_resp.status_code == 200
    results = run_resp.json()["data"]
    assert all(r["execution_status"] == "FAIL" for r in results)
    assert all(r["issues_detected"] == 1 for r in results)


@pytest.mark.database
def test_validation_detects_amount_discrepancy_between_db_and_api_payload(
    client: TestClient, db_session: Session, payment_payload_factory
) -> None:
    tx_id = client.post("/api/v1/payments", json=payment_payload_factory(amount="400.00")).json()["data"]["transaction_id"]
    row = db_session.scalar(select(Transaction).where(Transaction.transaction_id == tx_id))
    assert row is not None
    # Simulate corrupted response_payload amount drift
    row.response_payload = {**(row.response_payload or {}), "amount": "450.00"}
    db_session.commit()

    consistency = client.get(f"/api/v1/validation/consistency/{tx_id}").json()["data"]
    assert consistency["consistent"] is False
    assert consistency["amount_consistent"] is False
    assert len(consistency["discrepancies"]) >= 1

    check_res = client.post(
        "/api/v1/validation/run", json={"check_keys": ["verify_payment_amount_consistency"]}
    ).json()["data"][0]
    assert check_res["execution_status"] == "FAIL"
    assert check_res["issues_detected"] == 1


@pytest.mark.database
def test_consistency_checker_passes_after_valid_webhook_settlement(
    client: TestClient, payment_payload_factory
) -> None:
    tx = client.post("/api/v1/payments", json=payment_payload_factory(scenario="delayed_webhook")).json()["data"]
    client.post(
        "/api/v1/webhooks/simulate",
        json={"transaction_id": tx["transaction_id"], "event_type": "payment.success"},
    )

    report = client.get(f"/api/v1/validation/consistency/{tx['transaction_id']}").json()["data"]
    assert report["consistent"] is True
    assert report["db_status"] == "SUCCESS"
    assert report["api_response_status"] == "SUCCESS"
    assert report["latest_webhook_event"] == "payment.success"
    assert report["discrepancies"] == []

