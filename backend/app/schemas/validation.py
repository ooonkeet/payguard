"""Pydantic schemas for Database Validation Console."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class ValidationCheckDefinition(BaseModel):
    check_key: str
    check_name: str
    description: str
    category: str


class ValidationRunRequest(BaseModel):
    check_keys: Optional[List[str]] = None
    transaction_id: Optional[str] = None


class ValidationResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    check_key: str
    check_name: str
    execution_status: str
    records_examined: int
    issues_detected: int
    details: Optional[List[Dict[str, Any]]] = None
    execution_duration_ms: float
    executed_at: datetime


class ConsistencyReportOut(BaseModel):
    transaction_id: str
    consistent: bool
    api_response_status: Optional[str] = None
    db_status: Optional[str] = None
    latest_webhook_event: Optional[str] = None
    latest_webhook_status: Optional[str] = None
    final_payment_state: Optional[str] = None
    amount_consistent: bool
    discrepancies: List[str]
    details: Dict[str, Any]

