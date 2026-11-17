"""Pydantic schemas for Automated Test Suite Execution."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class AllowedTestSuite(str, Enum):
    ALL = "all"
    SMOKE = "smoke"
    REGRESSION = "regression"
    EDGE_CASES = "edge_cases"
    API_CONTRACT = "api_contract"
    DATABASE = "database"


class TestRunRequest(BaseModel):
    suite_name: AllowedTestSuite = AllowedTestSuite.SMOKE
    with_coverage: bool = True


class TestResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    test_name: str
    node_id: Optional[str] = None
    test_status: str
    failure_message: Optional[str] = None
    duration: float
    created_at: datetime


class TestRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: str
    suite_name: str
    total_tests: int
    passed: int
    failed: int
    skipped: int
    duration: float
    code_coverage: Optional[float] = None
    execution_status: str
    report_path: Optional[str] = None
    stdout_summary: Optional[str] = None
    is_seeded: bool
    started_at: datetime
    completed_at: Optional[datetime] = None
    pass_rate: float = 0.0


class TestRunDetailOut(TestRunOut):
    results: List[TestResultOut] = []

