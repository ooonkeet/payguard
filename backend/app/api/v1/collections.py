"""API Testing Console Collections & Safe Local Request Executor."""

import json
import time
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.exceptions import PayGuardException
from app.core.security import canonical_payload_bytes, compute_webhook_signature
from app.database.session import get_db
from app.schemas.api_collection import (
    ApiCollectionCreateRequest,
    ApiCollectionUpdateRequest,
    ApiConsoleExecuteRequest,
)
from app.services import collection_service

router = APIRouter(prefix="/api/v1/collections", tags=["API Console"])


@router.get("")
def list_collections(db: Session = Depends(get_db)) -> dict:
    items = collection_service.list_collections(db)
    return {"success": True, "data": [c.model_dump(mode="json") for c in items]}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_collection(payload: ApiCollectionCreateRequest, db: Session = Depends(get_db)) -> dict:
    item = collection_service.create_collection(db, payload)
    return {"success": True, "data": item.model_dump(mode="json")}


@router.put("/{collection_id}")
def update_collection(
    collection_id: int, payload: ApiCollectionUpdateRequest, db: Session = Depends(get_db)
) -> dict:
    item = collection_service.update_collection(db, collection_id, payload)
    return {"success": True, "data": item.model_dump(mode="json")}


@router.delete("/{collection_id}")
def delete_collection(collection_id: int, db: Session = Depends(get_db)) -> dict:
    collection_service.delete_collection(db, collection_id)
    return {"success": True, "data": {"deleted": collection_id}}


@router.post("/execute")
async def execute_console_request(payload: ApiConsoleExecuteRequest, request: Request) -> dict:
    """
    Execute an API console request directly against this PayGuard backend via ASGI transport.
    Restricts target paths to local PayGuard routes (/api/... or /health) to prevent SSRF,
    and optionally attaches a server-computed HMAC-SHA256 webhook signature so secrets never leak to the browser.
    """
    raw_endpoint = payload.endpoint.strip()
    if raw_endpoint.startswith("http://") or raw_endpoint.startswith("https://"):
        parsed = urlparse(raw_endpoint)
        if parsed.hostname not in ("localhost", "127.0.0.1"):
            raise PayGuardException(
                message="API Console only allows requests targeting the local PayGuard backend.",
                code="DISALLOWED_TARGET_HOST",
                status_code=400,
            )
        target_path = parsed.path or "/"
    else:
        target_path = raw_endpoint if raw_endpoint.startswith("/") else f"/{raw_endpoint}"

    if not (target_path.startswith("/api/") or target_path == "/health"):
        raise PayGuardException(
            message="Target endpoint must start with '/api/' or '/health'.",
            code="DISALLOWED_TARGET_PATH",
            status_code=400,
        )

    headers = {str(k): str(v) for k, v in payload.headers.items() if str(k).strip()}
    content_bytes: bytes | None = None

    if payload.body is not None and payload.method in ("POST", "PUT", "PATCH"):
        if isinstance(payload.body, (dict, list)):
            content_bytes = canonical_payload_bytes(payload.body) if isinstance(payload.body, dict) else json.dumps(payload.body).encode("utf-8")
        else:
            content_bytes = str(payload.body).encode("utf-8")
        if "content-type" not in {k.lower() for k in headers}:
            headers["Content-Type"] = "application/json"

        if payload.sign_webhook:
            headers["X-PayGuard-Signature"] = f"sha256={compute_webhook_signature(content_bytes)}"
        elif payload.invalid_signature:
            headers["X-PayGuard-Signature"] = "sha256=deadbeef00000000000000000000000000000000000000000000000000000000"

    t0 = time.perf_counter()
    transport = httpx.ASGITransport(app=request.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://payguard.local") as client:
        resp = await client.request(
            method=payload.method,
            url=target_path,
            headers=headers,
            params={k: v for k, v in payload.query_params.items() if k.strip()},
            content=content_bytes,
        )
    duration_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    try:
        resp_body = resp.json()
    except Exception:
        resp_body = resp.text

    return {
        "success": True,
        "data": {
            "status_code": resp.status_code,
            "reason_phrase": resp.reason_phrase,
            "duration_ms": duration_ms,
            "headers": dict(resp.headers),
            "body": resp_body,
            "request_path": target_path,
            "method": payload.method,
        },
    }

