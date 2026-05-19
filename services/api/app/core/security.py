"""Password hashing + JWT helpers."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.settings import settings


# bcrypt's max input is 72 BYTES (not chars). Truncating UTF-8 by byte length
# is required for any string with multi-byte chars; we slice on bytes.
_BCRYPT_MAX_BYTES = 72
_BCRYPT_ROUNDS = 12   # work factor; 12 is the modern minimum


def _to_bcrypt_bytes(plain: str) -> bytes:
    """Encode + truncate at 72 bytes (bcrypt's hard limit)."""
    return plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]


# ────────────────────────────────────────────────────────────────────────
# Passwords
# ────────────────────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    """Hash a plaintext password. Returns the hash string suitable for DB storage."""
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return bcrypt.hashpw(_to_bcrypt_bytes(plain), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time verification. Returns False on any malformed input."""
    try:
        return bcrypt.checkpw(_to_bcrypt_bytes(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ────────────────────────────────────────────────────────────────────────
# Access tokens (JWT, short-lived, in-memory only on client)
# ────────────────────────────────────────────────────────────────────────
def create_access_token(*, subject: str, extra: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_ttl_minutes)).timestamp()),
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Returns the JWT payload or raises ValueError on any failure."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as e:
        raise ValueError(f"invalid token: {e}") from e
    if payload.get("type") != "access":
        raise ValueError("not an access token")
    return payload


# ────────────────────────────────────────────────────────────────────────
# Refresh tokens (random opaque strings, hashed in DB)
# ────────────────────────────────────────────────────────────────────────
def generate_refresh_token() -> str:
    """Returns a high-entropy URL-safe token. ~256 bits."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(raw: str) -> str:
    """SHA-256 hash for DB storage. Raw token never persisted."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
