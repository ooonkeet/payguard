"""Standardized application exceptions and FastAPI exception handlers."""

from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import logger


class PayGuardException(Exception):
    """Base domain exception with standardized error envelope."""

    def __init__(
        self,
        message: str,
        code: str = "PAYGUARD_ERROR",
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class IdempotencyConflictError(PayGuardException):
    def __init__(self, idempotency_key: str, existing_transaction_id: str) -> None:
        super().__init__(
            message=(
                f"Idempotency conflict: key '{idempotency_key}' was already used with a "
                "different payment payload."
            ),
            code="IDEMPOTENCY_CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "idempotency_key": idempotency_key,
                "existing_transaction_id": existing_transaction_id,
            },
        )


class InvalidStateTransitionError(PayGuardException):
    def __init__(self, current_status: str, target_status: str) -> None:
        super().__init__(
            message=f"Invalid payment state transition: {current_status} -> {target_status}",
            code="INVALID_STATE_TRANSITION",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"current_status": current_status, "target_status": target_status},
        )


class NotFoundError(PayGuardException):
    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            message=f"{resource} '{identifier}' was not found.",
            code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource": resource, "identifier": identifier},
        )


class ConflictError(PayGuardException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(PayGuardException)
    async def payguard_exception_handler(request: Request, exc: PayGuardException) -> JSONResponse:
        logger.warning(
            exc.message,
            extra={"extra_data": {"code": exc.code, "path": str(request.url.path), "details": exc.details}},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                },
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = []
        for err in exc.errors():
            errors.append(
                {
                    "field": ".".join(str(loc) for loc in err.get("loc", [])),
                    "message": err.get("msg", "Invalid value"),
                    "type": err.get("type", "validation_error"),
                }
            )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed.",
                    "details": {"errors": errors},
                },
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            f"Unhandled server error on {request.url.path}: {exc}",
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected internal error occurred.",
                    "details": {},
                },
            },
        )

