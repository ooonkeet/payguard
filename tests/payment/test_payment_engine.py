"""Payment Simulation Engine, Idempotency, Concurrency, Timeout & State Machine Tests (18 test cases)."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import InvalidStateTransitionError
from app.services.payment_state_machine import can_transition, validate_transition


@pytest.mark.smoke
@pytest.mark.regression
@pytest.mark.parametrize("method", ["UPI", "CARD", "NET_BANKING", "WALLET"])
def test_successful_payment_across_all_methods(client: TestClient, payment_payload_factory, method: str) -> None:
    resp = client.post("/api/v1/payments", json=payment_payload_factory(payment_method=method))
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["status"] == "SUCCESS"
    assert data["payment_method"] == method
    assert data["response_code"] == "PG_200_APPROVED"


@pytest.mark.regression
def test_insufficient_balance_scenario_fails_cleanly(client: TestClient, payment_payload_factory) -> None:
    resp = client.post("/api/v1/payments", json=payment_payload_factory(scenario="insufficient_balance"))
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["status"] == "FAILED"
    assert data["response_code"] == "PG_402_INSUFFICIENT_FUNDS"
    assert "insufficient" in data["failure_reason"].lower()


@pytest.mark.regression
def test_invalid_payment_details_scenario(client: TestClient, payment_payload_factory) -> None:
    resp = client.post("/api/v1/payments", json=payment_payload_factory(scenario="invalid_payment_details"))
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["status"] == "FAILED"
    assert data["response_code"] == "PG_400_INVALID_INSTRUMENT"


@pytest.mark.edge_case
@pytest.mark.regression
def test_gateway_timeout_leaves_transaction_pending_for_reconciliation(client: TestClient, payment_payload_factory) -> None:
    resp = client.post("/api/v1/payments", json=payment_payload_factory(scenario="gateway_timeout"))
    assert resp.status_code == 201
    data = resp.json()["data"]
    # Timeout must NOT assume payment failed; leaves PENDING for reconciliation
    assert data["status"] == "PENDING"
    assert data["response_code"] == "PG_504_GATEWAY_TIMEOUT"
    assert "reconciliation" in data["failure_reason"].lower()


@pytest.mark.edge_case
def test_gateway_unavailable_scenario(client: TestClient, payment_payload_factory) -> None:
    resp = client.post("/api/v1/payments", json=payment_payload_factory(scenario="gateway_unavailable"))
    assert resp.status_code == 201
    assert resp.json()["data"]["status"] == "FAILED"
    assert resp.json()["data"]["response_code"] == "PG_503_GATEWAY_UNAVAILABLE"


@pytest.mark.regression
def test_pending_and_delayed_webhook_scenarios(client: TestClient, payment_payload_factory) -> None:
    r1 = client.post("/api/v1/payments", json=payment_payload_factory(scenario="pending_transaction"))
    r2 = client.post("/api/v1/payments", json=payment_payload_factory(scenario="delayed_webhook"))
    assert r1.json()["data"]["status"] == "PENDING"
    assert r2.json()["data"]["status"] == "PENDING"
    assert r2.json()["data"]["response_code"] == "PG_202_WEBHOOK_DELAYED"


@pytest.mark.regression
def test_processing_error_and_payment_failure_scenarios(client: TestClient, payment_payload_factory) -> None:
    r1 = client.post("/api/v1/payments", json=payment_payload_factory(scenario="processing_error"))
    r2 = client.post("/api/v1/payments", json=payment_payload_factory(scenario="payment_failure"))
    assert r1.json()["data"]["status"] == "FAILED"
    assert r1.json()["data"]["response_code"] == "PG_500_PROCESSING_ERROR"
    assert r2.json()["data"]["status"] == "FAILED"
    assert r2.json()["data"]["response_code"] == "PG_422_PAYMENT_FAILED"


@pytest.mark.regression
@pytest.mark.edge_case
def test_idempotency_replay_returns_existing_transaction_without_duplicate(
    client: TestClient, payment_payload_factory
) -> None:
    payload = payment_payload_factory(idempotency_key="idem-replay-unique-001", amount="750.00")
    first = client.post("/api/v1/payments", json=payload)
    second = client.post("/api/v1/payments", json=payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.headers.get("X-Idempotent-Replay") == "true"
    assert first.json()["data"]["transaction_id"] == second.json()["data"]["transaction_id"]
    assert second.json()["data"]["idempotent_replay"] is True

    # Verify only 1 transaction exists in database
    listed = client.get("/api/v1/payments").json()["data"]
    assert len(listed) == 1


@pytest.mark.regression
@pytest.mark.edge_case
def test_idempotency_key_reuse_with_different_payload_returns_409(
    client: TestClient, payment_payload_factory
) -> None:
    first_payload = payment_payload_factory(idempotency_key="idem-conflict-001", amount="500.00")
    second_payload = {**first_payload, "amount": "999.00"}

    r1 = client.post("/api/v1/payments", json=first_payload)
    r2 = client.post("/api/v1/payments", json=second_payload)

    assert r1.status_code == 201
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert r2.json()["error"]["details"]["existing_transaction_id"] == r1.json()["data"]["transaction_id"]


@pytest.mark.edge_case
def test_concurrent_duplicate_payment_requests_create_single_transaction(
    client: TestClient, payment_payload_factory
) -> None:
    payload = payment_payload_factory(idempotency_key="idem-concurrent-burst-001", amount="1200.00")

    def submit(_: int):
        return client.post("/api/v1/payments", json=payload)

    with ThreadPoolExecutor(max_workers=5) as pool:
        responses = list(pool.map(submit, range(5)))

    status_codes = [r.status_code for r in responses]
    assert all(code in (200, 201) for code in status_codes)
    tx_ids = {r.json()["data"]["transaction_id"] for r in responses}
    assert len(tx_ids) == 1

    listed = client.get("/api/v1/payments").json()["data"]
    assert len(listed) == 1


@pytest.mark.edge_case
def test_concurrent_idempotent_requests_with_real_delay_all_return_settled_status(
    client: TestClient, payment_payload_factory, monkeypatch
) -> None:
    """Regression test for in-flight concurrency race: concurrent replays must wait for settled state."""
    monkeypatch.setenv("PAYGUARD_FAST_SIMULATION", "0")
    payload = payment_payload_factory(idempotency_key="idem-concurrent-real-delay-001", amount="1850.00")

    def submit(_: int):
        return client.post("/api/v1/payments", json=payload)

    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(submit, range(8)))

    assert all(r.status_code in (200, 201) for r in responses)
    assert len({r.json()["data"]["transaction_id"] for r in responses}) == 1
    statuses = [r.json()["data"]["status"] for r in responses]
    assert all(s == "SUCCESS" for s in statuses), f"Expected all SUCCESS, got {statuses}"
    assert all(r.json()["data"]["response_code"] == "PG_200_APPROVED" for r in responses)


@pytest.mark.regression
def test_refund_successful_transaction_transitions_to_refunded(client: TestClient, payment_payload_factory) -> None:
    tx = client.post("/api/v1/payments", json=payment_payload_factory(scenario="successful_payment")).json()["data"]
    refund_resp = client.post(
        f"/api/v1/payments/{tx['transaction_id']}/refund",
        json={"reason": "Customer requested refund"},
    )
    assert refund_resp.status_code == 200
    assert refund_resp.json()["data"]["status"] == "REFUNDED"
    assert refund_resp.json()["data"]["response_code"] == "PG_200_REFUNDED"


@pytest.mark.edge_case
def test_invalid_state_transition_cannot_refund_failed_or_already_refunded_payment(
    client: TestClient, payment_payload_factory
) -> None:
    failed_tx = client.post("/api/v1/payments", json=payment_payload_factory(scenario="payment_failure")).json()["data"]
    r_fail = client.post(f"/api/v1/payments/{failed_tx['transaction_id']}/refund", json={"reason": "Invalid attempt"})
    assert r_fail.status_code == 422
    assert r_fail.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    ok_tx = client.post("/api/v1/payments", json=payment_payload_factory(scenario="successful_payment")).json()["data"]
    assert client.post(f"/api/v1/payments/{ok_tx['transaction_id']}/refund", json={"reason": "Valid"}).status_code == 200
    r_double = client.post(f"/api/v1/payments/{ok_tx['transaction_id']}/refund", json={"reason": "Second refund"})
    assert r_double.status_code == 422
    assert r_double.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


@pytest.mark.regression
@pytest.mark.edge_case
def test_reconcile_pending_timeout_transaction_to_success_and_block_second_reconcile(
    client: TestClient, payment_payload_factory
) -> None:
    pending_tx = client.post("/api/v1/payments", json=payment_payload_factory(scenario="gateway_timeout")).json()["data"]
    assert pending_tx["status"] == "PENDING"

    rec = client.post(
        f"/api/v1/payments/{pending_tx['transaction_id']}/reconcile",
        json={"resolved_status": "SUCCESS", "note": "Confirmed captured via acquirer inquiry"},
    )
    assert rec.status_code == 200
    assert rec.json()["data"]["status"] == "SUCCESS"
    assert rec.json()["data"]["failure_reason"] is None

    # Reconciling an already SUCCESS transaction to FAILED must fail state machine validation
    rec2 = client.post(
        f"/api/v1/payments/{pending_tx['transaction_id']}/reconcile",
        json={"resolved_status": "FAILED", "note": "Invalid post-success transition"},
    )
    assert rec2.status_code == 422
    assert rec2.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


@pytest.mark.edge_case
def test_state_machine_unit_transition_matrix() -> None:
    assert can_transition("CREATED", "PROCESSING") is True
    assert can_transition("PROCESSING", "SUCCESS") is True
    assert can_transition("PROCESSING", "FAILED") is True
    assert can_transition("PROCESSING", "PENDING") is True
    assert can_transition("PENDING", "SUCCESS") is True
    assert can_transition("PENDING", "FAILED") is True
    assert can_transition("SUCCESS", "REFUNDED") is True

    # Prohibited transitions
    assert can_transition("CREATED", "SUCCESS") is False
    assert can_transition("FAILED", "SUCCESS") is False
    assert can_transition("REFUNDED", "SUCCESS") is False
    with pytest.raises(InvalidStateTransitionError):
        validate_transition("FAILED", "REFUNDED")

