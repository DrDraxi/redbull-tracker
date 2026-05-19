"""Bearer-token + signed-cookie auth helpers."""

from __future__ import annotations

import hmac

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

COOKIE_NAME = "redbull_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days
_COOKIE_PAYLOAD = "authed"


def check_bearer(authorization_header: str | None, *, expected: str) -> bool:
    """Constant-time bearer token check."""
    if not authorization_header:
        return False
    parts = authorization_header.split(" ", 1)
    if len(parts) != 2 or parts[0] != "Bearer":
        return False
    return hmac.compare_digest(parts[1], expected)


def make_cookie_value(secret: str) -> str:
    """Generate a signed cookie payload."""
    return URLSafeTimedSerializer(secret).dumps(_COOKIE_PAYLOAD)


def check_cookie(value: str | None, *, secret: str, max_age_seconds: int) -> bool:
    """Validate a signed cookie. False on missing, tampered, or expired."""
    if not value:
        return False
    try:
        payload = URLSafeTimedSerializer(secret).loads(value, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return False
    return payload == _COOKIE_PAYLOAD
