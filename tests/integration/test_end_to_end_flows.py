"""Cross-Module Integration Tests: Payments + Webhooks + Validation + Bugs + Demo Seed Reset (5 test cases)."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
@pytest.mark.regression
def test_full_payment_to_webhook_to_validation_to_dashboard_pipeline(
    client: TestClient, payment_payload_factory
) -> None:
    # 1. Create delayed-webhook payment (starts PENDING)
    tx = client.post(
        "/api/v1/payments",
        json=payment_payload_factory(amount="2999.00", payment_method="UPI", scenario="delayed_webhook"),
    ).json()["data"]
    assert tx["status"] == "PENDING"

    # 2. Deliver valid signed webhook -> transitions to SUCCESS
    wh = client.post(
        "/api/v1/webhooks/simulate",
        json={"transaction_id": tx["transaction_id"], "event_type": "payment.success"},
    )
    assert wh.status_code == 200
    assert wh.json()["data"]["delivery_status"] == "DELIVERED"

    # 3. Verify transaction consistency report is completely clean
    consistency = client.get(f"/api/v1/validation/consistency/{tx['transaction_id']}").json()["data"]
    assert consistency["consistent"] is True
    assert consistency["final_payment_state"] == "SUCCESS"

    # 4. Verify dashboard metrics reflect the finalized SUCCESS transaction
    metrics = client.get("/api/v1/dashboard/metrics?range=24h").json()["data"]
    assert metrics["successful_transactions"] == 1
    assert metrics["pending_transactions"] == 0


@pytest.mark.integration
@pytest.mark.edge_case
def test_api_console_signed_webhook_execution_updates_transaction(
    client: TestClient, payment_payload_factory
) -> None:
    tx = client.post("/api/v1/payments", json=payment_payload_factory(scenario="pending_transaction")).json()["data"]

    exec_resp = client.post(
        "/api/v1/collections/execute",
        json={
            "method": "POST",
            "endpoint": "/api/v1/webhooks/payment",
            "headers": {"Content-Type": "application/json"},
            "query_params": {},
            "body": {
                "event_id": "EVT-INT-CONSOLE-01",
                "event_type": "payment.success",
                "transaction_id": tx["transaction_id"],
            },
            "sign_webhook": True,
        },
    )
    assert exec_resp.status_code == 200
    assert exec_resp.json()["data"]["status_code"] == 200
    assert client.get(f"/api/v1/payments/{tx['transaction_id']}/status").json()["data"]["status"] == "SUCCESS"


@pytest.mark.integration
def test_failed_payment_to_bug_report_and_detail_linkage(client: TestClient, payment_payload_factory) -> None:
    tx = client.post("/api/v1/payments", json=payment_payload_factory(scenario="processing_error")).json()["data"]
    assert tx["status"] == "FAILED"

    bug = client.post(
        "/api/v1/bugs",
        json={
            "title": "Switch routing error 96 on wallet checkout",
            "description": "Reproduced via processing_error simulation",
            "severity": "Critical",
            "priority": "P0",
            "module": "Payment Simulator",
            "transaction_id": tx["transaction_id"],
        },
    ).json()["data"]

    detail = client.get(f"/api/v1/payments/{tx['transaction_id']}").json()["data"]
    assert len(detail["related_bugs"]) == 1
    assert detail["related_bugs"][0]["bug_id"] == bug["bug_id"]


@pytest.mark.integration
def test_reset_demo_data_populates_exact_baseline_counts(client: TestClient) -> None:
    resp = client.post("/api/v1/settings/reset-demo")
    assert resp.status_code == 200
    counts = resp.json()["data"]["counts"]
    assert counts["transactions"] == 28  # 20 success + 5 failed + 3 pending
    assert counts["webhooks"] == 5
    assert counts["test_runs"] == 3
    assert counts["bugs"] == 3
    assert counts["api_collections"] == 4

    metrics = client.get("/api/v1/dashboard/metrics?range=30d").json()["data"]
    assert metrics["successful_transactions"] == 20
    assert metrics["failed_transactions"] == 5
    assert metrics["pending_transactions"] == 3


@pytest.mark.integration
def test_api_collection_persistence_crud(client: TestClient) -> None:
    created = client.post(
        "/api/v1/collections",
        json={
            "collection_name": "CUSTOM QA CHECKS",
            "description": "Custom saved endpoints",
            "requests": [
                {
                    "id": "custom-1",
                    "name": "Health Check",
                    "method": "GET",
                    "endpoint": "/api/v1/health",
                    "headers": {},
                    "query_params": {},
                    "body": None,
                }
            ],
        },
    )
    assert created.status_code == 201
    col_id = created.json()["data"]["id"]

    listed = client.get("/api/v1/collections").json()["data"]
    assert any(c["id"] == col_id for c in listed)

    deleted = client.delete(f"/api/v1/collections/{col_id}")
    assert deleted.status_code == 200

