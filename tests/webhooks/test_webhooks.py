"""Webhook HMAC-SHA256 Verification, Deduplication, State Updates, and Retry Tests (10 test cases)."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.regression
@pytest.mark.edge_case
def test_valid_signed_webhook_transitions_pending_payment_to_success(
    client: TestClient, payment_payload_factory, sign_webhook_payload
) -> None:
    tx = client.post("/api/v1/payments", json=payment_payload_factory(scenario="delayed_webhook")).json()["data"]
    assert tx["status"] == "PENDING"

    event_payload = {
        "event_id": "EVT-VALID-001",
        "event_type": "payment.success",
        "transaction_id": tx["transaction_id"],
        "amount": tx["amount"],
        "currency": tx["currency"],
    }
    raw, sig = sign_webhook_payload(event_payload)
    resp = client.post(
        "/api/v1/webhooks/payment",
        content=raw,
        headers={"Content-Type": "application/json", "X-PayGuard-Signature": sig},
    )
    assert resp.status_code == 200
    ev = resp.json()["data"]
    assert ev["signature_valid"] is True
    assert ev["delivery_status"] == "DELIVERED"

    # Confirm transaction state updated in DB
    tx_status = client.get(f"/api/v1/payments/{tx['transaction_id']}/status").json()["data"]
    assert tx_status["status"] == "SUCCESS"


@pytest.mark.edge_case
def test_invalid_webhook_signature_rejected_with_401_and_preserves_tx_state(
    client: TestClient, payment_payload_factory
) -> None:
    tx = client.post("/api/v1/payments", json=payment_payload_factory(scenario="pending_transaction")).json()["data"]

    resp = client.post(
        "/api/v1/webhooks/payment",
        json={
            "event_id": "EVT-BAD-SIG-001",
            "event_type": "payment.success",
            "transaction_id": tx["transaction_id"],
        },
        headers={"X-PayGuard-Signature": "sha256=tampered00000000000000000000000000000000000000000000000000000000"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_WEBHOOK_SIGNATURE"
    assert resp.json()["data"]["signature_valid"] is False
    assert resp.json()["data"]["delivery_status"] == "INVALID_SIGNATURE"

    # Transaction must remain PENDING
    tx_status = client.get(f"/api/v1/payments/{tx['transaction_id']}/status").json()["data"]
    assert tx_status["status"] == "PENDING"


@pytest.mark.edge_case
def test_missing_webhook_signature_rejected_with_401(client: TestClient, payment_payload_factory) -> None:
    tx = client.post("/api/v1/payments", json=payment_payload_factory(scenario="pending_transaction")).json()["data"]
    resp = client.post(
        "/api/v1/webhooks/payment",
        json={
            "event_id": "EVT-NO-SIG-001",
            "event_type": "payment.failed",
            "transaction_id": tx["transaction_id"],
        },
    )
    assert resp.status_code == 401
    assert resp.json()["data"]["signature_valid"] is False


@pytest.mark.edge_case
@pytest.mark.regression
def test_duplicate_webhook_event_is_deduplicated_and_not_processed_twice(
    client: TestClient, payment_payload_factory, sign_webhook_payload
) -> None:
    tx = client.post("/api/v1/payments", json=payment_payload_factory(scenario="pending_transaction")).json()["data"]

    payload = {
        "event_id": "EVT-DEDUP-001",
        "event_type": "payment.success",
        "transaction_id": tx["transaction_id"],
    }
    raw, sig = sign_webhook_payload(payload)

    r1 = client.post(
        "/api/v1/webhooks/payment",
        content=raw,
        headers={"Content-Type": "application/json", "X-PayGuard-Signature": sig},
    )
    r2 = client.post(
        "/api/v1/webhooks/payment",
        content=raw,
        headers={"Content-Type": "application/json", "X-PayGuard-Signature": sig},
    )

    assert r1.status_code == 200
    assert r1.json()["meta"]["deduplicated"] is False
    assert r2.status_code == 200
    assert r2.json()["meta"]["deduplicated"] is True
    assert r2.json()["data"]["duplicate_attempts"] == 1
    assert r2.json()["data"]["attempt_count"] == 2

    # Ensure only 1 webhook record exists and timeline only recorded WEBHOOK_PROCESSED once
    events = client.get("/api/v1/webhooks/events").json()["data"]
    assert len(events) == 1
    tx_detail = client.get(f"/api/v1/payments/{tx['transaction_id']}").json()["data"]
    webhook_stages = [step for step in tx_detail["timeline"] if step["stage"] == "WEBHOOK_PROCESSED"]
    assert len(webhook_stages) == 1


@pytest.mark.edge_case
def test_failed_webhook_delivery_can_be_retried_and_succeeds(
    client: TestClient, payment_payload_factory, sign_webhook_payload
) -> None:
    tx = client.post("/api/v1/payments", json=payment_payload_factory(scenario="pending_transaction")).json()["data"]
    payload = {
        "event_id": "EVT-RETRY-001",
        "event_type": "payment.success",
        "transaction_id": tx["transaction_id"],
    }
    raw, sig = sign_webhook_payload(payload)

    first = client.post(
        "/api/v1/webhooks/payment",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-PayGuard-Signature": sig,
            "X-Simulate-Delivery-Failure": "true",
        },
    )
    assert first.status_code == 200
    assert first.json()["data"]["delivery_status"] == "FAILED"
    assert client.get(f"/api/v1/payments/{tx['transaction_id']}/status").json()["data"]["status"] == "PENDING"

    retry = client.post("/api/v1/webhooks/events/EVT-RETRY-001/retry")
    assert retry.status_code == 200
    assert retry.json()["data"]["delivery_status"] == "DELIVERED"
    assert retry.json()["data"]["attempt_count"] == 2
    assert client.get(f"/api/v1/payments/{tx['transaction_id']}/status").json()["data"]["status"] == "SUCCESS"


@pytest.mark.edge_case
def test_retry_on_invalid_signature_webhook_is_blocked(client: TestClient, payment_payload_factory) -> None:
    tx = client.post("/api/v1/payments", json=payment_payload_factory(scenario="pending_transaction")).json()["data"]
    client.post(
        "/api/v1/webhooks/payment",
        json={"event_id": "EVT-BAD-RETRY", "event_type": "payment.success", "transaction_id": tx["transaction_id"]},
        headers={"X-PayGuard-Signature": "sha256=invalid"},
    )
    retry = client.post("/api/v1/webhooks/events/EVT-BAD-RETRY/retry")
    assert retry.status_code == 400
    assert retry.json()["error"]["code"] == "INVALID_WEBHOOK_SIGNATURE"


@pytest.mark.edge_case
def test_webhook_for_failed_transaction_cannot_override_to_success(
    client: TestClient, payment_payload_factory, sign_webhook_payload
) -> None:
    tx = client.post("/api/v1/payments", json=payment_payload_factory(scenario="payment_failure")).json()["data"]
    assert tx["status"] == "FAILED"

    payload = {
        "event_id": "EVT-INVALID-TRANS-01",
        "event_type": "payment.success",
        "transaction_id": tx["transaction_id"],
    }
    raw, sig = sign_webhook_payload(payload)
    resp = client.post(
        "/api/v1/webhooks/payment",
        content=raw,
        headers={"Content-Type": "application/json", "X-PayGuard-Signature": sig},
    )
    assert resp.status_code == 200
    # Transaction must stay FAILED because FAILED -> SUCCESS is prohibited
    assert client.get(f"/api/v1/payments/{tx['transaction_id']}/status").json()["data"]["status"] == "FAILED"


@pytest.mark.regression
def test_webhook_simulate_endpoint_valid_and_refunded_flow(client: TestClient, payment_payload_factory) -> None:
    tx = client.post("/api/v1/payments", json=payment_payload_factory(scenario="successful_payment")).json()["data"]
    sim = client.post(
        "/api/v1/webhooks/simulate",
        json={"transaction_id": tx["transaction_id"], "event_type": "payment.refunded"},
    )
    assert sim.status_code == 200
    assert sim.json()["data"]["delivery_status"] == "DELIVERED"
    assert client.get(f"/api/v1/payments/{tx['transaction_id']}/status").json()["data"]["status"] == "REFUNDED"


@pytest.mark.edge_case
def test_webhook_simulate_invalid_signature_returns_401(client: TestClient, payment_payload_factory) -> None:
    tx = client.post("/api/v1/payments", json=payment_payload_factory(scenario="pending_transaction")).json()["data"]
    sim = client.post(
        "/api/v1/webhooks/simulate",
        json={
            "transaction_id": tx["transaction_id"],
            "event_type": "payment.success",
            "simulate_invalid_signature": True,
        },
    )
    assert sim.status_code == 401
    assert sim.json()["data"]["delivery_status"] == "INVALID_SIGNATURE"


@pytest.mark.contract
def test_webhook_list_and_get_by_event_id(client: TestClient, payment_payload_factory) -> None:
    tx = client.post("/api/v1/payments", json=payment_payload_factory(scenario="pending_transaction")).json()["data"]
    ev_id = client.post(
        "/api/v1/webhooks/simulate",
        json={"transaction_id": tx["transaction_id"], "event_type": "payment.failed"},
    ).json()["data"]["event_id"]

    fetched = client.get(f"/api/v1/webhooks/events/{ev_id}")
    assert fetched.status_code == 200
    assert fetched.json()["data"]["event_type"] == "payment.failed"

    filtered = client.get("/api/v1/webhooks/events?delivery_status=DELIVERED").json()["data"]
    assert any(e["event_id"] == ev_id for e in filtered)

