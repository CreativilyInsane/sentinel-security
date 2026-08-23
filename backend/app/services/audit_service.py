# backend/app/services/audit_service.py
"""Thin wrapper around the existing AuditLog model.

The Basir codebase already has an ``AuditLog`` table and global exception
handler, but no service for actually writing audit entries.  Recon events
(SCAN_CREATED, ASSET_DISCOVERED, …) flow through this service.
"""
from __future__ import annotations

from typing import Any, Optional, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.core.logging import logger


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        *,
        user_id: Optional[int],
        action: str,
        resource: str,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persist an audit log entry.

        Failures here are intentionally swallowed — audit logging must not
        break the request flow.  Errors are logged via the application
        logger so an operator can investigate.
        """
        try:
            entry = AuditLog(
                user_id=user_id,
                action=action,
                resource=resource,
                ip_address=ip_address,
                details=details or {},
            )
            self.db.add(entry)
            await self.db.flush()
        except Exception as exc:  # noqa: BLE001 — we explicitly want to swallow
            logger.error(f"Audit log write failed: {exc} action={action} resource={resource}")
