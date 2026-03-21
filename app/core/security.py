from __future__ import annotations

import hashlib
import hmac
import uuid


def sign_session_token(*, user_id: uuid.UUID, secret: str) -> str:
    payload = user_id.hex
    signature = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_session_token(token: str | None, *, secret: str) -> uuid.UUID | None:
    if token is None:
        return None

    payload, separator, signature = token.partition(".")
    if not payload or separator == "" or not signature:
        return None

    expected_signature = hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        return uuid.UUID(hex=payload)
    except ValueError:
        return None
