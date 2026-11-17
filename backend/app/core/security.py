"""Security utilities: HMAC-SHA256 webhook verification & synthetic auth checks."""

import hashlib
import hmac
import json
from typing import Any, Dict

from app.core.config import get_settings


def canonical_payload_bytes(payload: Dict[str, Any]) -> bytes:
    """Serialize JSON deterministically for hashing and HMAC verification."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def compute_payload_hash(payload: Dict[str, Any]) -> str:
    """Compute SHA-256 hash of a normalized request payload for idempotency checks."""
    return hashlib.sha256(canonical_payload_bytes(payload)).hexdigest()


def compute_webhook_signature(raw_body: bytes, secret: str | None = None) -> str:
    """Compute hex HMAC-SHA256 signature for webhook payload."""
    signing_secret = secret if secret is not None else get_settings().WEBHOOK_SECRET
    return hmac.new(
        signing_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()


def verify_webhook_signature(raw_body: bytes, provided_signature: str | None, secret: str | None = None) -> bool:
    """Constant-time HMAC-SHA256 verification supporting optional 'sha256=' prefix."""
    if not provided_signature:
        return False
    normalized = provided_signature.strip()
    if normalized.lower().startswith("sha256="):
        normalized = normalized[7:]
    expected = compute_webhook_signature(raw_body, secret=secret)
    return hmac.compare_digest(expected, normalized)

