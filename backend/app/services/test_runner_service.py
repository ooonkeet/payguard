"""Safe Pytest Automated Test Suite Execution Engine with Lock, Isolated Test DB, JUnit XML & HTML Reports."""

import json
import os
import subprocess
import sys
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import PROJECT_ROOT, REPORTS_DIR, get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import logger
from app.models.test_run import TestResult, TestRun
from app.schemas.test_run import AllowedTestSuite, TestResultOut, TestRunDetailOut, TestRunOut

# Prevent concurrent conflicting pytest executions against the dedicated test DB
_EXECUTION_LOCK = threading.Lock()

# Strict whitelist mapping — frontend NEVER supplies raw shell arguments or file paths
SUITE_PYTEST_ARGS: Dict[str, List[str]] = {
    AllowedTestSuite.ALL.value: ["tests/api", "tests/payment", "tests/webhooks", "tests/database", "tests/integration"],
    AllowedTestSuite.SMOKE.value: ["-m", "smoke", "tests/api", "tests/payment"],
    AllowedTestSuite.REGRESSION.value: ["-m", "regression", "tests/api", "tests/payment", "tests/integration"],
    AllowedTestSuite.EDGE_CASES.value: ["-m", "edge_case", "tests/payment", "tests/webhooks", "tests/integration"],
    AllowedTestSuite.API_CONTRACT.value: ["-m", "contract", "tests/api"],
    AllowedTestSuite.DATABASE.value: ["tests/database"],
}


def _compute_pass_rate(passed: int, total: int) -> float:
    return round((passed / total) * 100.0, 2) if total > 0 else 0.0


def _to_run_out(run: TestRun) -> TestRunOut:
    out = TestRunOut.model_validate(run)
    out.pass_rate = _compute_pass_rate(run.passed, run.total_tests)
    return out


def _parse_junit_xml(xml_path: Path) -> List[Dict[str, object]]:
    parsed: List[Dict[str, object]] = []
    if not xml_path.exists():
        return parsed

    tree = ET.parse(xml_path)
    root = tree.getroot()
    for testcase in root.iter("testcase"):
        classname = testcase.attrib.get("classname", "")
        name = testcase.attrib.get("name", "unknown_test")
        duration = float(testcase.attrib.get("time", "0.0") or 0.0)
        node_id = f"{classname}::{name}" if classname else name

        failure_el = testcase.find("failure")
        error_el = testcase.find("error")
        skipped_el = testcase.find("skipped")

        if failure_el is not None:
            status = "FAILED"
            msg = failure_el.attrib.get("message") or (failure_el.text or "").strip()
        elif error_el is not None:
            status = "FAILED"
            msg = error_el.attrib.get("message") or (error_el.text or "").strip()
        elif skipped_el is not None:
            status = "SKIPPED"
            msg = skipped_el.attrib.get("message") or (skipped_el.text or "").strip()
        else:
            status = "PASSED"
            msg = None

        parsed.append(
            {
                "test_name": name,
                "node_id": node_id,
                "test_status": status,
                "failure_message": msg[:2000] if msg else None,
                "duration": round(duration, 4),
            }
        )
    return parsed


def _parse_coverage_json(cov_json_path: Path) -> Optional[float]:
    if not cov_json_path.exists():
        return None
    try:
        data = json.loads(cov_json_path.read_text(encoding="utf-8"))
        totals = data.get("totals", {})
        percent = totals.get("percent_covered")
        return round(float(percent), 2) if percent is not None else None
    except Exception:
        return None


def execute_test_suite(db: Session, suite: AllowedTestSuite, with_coverage: bool = True) -> TestRunDetailOut:
    """Execute a whitelisted Pytest suite in an isolated subprocess and persist results."""
    if not _EXECUTION_LOCK.acquire(blocking=False):
        raise ConflictError(
            "Another automated test suite is currently executing. Wait for it to finish before starting a new run."
        )

    settings = get_settings()
    run_id = f"RUN-{uuid.uuid4().hex[:10].upper()}"
    started_at = datetime.now(timezone.utc)

    run_record = TestRun(
        run_id=run_id,
        suite_name=suite.value,
        total_tests=0,
        passed=0,
        failed=0,
        skipped=0,
        duration=0.0,
        code_coverage=None,
        execution_status="RUNNING",
        report_path=None,
        stdout_summary=None,
        is_seeded=False,
        started_at=started_at,
        completed_at=None,
    )
    db.add(run_record)
    db.commit()
    db.refresh(run_record)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    html_report_file = REPORTS_DIR / f"{run_id}_{suite.value}.html"
    junit_xml_file = REPORTS_DIR / f"{run_id}_{suite.value}_junit.xml"
    cov_json_file = REPORTS_DIR / f"{run_id}_{suite.value}_cov.json"

    try:
        pytest_targets = SUITE_PYTEST_ARGS[suite.value]
        cmd: List[str] = [
            sys.executable,
            "-m",
            "pytest",
            *pytest_targets,
            f"--junitxml={junit_xml_file}",
            f"--html={html_report_file}",
            "--self-contained-html",
            "-v",
            "--tb=short",
        ]
        if with_coverage:
            cmd.extend(["--cov=backend/app", f"--cov-report=json:{cov_json_file}"])

        env = os.environ.copy()
        env["DATABASE_URL"] = settings.TEST_DATABASE_URL
        env["TEST_DATABASE_URL"] = settings.TEST_DATABASE_URL
        env["PYTHONPATH"] = str(PROJECT_ROOT / "backend")
        env["PAYGUARD_FAST_SIMULATION"] = "1"

        t0 = time.perf_counter()
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        wall_duration = round(time.perf_counter() - t0, 3)

        cases = _parse_junit_xml(junit_xml_file)
        coverage_pct = _parse_coverage_json(cov_json_file) if with_coverage else None

        passed = sum(1 for c in cases if c["test_status"] == "PASSED")
        failed = sum(1 for c in cases if c["test_status"] == "FAILED")
        skipped = sum(1 for c in cases if c["test_status"] == "SKIPPED")
        total = len(cases)

        # Exit code 0 = all passed, 1 = some tests failed, 5 = no tests collected
        if total == 0 and proc.returncode not in (0, 5):
            exec_status = "ERROR"
        elif failed > 0:
            exec_status = "FAILED"
        else:
            exec_status = "PASSED"

        combined_output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        run_record.total_tests = total
        run_record.passed = passed
        run_record.failed = failed
        run_record.skipped = skipped
        run_record.duration = wall_duration
        run_record.code_coverage = coverage_pct
        run_record.execution_status = exec_status
        run_record.report_path = html_report_file.name if html_report_file.exists() else None
        run_record.stdout_summary = combined_output[-4000:]
        run_record.completed_at = datetime.now(timezone.utc)

        result_models: List[TestResult] = []
        for c in cases:
            tr = TestResult(
                run_id=run_id,
                test_name=str(c["test_name"]),
                node_id=str(c["node_id"]),
                test_status=str(c["test_status"]),
                failure_message=c["failure_message"],  # type: ignore[arg-type]
                duration=float(c["duration"]),  # type: ignore[arg-type]
                created_at=datetime.now(timezone.utc),
            )
            db.add(tr)
            result_models.append(tr)

        db.commit()
        db.refresh(run_record)
        for tr in result_models:
            db.refresh(tr)

        logger.info(
            "Automated test suite finished",
            extra={
                "extra_data": {
                    "run_id": run_id,
                    "suite": suite.value,
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "duration": wall_duration,
                }
            },
        )

        detail = TestRunDetailOut.model_validate(run_record)
        detail.pass_rate = _compute_pass_rate(run_record.passed, run_record.total_tests)
        detail.results = [TestResultOut.model_validate(tr) for tr in result_models]
        return detail

    except subprocess.TimeoutExpired:
        run_record.execution_status = "TIMEOUT"
        run_record.stdout_summary = "Pytest execution exceeded the 180-second safety timeout."
        run_record.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run_record)
        detail = TestRunDetailOut.model_validate(run_record)
        detail.results = []
        return detail
    finally:
        # Clean up temporary XML/JSON intermediates while keeping HTML reports
        for temp_path in (junit_xml_file, cov_json_file):
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
        _EXECUTION_LOCK.release()


def list_test_runs(db: Session, suite_name: Optional[str] = None, limit: int = 50) -> List[TestRunOut]:
    stmt = select(TestRun)
    if suite_name and suite_name != "ALL":
        stmt = stmt.where(TestRun.suite_name == suite_name)
    rows = db.scalars(stmt.order_by(desc(TestRun.started_at), desc(TestRun.id)).limit(limit)).all()
    return [_to_run_out(r) for r in rows]


def get_test_run(db: Session, run_id: str) -> TestRunDetailOut:
    run = db.scalar(select(TestRun).where(TestRun.run_id == run_id))
    if run is None:
        raise NotFoundError("TestRun", run_id)
    results = db.scalars(
        select(TestResult).where(TestResult.run_id == run_id).order_by(TestResult.id)
    ).all()
    detail = TestRunDetailOut.model_validate(run)
    detail.pass_rate = _compute_pass_rate(run.passed, run.total_tests)
    detail.results = [TestResultOut.model_validate(r) for r in results]
    return detail


def get_test_run_results(db: Session, run_id: str) -> List[TestResultOut]:
    run = db.scalar(select(TestRun).where(TestRun.run_id == run_id))
    if run is None:
        raise NotFoundError("TestRun", run_id)
    results = db.scalars(
        select(TestResult).where(TestResult.run_id == run_id).order_by(TestResult.id)
    ).all()
    return [TestResultOut.model_validate(r) for r in results]


def get_report_file_path(db: Session, run_id: str) -> Path:
    run = db.scalar(select(TestRun).where(TestRun.run_id == run_id))
    if run is None:
        raise NotFoundError("TestRun", run_id)
    if not run.report_path:
        raise NotFoundError("HTML Report", run_id)
    # Prevent path traversal by resolving strictly inside REPORTS_DIR
    candidate = (REPORTS_DIR / Path(run.report_path).name).resolve()
    if not candidate.exists() or REPORTS_DIR.resolve() not in candidate.parents:
        raise NotFoundError("HTML Report file", run_id)
    return candidate

