"""Test Reporting & Quality Metrics Service — distinguishes pass rate, code coverage, test case coverage, and defect density."""

import csv
import io
from collections import Counter
from typing import Any, Dict, List

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.test_run import TestResult, TestRun
from app.models.transaction import Transaction

# Total catalog of defined PayGuard functional requirement areas / planned test scenarios
PLANNED_TEST_SCENARIO_CATALOG = 55


def get_quality_metrics(db: Session) -> Dict[str, Any]:
    runs = db.scalars(select(TestRun).order_by(desc(TestRun.started_at))).all()
    results = db.scalars(select(TestResult).order_by(desc(TestResult.created_at))).all()
    bugs = db.scalars(select(Bug).order_by(desc(Bug.created_at))).all()
    transactions = db.scalars(select(Transaction)).all()

    total_test_cases_executed = sum(r.total_tests for r in runs)
    total_passed = sum(r.passed for r in runs)
    total_failed = sum(r.failed for r in runs)
    total_skipped = sum(r.skipped for r in runs)

    # 1. Automated Test Pass Rate & Failure Rate (execution outcome across runs)
    automated_test_pass_rate = (
        round((total_passed / total_test_cases_executed) * 100.0, 2) if total_test_cases_executed > 0 else 0.0
    )
    automated_test_failure_rate = (
        round((total_failed / total_test_cases_executed) * 100.0, 2) if total_test_cases_executed > 0 else 0.0
    )

    # 2. Code Coverage (statement coverage from pytest-cov on most recent real/coverage-enabled run)
    runs_with_cov = [r for r in runs if r.code_coverage is not None]
    latest_code_coverage = round(runs_with_cov[0].code_coverage, 2) if runs_with_cov else None

    # 3. Test Case Coverage (distinct automated test cases exercised / planned requirement test catalog)
    distinct_test_names = {res.test_name for res in results}
    test_case_coverage = min(100.0, round((len(distinct_test_names) / PLANNED_TEST_SCENARIO_CATALOG) * 100.0, 2))

    # 4. Defect Density (defects per 100 executed test cases and per 100 transactions)
    total_bugs = len(bugs)
    open_bugs = sum(1 for b in bugs if b.status in ("OPEN", "IN_PROGRESS"))
    defect_density_per_100_tests = (
        round((total_bugs / max(1, total_test_cases_executed)) * 100.0, 2) if total_test_cases_executed > 0 else 0.0
    )
    defect_density_per_100_tx = (
        round((total_bugs / max(1, len(transactions))) * 100.0, 2) if transactions else 0.0
    )

    # Severity distribution
    sev_counts = Counter(b.severity for b in bugs)
    defect_distribution = [
        {"severity": sev, "count": sev_counts.get(sev, 0)}
        for sev in ("Critical", "High", "Medium", "Low")
    ]

    # Regression failure trends (ordered chronologically)
    regression_trends = [
        {
            "run_id": r.run_id,
            "suite_name": r.suite_name,
            "date": r.started_at.strftime("%m-%d %H:%M"),
            "passed": r.passed,
            "failed": r.failed,
            "pass_rate": round((r.passed / r.total_tests) * 100.0, 1) if r.total_tests else 0.0,
            "duration": round(r.duration, 2),
        }
        for r in reversed(runs[:20])
    ]

    avg_api_response_ms = (
        round(sum(t.processing_duration_ms for t in transactions) / len(transactions), 1) if transactions else 0.0
    )
    avg_test_exec_sec = round(sum(r.duration for r in runs) / len(runs), 2) if runs else 0.0

    # Failure analysis (top failing test cases + transaction failure codes)
    failed_test_results = [res for res in results if res.test_status == "FAILED"]
    failed_test_groups = Counter(res.test_name for res in failed_test_results)
    top_test_failures = [
        {
            "test_name": name,
            "occurrences": count,
            "latest_message": next((r.failure_message for r in failed_test_results if r.test_name == name), ""),
        }
        for name, count in failed_test_groups.most_common(10)
    ]

    tx_failure_codes = Counter(t.response_code for t in transactions if t.status == "FAILED")
    transaction_failure_breakdown = [
        {"response_code": code, "count": count} for code, count in tx_failure_codes.most_common(10)
    ]

    return {
        "summary": {
            "total_runs": len(runs),
            "total_tests_executed": total_test_cases_executed,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "total_skipped": total_skipped,
            "automated_test_pass_rate": automated_test_pass_rate,
            "automated_test_failure_rate": automated_test_failure_rate,
            "code_coverage_percent": latest_code_coverage,
            "test_case_coverage_percent": test_case_coverage,
            "distinct_tests_exercised": len(distinct_test_names),
            "planned_test_catalog_size": PLANNED_TEST_SCENARIO_CATALOG,
            "total_defects": total_bugs,
            "open_defects": open_bugs,
            "defect_density_per_100_tests": defect_density_per_100_tests,
            "defect_density_per_100_transactions": defect_density_per_100_tx,
            "avg_api_response_time_ms": avg_api_response_ms,
            "avg_test_execution_time_sec": avg_test_exec_sec,
        },
        "metric_definitions": {
            "automated_test_pass_rate": "Percentage of executed automated assertions that passed across test runs.",
            "code_coverage": "Backend Python statement coverage measured by pytest-cov during execution.",
            "test_case_coverage": "Distinct automated test cases exercised relative to the planned requirement catalog.",
            "defect_density": "Logged defects normalized per 100 executed test cases (and per 100 transactions).",
        },
        "defect_distribution": defect_distribution,
        "regression_trends": regression_trends,
        "failure_analysis": {
            "top_test_failures": top_test_failures,
            "transaction_failure_breakdown": transaction_failure_breakdown,
        },
    }


def export_transactions_csv(db: Session) -> str:
    rows = db.scalars(select(Transaction).order_by(desc(Transaction.created_at))).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "transaction_id",
            "order_id",
            "amount",
            "currency",
            "payment_method",
            "status",
            "scenario",
            "idempotency_key",
            "gateway_reference",
            "response_code",
            "failure_reason",
            "processing_duration_ms",
            "is_seeded",
            "created_at",
        ]
    )
    for tx in rows:
        writer.writerow(
            [
                tx.transaction_id,
                tx.order_id,
                f"{tx.amount:.2f}",
                tx.currency,
                tx.payment_method,
                tx.status,
                tx.scenario,
                tx.idempotency_key,
                tx.gateway_reference or "",
                tx.response_code,
                tx.failure_reason or "",
                tx.processing_duration_ms,
                tx.is_seeded,
                tx.created_at.isoformat(),
            ]
        )
    return buf.getvalue()


def export_tests_csv(db: Session) -> str:
    runs = db.scalars(select(TestRun).order_by(desc(TestRun.started_at))).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "run_id",
            "suite_name",
            "execution_status",
            "total_tests",
            "passed",
            "failed",
            "skipped",
            "pass_rate_percent",
            "code_coverage_percent",
            "duration_sec",
            "is_seeded",
            "started_at",
            "completed_at",
        ]
    )
    for r in runs:
        pass_rate = round((r.passed / r.total_tests) * 100.0, 2) if r.total_tests else 0.0
        writer.writerow(
            [
                r.run_id,
                r.suite_name,
                r.execution_status,
                r.total_tests,
                r.passed,
                r.failed,
                r.skipped,
                pass_rate,
                r.code_coverage if r.code_coverage is not None else "",
                round(r.duration, 3),
                r.is_seeded,
                r.started_at.isoformat(),
                r.completed_at.isoformat() if r.completed_at else "",
            ]
        )
    return buf.getvalue()

