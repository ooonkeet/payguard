"""Pydantic schemas for Bug / Defect Tracker."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BugSeverity(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class BugPriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class BugStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    FIXED = "FIXED"
    VERIFIED = "VERIFIED"
    CLOSED = "CLOSED"


class BugCreateRequest(BaseModel):
    title: str = Field(..., min_length=4, max_length=200)
    description: str = Field(..., min_length=4)
    severity: BugSeverity = BugSeverity.MEDIUM
    priority: BugPriority = BugPriority.P2
    module: str = Field(default="Payment Simulator", min_length=2, max_length=64)
    reproduction_steps: Optional[str] = None
    expected_result: Optional[str] = None
    actual_result: Optional[str] = None
    environment: str = Field(default="SANDBOX", max_length=64)
    transaction_id: Optional[str] = None
    associated_test_case: Optional[str] = None


class BugUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=4, max_length=200)
    description: Optional[str] = Field(default=None, min_length=4)
    severity: Optional[BugSeverity] = None
    priority: Optional[BugPriority] = None
    status: Optional[BugStatus] = None
    module: Optional[str] = Field(default=None, min_length=2, max_length=64)
    reproduction_steps: Optional[str] = None
    expected_result: Optional[str] = None
    actual_result: Optional[str] = None
    environment: Optional[str] = Field(default=None, max_length=64)
    transaction_id: Optional[str] = None
    associated_test_case: Optional[str] = None


class BugOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bug_id: str
    title: str
    description: str
    severity: str
    priority: str
    status: str
    module: str
    reproduction_steps: Optional[str] = None
    expected_result: Optional[str] = None
    actual_result: Optional[str] = None
    environment: str
    transaction_id: Optional[str] = None
    associated_test_case: Optional[str] = None
    is_seeded: bool
    created_at: datetime
    updated_at: datetime

