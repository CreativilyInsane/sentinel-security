# backend/app/services/report_token_service.py
"""Short-lived signed report URL tokens.

When the frontend wants to open an HTML/PDF report in a new browser tab
(or iframe), the JWT cannot be attached to the request because the
browser does not allow setting custom headers on a top-level navigation.
Instead, the frontend calls ``POST /api/v1/recon/clients/{id}/report/token``
(or the scan-level equivalent) to obtain a short-lived signed URL
token, then opens ``/api/v1/recon/clients/{id}/report/html?token=…``.

The token:
  * is a JWT signed with the same ``SECRET_KEY`` used for auth tokens,
  * has a short TTL (default 5 minutes),
  * encodes ``user_id``, ``client_id`` (or ``scan_id``), and
    ``format`` (``html``/``pdf``),
  * is single-use: its ``jti`` is recorded in a Redis set with the
    same TTL, and the report endpoint rejects a token whose ``jti`` has
    already been consumed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from jose import jwt, JWTError

from app.core.config import settings
from app.db.redis import redis_client
from app.utils.errors import UnauthorizedError


REPORT_TOKEN_TTL_SECONDS = 300  # 5 minutes
REPORT_TOKEN_TYPE = "report"


class ReportTokenService:
    """Issue and consume short-lived signed report tokens."""

    @staticmethod
    def issue(
        *,
        user_id: int,
        client_id: Optional[int] = None,
        scan_id: Optional[int] = None,
        fmt: str = "html",
        ttl: int = REPORT_TOKEN_TTL_SECONDS,
    ) -> str:
        """Issue a signed JWT authorising the bearer to view the report
        for ``client_id`` or ``scan_id`` in format ``fmt`` (``html`` or
        ``pdf``).  Returns the encoded JWT string.
        """
        now = datetime.now(timezone.utc)
        jti = str(uuid.uuid4())
        payload = {
            "sub": str(user_id),
            "type": REPORT_TOKEN_TYPE,
            "jti": jti,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=ttl)).timestamp()),
            "user_id": user_id,
            "format": fmt,
        }
        if client_id is not None:
            payload["client_id"] = client_id
        if scan_id is not None:
            payload["scan_id"] = scan_id
        # NOTE: the project's Settings class uses ``JWT_SECRET_KEY`` and
        # ``JWT_ALGORITHM`` (NOT ``SECRET_KEY`` / ``ALGORITHM``).  Using
        # the wrong names here causes AttributeError at runtime.
        return jwt.encode(
            payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM,
        )

    @staticmethod
    async def consume(token: str) -> dict:
        """Validate the token, ensure it has not already been used, and
        mark it as consumed.  Returns the decoded payload.

        Raises ``UnauthorizedError`` if the token is invalid, expired,
        or already consumed.
        """
        try:
            payload = jwt.decode(
                token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM],
            )
        except JWTError as exc:
            raise UnauthorizedError(f"Invalid report token: {exc}")

        if payload.get("type") != REPORT_TOKEN_TYPE:
            raise UnauthorizedError("Not a report token.")

        jti = payload.get("jti")
        if not jti:
            raise UnauthorizedError("Report token missing jti.")

        # Single-use enforcement: atomically check-and-set in Redis.
        redis_key = f"report_token_used:{jti}"
        # ``set`` with ``nx=True`` returns True only if the key did not
        # exist before.  If it returns None, the token has already been
        # consumed.
        acquired = await redis_client.set(redis_key, "1", ex=REPORT_TOKEN_TTL_SECONDS, nx=True)
        if not acquired:
            raise UnauthorizedError("Report token has already been used.")

        return payload
