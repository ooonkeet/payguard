"""API Smoke, Contract, Auth, Negative Boundary, Bug Tracker, and Reporting Tests (22 test cases)."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings


@pytest.mark.smoke
@pytest.mark.contract
def test_root_health_endpoint_contract(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "healthy"
    assert body["data"]["environment"] == "SANDBOX"
    assert body["data"]["simulation_mode"] is True
    assert body["data"]["database"] == "connected"


@pytest.mark.smoke
@pytest.mark.contract
def test_v1_health_endpoint_contract(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["data"]["service"] == "PayGuard"


@pytest.mark.smoke
@pytest.mark.contract
def test_create_payment_response_schema(client: TestClient, payment_payload_factory) -> None:
    payload = payment_payload_factory(amount="1500.50", currency="INR", payment_method="UPI")
    resp = client.post("/api/v1/payments", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    required_keys = {
        "id",
        "transaction_id",
        "order_id",
        "amount",
        "currency",
        "payment_method",
        "status",
        "idempotency_key",
        "gateway_reference",
        "response_code",
        "processing_duration_ms",
        "timeline",
        "created_at",
    }
    assert required_keys.issubset(data.keys())
    assert data["status"] == "SUCCESS"
    assert data["amount"] == "1500.50"
    assert isinstance(data["timeline"], list) and len(data["timeline"]) >= 5


@pytest.mark.smoke
@pytest.mark.contract
def test_get_payment_detail_and_status(client: TestClient, payment_payload_factory) -> None:
    created = client.post("/api/v1/payments", json=payment_payload_factory()).json()["data"]
    tx_id = created["transaction_id"]

    detail_resp = client.get(f"/api/v1/payments/{tx_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert detail["transaction_id"] == tx_id
    assert "request_payload" in detail and "response_payload" in detail
    assert isinstance(detail["webhooks"], list)

    status_resp = client.get(f"/api/v1/payments/{tx_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["data"]["status"] == "SUCCESS"


@pytest.mark.smoke
@pytest.mark.contract
def test_list_transactions_pagination_and_filters(client: TestClient, payment_payload_factory) -> None:
    client.post("/api/v1/payments", json=payment_payload_factory(order_id="ORD-FLT-1", amount="100.00", payment_method="UPI"))
    client.post(
        "/api/v1/payments",
        json=payment_payload_factory(
            order_id="ORD-FLT-2", amount="900.00", payment_method="CARD", scenario="insufficient_balance"
        ),
    )
    client.post("/api/v1/payments", json=payment_payload_factory(order_id="ORD-FLT-3", amount="500.00", payment_method="WALLET"))

    resp = client.get("/api/v1/payments?page=1&page_size=2&sort_by=amount&sort_order=desc")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["pagination"]["total"] == 3
    assert body["pagination"]["total_pages"] == 2
    assert float(body["data"][0]["amount"]) >= float(body["data"][1]["amount"])

    failed_only = client.get("/api/v1/payments?status=FAILED").json()["data"]
    assert len(failed_only) == 1
    assert failed_only[0]["order_id"] == "ORD-FLT-2"

    search_hit = client.get("/api/v1/payments?search=ORD-FLT-3").json()["data"]
    assert len(search_hit) == 1
    assert search_hit[0]["payment_method"] == "WALLET"


@pytest.mark.regression
@pytest.mark.contract
def test_negative_missing_required_fields_returns_422(client: TestClient) -> None:
    resp = client.post("/api/v1/payments", json={"currency": "INR"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert len(body["error"]["details"]["errors"]) >= 3


@pytest.mark.regression
@pytest.mark.contract
def test_negative_zero_and_negative_amount_rejected(client: TestClient, payment_payload_factory) -> None:
    r_neg = client.post("/api/v1/payments", json=payment_payload_factory(amount="-50.00"))
    r_zero = client.post("/api/v1/payments", json=payment_payload_factory(amount="0.00"))
    assert r_neg.status_code == 422
    assert r_zero.status_code == 422


@pytest.mark.regression
@pytest.mark.contract
def test_negative_excessive_amount_boundary_rejected(client: TestClient, payment_payload_factory) -> None:
    resp = client.post("/api/v1/payments", json=payment_payload_factory(amount="99999999.99"))
    assert resp.status_code == 422


@pytest.mark.regression
@pytest.mark.contract
def test_negative_invalid_currency_rejected(client: TestClient, payment_payload_factory) -> None:
    resp = client.post("/api/v1/payments", json=payment_payload_factory(currency="ZZZ"))
    assert resp.status_code == 422


@pytest.mark.regression
@pytest.mark.contract
def test_negative_invalid_payment_method_rejected(client: TestClient, payment_payload_factory) -> None:
    resp = client.post("/api/v1/payments", json=payment_payload_factory(payment_method="CRYPTO_INVALID"))
    assert resp.status_code == 422


@pytest.mark.regression
@pytest.mark.contract
def test_negative_short_idempotency_key_rejected(client: TestClient, payment_payload_factory) -> None:
    resp = client.post("/api/v1/payments", json=payment_payload_factory(idempotency_key="ab"))
    assert resp.status_code == 422


@pytest.mark.regression
@pytest.mark.contract
def test_negative_nonexistent_transaction_returns_404(client: TestClient) -> None:
    resp = client.get("/api/v1/payments/TXN-NONEXISTENT-404")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.contract
def test_auth_verify_valid_token(client: TestClient) -> None:
    settings = get_settings()
    resp = client.get("/api/v1/auth/verify", headers={"Authorization": f"Bearer {settings.API_AUTH_TOKEN}"})
    assert resp.status_code == 200
    assert resp.json()["data"]["authenticated"] is True


@pytest.mark.contract
def test_auth_verify_invalid_token_returns_401(client: TestClient) -> None:
    resp = client.get("/api/v1/auth/verify", headers={"Authorization": "Bearer wrong_token_value"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_AUTH_TOKEN"


@pytest.mark.contract
def test_auth_verify_missing_header_returns_401(client: TestClient) -> None:
    resp = client.get("/api/v1/auth/verify")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "MISSING_AUTH_TOKEN"


@pytest.mark.contract
def test_auth_verify_expired_token_returns_401(client: TestClient) -> None:
    settings = get_settings()
    resp = client.get("/api/v1/auth/verify", headers={"Authorization": f"Bearer {settings.EXPIRED_AUTH_TOKEN}"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "TOKEN_EXPIRED"


@pytest.mark.regression
@pytest.mark.contract
def test_bug_tracker_crud_lifecycle(client: TestClient, payment_payload_factory) -> None:
    tx = client.post("/api/v1/payments", json=payment_payload_factory(scenario="payment_failure")).json()["data"]

    create_resp = client.post(
        "/api/v1/bugs",
        json={
            "title": "Acquirer decline message truncated on card failure",
            "description": "Failure reason missing ISO code in API payload",
            "severity": "High",
            "priority": "P1",
            "module": "Payment Simulator",
            "reproduction_steps": "1. Run payment_failure scenario",
            "expected_result": "Full reason logged",
            "actual_result": "Truncated reason",
            "transaction_id": tx["transaction_id"],
            "associated_test_case": "test_payment_failure_scenario",
        },
    )
    assert create_resp.status_code == 201
    bug_id = create_resp.json()["data"]["bug_id"]
    assert create_resp.json()["data"]["status"] == "OPEN"

    patch_resp = client.patch(f"/api/v1/bugs/{bug_id}", json={"status": "FIXED", "severity": "Medium"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["data"]["status"] == "FIXED"
    assert patch_resp.json()["data"]["severity"] == "Medium"

    list_resp = client.get("/api/v1/bugs?status=FIXED")
    assert list_resp.status_code == 200
    assert any(b["bug_id"] == bug_id for b in list_resp.json()["data"])


@pytest.mark.contract
def test_dashboard_metrics_reflect_real_database_state(client: TestClient, payment_payload_factory) -> None:
    client.post("/api/v1/payments", json=payment_payload_factory(scenario="successful_payment"))
    client.post("/api/v1/payments", json=payment_payload_factory(scenario="successful_payment"))
    client.post("/api/v1/payments", json=payment_payload_factory(scenario="insufficient_balance"))
    client.post("/api/v1/payments", json=payment_payload_factory(scenario="pending_transaction"))

    resp = client.get("/api/v1/dashboard/metrics?range=30d")
    assert resp.status_code == 200
    m = resp.json()["data"]
    assert m["total_transactions"] == 4
    assert m["successful_transactions"] == 2
    assert m["failed_transactions"] == 1
    assert m["pending_transactions"] == 1
    assert m["success_rate"] == 50.0
    assert m["failure_rate"] == 25.0


@pytest.mark.contract
def test_reporting_metrics_and_csv_downloads(client: TestClient, payment_payload_factory) -> None:
    client.post("/api/v1/payments", json=payment_payload_factory(order_id="ORD-CSV-1"))

    metrics_resp = client.get("/api/v1/reports/metrics")
    assert metrics_resp.status_code == 200
    data = metrics_resp.json()["data"]
    assert "metric_definitions" in data
    assert "automated_test_pass_rate" in data["summary"]
    assert "test_case_coverage_percent" in data["summary"]
    assert "defect_density_per_100_tests" in data["summary"]

    tx_csv = client.get("/api/v1/reports/transactions.csv")
    assert tx_csv.status_code == 200
    assert "text/csv" in tx_csv.headers["content-type"]
    assert "ORD-CSV-1" in tx_csv.text

    tests_csv = client.get("/api/v1/reports/tests.csv")
    assert tests_csv.status_code == 200
    assert "run_id,suite_name" in tests_csv.text


@pytest.mark.contract
def test_reporting_filters_and_failure_analysis_endpoint(client: TestClient, payment_payload_factory) -> None:
    client.post("/api/v1/payments", json=payment_payload_factory(scenario="insufficient_balance"))
    fa_resp = client.get("/api/v1/reports/failure-analysis?include_seeded=false")
    assert fa_resp.status_code == 200
    fa = fa_resp.json()["data"]
    assert any(item["response_code"] == "PG_402_INSUFFICIENT_FUNDS" for item in fa["transaction_failure_breakdown"])

    filtered = client.get("/api/v1/reports/metrics?suite_name=smoke&include_seeded=false")
    assert filtered.status_code == 200
    assert filtered.json()["data"]["summary"]["total_runs"] == 0


@pytest.mark.contract
def test_api_console_rejects_external_host_ssrf(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/collections/execute",
        json={"method": "GET", "endpoint": "https://example.com/admin", "headers": {}, "query_params": {}},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "DISALLOWED_TARGET_HOST"


@pytest.mark.contract
def test_api_console_executes_real_local_request(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/collections/execute",
        json={"method": "GET", "endpoint": "/api/v1/health", "headers": {}, "query_params": {}},
    )
    assert resp.status_code == 200
    result = resp.json()["data"]
    assert result["status_code"] == 200
    assert result["body"]["data"]["service"] == "PayGuard"
    assert result["duration_ms"] >= 0


@pytest.mark.contract
def test_test_runner_rejects_arbitrary_suite_name(client: TestClient) -> None:
    resp = client.post("/api/v1/tests/run", json={"suite_name": "smoke; rm -rf /"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

