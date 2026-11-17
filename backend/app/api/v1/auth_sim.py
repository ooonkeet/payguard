"""Sandbox Authentication Verification Endpoint for API Testing Console Collection 2."""

import hmac
from typing import Optional

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from app.core.config import get_settings

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication Testing"])


@router.get("/verify")
def verify_sandbox_auth(authorization: Optional[str] = Header(default=None)) -> JSONResponse:
    settings = get_settings()
    if not authorization or not authorization.strip():
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": {
                    "code": "MISSING_AUTH_TOKEN",
                    "message": "Authorization header with Bearer token is required.",
                    "details": {},
                },
            },
        )

    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": {
                    "code": "MALFORMED_AUTH_HEADER",
                    "message": "Authorization header must follow 'Bearer <token>' format.",
                    "details": {},
                },
            },
        )

    token = parts[1].strip()
    if hmac.compare_digest(token, settings.EXPIRED_AUTH_TOKEN):
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": {
                    "code": "TOKEN_EXPIRED",
                    "message": "Provided sandbox API token has expired.",
                    "details": {},
                },
            },
        )

    if not hmac.compare_digest(token, settings.API_AUTH_TOKEN):
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "error": {
                    "code": "INVALID_AUTH_TOKEN",
                    "message": "Provided sandbox API token is invalid.",
                    "details": {},
                },
            },
        )

    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "data": {
                "authenticated": True,
                "principal": "qa-automation-engineer@payguard.sandbox",
                "role": "QA_ENGINEER",
                "environment": settings.APP_ENV,
                "scopes": ["payments:simulate", "tests:execute", "webhooks:verify", "validation:read"],
            },
        },
    )

