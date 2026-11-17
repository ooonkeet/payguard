"""Pydantic schemas for API Testing Console Collections."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ApiRequestItem(BaseModel):
    id: str
    name: str
    method: str = Field(..., pattern="^(GET|POST|PUT|PATCH|DELETE)$")
    endpoint: str
    headers: Dict[str, str] = Field(default_factory=dict)
    query_params: Dict[str, str] = Field(default_factory=dict)
    body: Optional[Any] = None
    description: Optional[str] = None
    sign_webhook: bool = False
    invalid_signature: bool = False


class ApiCollectionCreateRequest(BaseModel):
    collection_name: str = Field(..., min_length=2, max_length=128)
    description: Optional[str] = None
    requests: List[ApiRequestItem] = Field(default_factory=list)


class ApiCollectionUpdateRequest(BaseModel):
    collection_name: Optional[str] = Field(default=None, min_length=2, max_length=128)
    description: Optional[str] = None
    requests: Optional[List[ApiRequestItem]] = None


class ApiCollectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    collection_name: str
    description: Optional[str] = None
    configuration: Dict[str, Any]
    is_seeded: bool
    created_at: datetime
    updated_at: datetime


class ApiConsoleExecuteRequest(BaseModel):
    method: str = Field(..., pattern="^(GET|POST|PUT|PATCH|DELETE)$")
    endpoint: str = Field(..., min_length=1)
    headers: Dict[str, str] = Field(default_factory=dict)
    query_params: Dict[str, str] = Field(default_factory=dict)
    body: Optional[Any] = None
    sign_webhook: bool = False
    invalid_signature: bool = False

