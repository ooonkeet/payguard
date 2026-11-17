"""Common response envelopes and pagination schemas."""

from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
    meta: Optional[dict[str, Any]] = None


class PaginatedResponse(BaseModel, Generic[T]):
    success: bool = True
    data: List[T]
    pagination: PaginationMeta

