# backend/app/api/v1/endpoints/recon.py
"""HTTP API for the Basir recon module.

All endpoints require authentication via the existing ``get_current_user``
dependency.  Per-user ownership is enforced by ``ScanService`` /
``AssetService`` — admins (role == ``Administrator``) bypass ownership
checks via the ``is_admin`` flag derived from the existing RBAC system.
"""
from __future__ import annotations

import os
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_or_none
from app.core.constants import Roles, OwnershipType, ModulePermission, ScanStatus
from app.core.logging import logger
from app.db.session import get_db
from app.models.user import User
from app.recon.asset_service import AssetService
from app.recon.schemas.scan import (
    ScanCreate, ScanRead, ScanSummary, ScanListFilters, CancelResponse,
)
from app.recon.schemas.result import ScanResultRead, ScanResultGrouped
from app.recon.schemas.asset import AssetRead, AssetListFilters
from app.recon.services.report_service import ReportService
from app.recon.services.scan_service import ScanService
from app.recon.workers.tasks import run_scan
from app.schemas.common import StandardResponse, PaginatedResponse
from app.utils.errors import NotFoundError, BadRequestError, ForbiddenError
from app.services.audit_service import AuditService
from app.services.module_permission_service import ModulePermissionService
from app.core.constants import AuditAction


router = APIRouter()


def _is_admin(user: User) -> bool:
    return bool(user.role and user.role.name == Roles.ADMIN)


async def _require_module(db: AsyncSession, user: User, module_name: str) -> None:
    """Raise ForbiddenError if the user does not have ``module_name``.

    Admins always pass.
    """
    if _is_admin(user):
        return
    svc = ModulePermissionService(db)
    allowed = await svc.is_allowed(user, module_name)
    if not allowed:
        raise ForbiddenError(
            f"You do not have permission to use the '{module_name}' module. "
            f"Contact an administrator."
        )


def _client_ip(request: Request) -> Optional[str]:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


# ===========================================================================
# Scan CRUD
# ===========================================================================
@router.post(
    "/scans",
    response_model=StandardResponse[ScanRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_scan(
    payload: ScanCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new reconnaissance scan and queue it for execution."""
    service = ScanService(db)
    scan = await service.create_scan(
        user_id=current_user.id,
        payload=payload,
        ip_address=_client_ip(request),
        user=current_user,
    )
    # Dispatch the Celery task — fire-and-forget; the worker owns execution.
    module_status_rows: list = []
    try:
        task = run_scan.delay(scan.id)
        # Persist the celery task id so the UI can show it (and operators can
        # inspect the worker logs).
        from app.recon.repositories.scan_repository import ScanRepository, ScanModuleStatusRepository
        repo = ScanRepository(db)
        await repo.set_celery_task_id(scan.id, task.id)
        await db.commit()
        # Re-fetch so the response includes celery_task_id.  Use the
        # eager-loading variant so we don't trigger a lazy-load when
        # building ScanRead.
        scan = await repo.get_scan_with_results(scan.id)
        if scan is None:
            scan = await repo.get_by_id(scan.id)
        # Fetch the per-module status rows explicitly (they were created
        # by ScanService.create_scan via init_for_scan).
        ms_repo = ScanModuleStatusRepository(db)
        module_status_rows = await ms_repo.list_for_scan(scan.id)
    except Exception as exc:  # noqa: BLE001
        # If Celery broker is unreachable we still keep the scan row but mark
        # it as failed so the user sees a clear error.
        logger.error(f"Failed to enqueue Celery task for scan {scan.id}: {exc}")
        from app.recon.repositories.scan_repository import ScanRepository, ScanModuleStatusRepository
        from app.core.constants import ScanStatus
        from datetime import datetime, timezone
        repo = ScanRepository(db)
        await repo.update_status(
            scan.id,
            status=ScanStatus.FAILED,
            error_message=f"Failed to enqueue scan task: {exc}",
            completed_at=datetime.now(timezone.utc),
        )
        await db.commit()
        scan = await repo.get_scan_with_results(scan.id)
        if scan is None:
            scan = await repo.get_by_id(scan.id)
        ms_repo = ScanModuleStatusRepository(db)
        module_status_rows = await ms_repo.list_for_scan(scan.id)
    return StandardResponse(
        success=True, message="Scan created and queued.",
        data=ScanRead.from_scan(scan, module_statuses=module_status_rows),
    )


@router.get(
    "/scans",
    response_model=StandardResponse[List[ScanSummary]],
    status_code=status.HTTP_200_OK,
)
async def list_scans(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: Optional[str] = Query(None, alias="status"),
    target: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the authenticated user's scans (admins see all)."""
    service = ScanService(db)
    is_admin = _is_admin(current_user)
    if is_admin:
        scans = await service.list_all_scans(
            skip=skip, limit=limit, status_filter=status_filter, target_filter=target,
        )
    else:
        scans = await service.list_user_scans(
            current_user.id, skip=skip, limit=limit,
            status_filter=status_filter, target_filter=target,
        )
    # Batch-fetch usernames so the Reports page can show "Generated by".
    from app.repositories.user_repository import UserRepository
    user_repo = UserRepository(db)
    user_cache: dict[int, str] = {}
    for s in scans:
        if s.user_id not in user_cache:
            u = await user_repo.get_user_with_role(s.user_id)
            user_cache[s.user_id] = u.username if u else f"User #{s.user_id}"
    data = []
    for s in scans:
        summary = ScanSummary.model_validate(s)
        summary.user_username = user_cache.get(s.user_id)
        data.append(summary)
    return StandardResponse(success=True, message="Scans retrieved.", data=data)


@router.get(
    "/scans/{scan_id}",
    response_model=StandardResponse[ScanRead],
    status_code=status.HTTP_200_OK,
)
async def get_scan(
    scan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a single scan with its results + module statuses eager-loaded."""
    service = ScanService(db)
    scan = await service.get_scan(
        scan_id, user_id=current_user.id, is_admin=_is_admin(current_user),
    )
    return StandardResponse(success=True, message="Scan retrieved.", data=ScanRead.from_scan(scan))


@router.get(
    "/scans/{scan_id}/events",
    status_code=status.HTTP_200_OK,
)
async def scan_events(
    scan_id: int,
    request: Request,
    token: Optional[str] = Query(None, description="JWT access token (for EventSource which cannot set headers)"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_or_none),
):
    """Server-Sent Events stream for real-time scan + module status updates.

    The browser subscribes via ``new EventSource('/api/v1/recon/scans/{id}/events?token=…')``
    and receives named events:

        * snapshot        (initial state)
        * scan_created
        * scan_started
        * module_started
        * module_completed
        * module_failed
        * scan_completed
        * scan_cancelled
        * scan_failed

    Each event carries a JSON payload describing the change.  The endpoint
    also sends an initial ``snapshot`` event with the current scan row +
    module_statuses so a freshly-opened page can render immediately without
    waiting for the first pub/sub message.

    The connection auto-closes after the scan reaches a terminal state.

    Auth: EventSource cannot set custom headers, so we accept the JWT
    access token as a ``?token=`` query parameter as a fallback when
    the Authorization header is absent.
    """
    import asyncio
    import json
    from sse_starlette.sse import EventSourceResponse
    from app.db.redis import redis_client
    from app.recon.repositories.scan_repository import ScanRepository, ScanModuleStatusRepository
    from app.api.deps import get_current_user
    from app.services.token_service import TokenService
    from app.core.constants import TokenType
    from app.utils.errors import ForbiddenError

    # If no Authorization header was sent, try the ?token= query param.
    user = current_user
    if user is None and token:
        try:
            token_service = TokenService()
            payload = await token_service.validate_token(token, TokenType.ACCESS)
            uid = payload.get("user_id")
            if uid:
                from app.repositories.user_repository import UserRepository
                user_repo = UserRepository(db)
                user = await user_repo.get_user_with_role(int(uid))
                if user and not user.is_active:
                    user = None
        except Exception:
            user = None
    if user is None:
        raise ForbiddenError("Not authenticated.")

    # Authorise: same rule as get_scan.
    service = ScanService(db)
    scan = await service.get_scan(
        scan_id, user_id=user.id, is_admin=_is_admin(user),
    )

    scan_repo = ScanRepository(db)
    module_status_repo = ScanModuleStatusRepository(db)
    channel = f"scan_events:{scan_id}"

    async def event_generator():
        # Send an initial snapshot of the current state.
        try:
            fresh = await scan_repo.get_scan_with_results(scan_id)
            if fresh:
                statuses = await module_status_repo.list_for_scan(scan_id)
                snapshot = {
                    "scan_id": scan_id,
                    "scan": {
                        "id": fresh.id,
                        "status": fresh.status,
                        "progress": fresh.progress,
                        "started_at": fresh.started_at.isoformat() if fresh.started_at else None,
                        "completed_at": fresh.completed_at.isoformat() if fresh.completed_at else None,
                        "error_message": fresh.error_message,
                        "modules": list(fresh.modules or []),
                    },
                    "module_statuses": [
                        {
                            "module_name": ms.module_name,
                            "status": ms.status,
                            "progress": ms.progress,
                            "error_message": ms.error_message,
                            "started_at": ms.started_at.isoformat() if ms.started_at else None,
                            "completed_at": ms.completed_at.isoformat() if ms.completed_at else None,
                        }
                        for ms in statuses
                    ],
                }
                yield {"event": "snapshot", "data": json.dumps(snapshot)}
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"SSE snapshot failed for scan {scan_id}: {exc}")

        # If the scan is already terminal, close the stream after the snapshot.
        if scan.status in {ScanStatus.COMPLETED, ScanStatus.FAILED, ScanStatus.CANCELLED}:
            return

        # Subscribe to Redis pub/sub for live events.
        try:
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(channel)
            try:
                while True:
                    # Check for client disconnect.
                    if await request.is_disconnected():
                        break

                    # Re-check scan status; if terminal, drain pending
                    # messages and close.
                    fresh = await scan_repo.get_by_id(scan_id)
                    if fresh and fresh.status in {
                        ScanStatus.COMPLETED, ScanStatus.FAILED, ScanStatus.CANCELLED,
                    }:
                        # Drain any final messages.
                        while True:
                            msg = await pubsub.get_message(
                                ignore_subscribe_messages=True, timeout=0.5,
                            )
                            if msg is None:
                                break
                            if msg.get("type") == "message":
                                data = msg.get("data")
                                if isinstance(data, bytes):
                                    data = data.decode("utf-8", errors="ignore")
                                try:
                                    parsed = json.loads(data)
                                    yield {
                                        "event": parsed.get("event", "message"),
                                        "data": json.dumps(parsed.get("payload", parsed)),
                                    }
                                except Exception:
                                    yield {"event": "message", "data": str(data)}
                        break

                    # Poll for the next message with a short timeout.
                    msg = await pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=1.0,
                    )
                    if msg is None:
                        # Yield a no-op comment to keep the connection alive.
                        yield {"comment": "keepalive"}
                        continue
                    if msg.get("type") != "message":
                        continue
                    data = msg.get("data")
                    if isinstance(data, bytes):
                        data = data.decode("utf-8", errors="ignore")
                    try:
                        parsed = json.loads(data)
                        yield {
                            "event": parsed.get("event", "message"),
                            "data": json.dumps(parsed.get("payload", parsed)),
                        }
                    except Exception:
                        yield {"event": "message", "data": str(data)}
            finally:
                try:
                    await pubsub.unsubscribe(channel)
                    await pubsub.close()
                except Exception:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"SSE stream for scan {scan_id} ended: {exc}")

    return EventSourceResponse(event_generator())


@router.get(
    "/scans/{scan_id}/results",
    response_model=StandardResponse[ScanResultGrouped],
    status_code=status.HTTP_200_OK,
)
async def get_scan_results(
    scan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all results for a scan, grouped by result_type."""
    service = ScanService(db)
    results = await service.get_scan_results(
        scan_id, user_id=current_user.id, is_admin=_is_admin(current_user),
    )

    grouped = ScanResultGrouped(scan_id=scan_id)
    for r in results:
        # Map DB result_type → grouped field
        rt = r.result_type
        if rt == "HOST_DISCOVERY":
            grouped.host_discovery.append(r.data)
        elif rt == "PORT_SCAN":
            grouped.port_scan.append(r.data)
        elif rt == "SERVICE":
            grouped.service.append(r.data)
        elif rt == "WHOIS":
            grouped.whois = r.data
        elif rt == "DNS":
            grouped.dns.append(r.data)
        elif rt == "SSL":
            grouped.ssl = r.data
        elif rt == "HTTP":
            grouped.http = r.data
        elif rt == "SCREENSHOT":
            grouped.screenshot.append(r.data)
        if r.error:
            grouped.errors.append({"module": rt, "error": r.error})
    return StandardResponse(success=True, message="Results retrieved.", data=grouped)


@router.post(
    "/scans/{scan_id}/cancel",
    response_model=StandardResponse[CancelResponse],
    status_code=status.HTTP_200_OK,
)
async def cancel_scan(
    scan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a queued or running scan."""
    service = ScanService(db)
    scan = await service.cancel_scan(
        scan_id, user_id=current_user.id, is_admin=_is_admin(current_user),
    )
    await db.commit()
    payload = CancelResponse(
        id=scan.id, status=scan.status,
        message=f"Scan {scan.id} has been cancelled.",
    )
    return StandardResponse(success=True, message="Scan cancelled.", data=payload)


@router.delete(
    "/scans/{scan_id}",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_scan(
    scan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a scan and its associated results + assets."""
    service = ScanService(db)
    await service.delete_scan(
        scan_id, user_id=current_user.id, is_admin=_is_admin(current_user),
    )
    await db.commit()
    return StandardResponse(success=True, message="Scan deleted.")


# ===========================================================================
# Reports
# ===========================================================================
async def _resolve_report_user(
    db: AsyncSession,
    current_user: Optional[User],
    token: Optional[str],
    *,
    expected_client_id: Optional[int] = None,
    expected_scan_id: Optional[int] = None,
    fmt: str = "html",
) -> User:
    """Return the user authorised to view this report.

    Two paths:
      1. JWT-authenticated request (``current_user`` is set) — used by
         the API when the frontend fetches the report via axios (it
         attaches the Bearer token automatically).  Run the standard
         ``reports`` module-permission check.
      2. Signed report token (``token`` query param) — used when the
         browser opens the report URL in a new tab / iframe (no JWT
         header).  Consume the token and look up the user from its
         ``user_id`` claim.

    Raises ``ForbiddenError`` / ``UnauthorizedError`` as appropriate.
    """
    from app.services.report_token_service import ReportTokenService
    from app.repositories.user_repository import UserRepository

    if current_user is not None:
        # JWT path — run the standard permission check.
        await _require_module(db, current_user, ModulePermission.REPORTS)
        return current_user

    if not token:
        raise ForbiddenError("Not authenticated.")

    # Token path — single-use, short-lived, signed JWT.
    payload = await ReportTokenService.consume(token)
    if payload.get("format") != fmt:
        raise ForbiddenError(f"Report token was issued for a different format.")

    if expected_client_id is not None:
        tok_client_id = payload.get("client_id")
        if tok_client_id != expected_client_id:
            raise ForbiddenError("Report token does not match this client.")

    if expected_scan_id is not None:
        tok_scan_id = payload.get("scan_id")
        if tok_scan_id != expected_scan_id:
            raise ForbiddenError("Report token does not match this scan.")

    user_id = payload.get("user_id")
    if not user_id:
        raise ForbiddenError("Report token missing user_id.")

    user_repo = UserRepository(db)
    user = await user_repo.get_user_with_role(int(user_id))
    if not user or not user.is_active:
        raise ForbiddenError("Report token user is no longer active.")

    # Audit the token usage.
    audit = AuditService(db)
    await audit.log(
        user_id=user.id, action=AuditAction.REPORT_TOKEN_USED,
        resource="recon.report",
        details={
            "client_id": expected_client_id,
            "scan_id": expected_scan_id,
            "format": fmt,
            "jti": payload.get("jti"),
        },
    )
    return user


@router.post(
    "/scans/{scan_id}/report/token",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
)
async def issue_scan_report_token(
    scan_id: int,
    fmt: str = Query("html", pattern="^(html|pdf)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Issue a short-lived signed URL token for opening the scan report
    in a new browser tab/iframe.

    Returns ``{token, url, expires_in}`` where ``url`` is the full path
    the browser should navigate to.
    """
    await _require_module(db, current_user, ModulePermission.REPORTS)
    service = ScanService(db)
    await service.get_scan(
        scan_id, user_id=current_user.id, is_admin=_is_admin(current_user),
    )
    from app.services.report_token_service import ReportTokenService
    token = ReportTokenService.issue(
        user_id=current_user.id, scan_id=scan_id, fmt=fmt,
    )
    url = f"/api/v1/recon/scans/{scan_id}/report/{fmt}?token={token}"
    return StandardResponse(
        success=True, message="Report token issued.",
        data={"token": token, "url": url, "expires_in": 300},
    )


@router.post(
    "/clients/{client_id}/report/token",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
)
async def issue_client_report_token(
    client_id: int,
    fmt: str = Query("html", pattern="^(html|pdf)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Issue a short-lived signed URL token for opening the merged
    client report in a new browser tab/iframe.
    """
    await _require_module(db, current_user, ModulePermission.REPORTS)
    # Verify the user is authorised for this client.
    from app.repositories.client_repository import ClientRepository
    from app.repositories.target_assignment_repository import TargetAssignmentRepository
    client_repo = ClientRepository(db)
    assignment_repo = TargetAssignmentRepository(db)
    client = await client_repo.get_by_id(client_id)
    if not client:
        raise NotFoundError("Client not found.")
    is_admin = _is_admin(current_user)
    if not is_admin:
        active_client_ids = await assignment_repo.list_active_user_client_ids(current_user.id)
        if client_id not in active_client_ids:
            raise ForbiddenError("You do not have access to this client.")

    from app.services.report_token_service import ReportTokenService
    token = ReportTokenService.issue(
        user_id=current_user.id, client_id=client_id, fmt=fmt,
    )
    audit = AuditService(db)
    await audit.log(
        user_id=current_user.id, action=AuditAction.REPORT_TOKEN_ISSUED,
        resource="recon.report",
        details={"client_id": client_id, "format": fmt},
    )
    await db.commit()
    url = f"/api/v1/recon/clients/{client_id}/report/{fmt}?token={token}"
    return StandardResponse(
        success=True, message="Report token issued.",
        data={"token": token, "url": url, "expires_in": 300},
    )


@router.get(
    "/scans/{scan_id}/report",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
)
async def get_report_metadata(
    scan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return report metadata (formats available, timestamps)."""
    await _require_module(db, current_user, ModulePermission.REPORTS)
    service = ScanService(db)
    await service.get_scan(
        scan_id, user_id=current_user.id, is_admin=_is_admin(current_user),
    )
    report_service = ReportService(db)
    meta = await report_service.get_metadata(scan_id)
    if not meta:
        raise NotFoundError("Report metadata not available.")
    return StandardResponse(success=True, message="Report metadata retrieved.", data=meta)


@router.get(
    "/scans/{scan_id}/report/html",
    response_class=HTMLResponse,
    status_code=status.HTTP_200_OK,
)
async def get_report_html(
    scan_id: int,
    token: Optional[str] = Query(None, description="Signed report URL token (alternative to JWT)"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_or_none),
):
    """Generate and return the standalone HTML report.

    Auth paths:
      * JWT (default) — the frontend's axios client attaches the Bearer
        token automatically.
      * Signed report token — passed as ``?token=`` query param when
        the browser opens this URL in a new tab/iframe.
    """
    user = await _resolve_report_user(
        db, current_user, token, expected_scan_id=scan_id, fmt="html",
    )
    service = ScanService(db)
    await service.get_scan(
        scan_id, user_id=user.id, is_admin=_is_admin(user),
    )
    report_service = ReportService(db)
    html_content = await report_service.generate_html(scan_id)
    if html_content is None:
        raise NotFoundError("Report could not be generated.")
    # Audit
    audit = AuditService(db)
    await audit.log(
        user_id=user.id, action=AuditAction.REPORT_GENERATED,
        resource="recon.report", details={"scan_id": scan_id, "format": "html"},
    )
    await db.commit()
    return HTMLResponse(content=html_content, status_code=200)


@router.get(
    "/scans/{scan_id}/report/pdf",
    status_code=status.HTTP_200_OK,
)
async def get_report_pdf(
    scan_id: int,
    token: Optional[str] = Query(None, description="Signed report URL token (alternative to JWT)"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_or_none),
):
    """Generate and return the PDF report."""
    user = await _resolve_report_user(
        db, current_user, token, expected_scan_id=scan_id, fmt="pdf",
    )
    service = ScanService(db)
    await service.get_scan(
        scan_id, user_id=user.id, is_admin=_is_admin(user),
    )
    report_service = ReportService(db)
    pdf_bytes = await report_service.generate_pdf(scan_id)
    if pdf_bytes is None:
        raise NotFoundError("Report could not be generated.")
    audit = AuditService(db)
    await audit.log(
        user_id=user.id, action=AuditAction.REPORT_GENERATED,
        resource="recon.report", details={"scan_id": scan_id, "format": "pdf"},
    )
    await db.commit()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="basir-recon-scan-{scan_id}.pdf"',
        },
    )


# ===========================================================================
# Screenshots (static file streaming)
# ===========================================================================
@router.get(
    "/screenshots/{screenshot_id}",
    status_code=status.HTTP_200_OK,
)
async def get_screenshot(
    screenshot_id: str,
    current_user: User = Depends(get_current_user),
):
    """Stream a screenshot file from disk.  Authenticated users only —
    the screenshot_id is a generated UUID and not user-controlled."""
    # Validate the format — must be a hex UUID
    try:
        uuid.UUID(screenshot_id)
    except (ValueError, AttributeError):
        raise BadRequestError("Invalid screenshot ID format.")

    from app.core.config import settings
    path = os.path.join(settings.RECON_SCREENSHOT_STORAGE_PATH, f"{screenshot_id}.png")
    if not os.path.isfile(path):
        raise NotFoundError("Screenshot not found.")

    # Read the file and serve it.  We do not use FileResponse because that
    # would require importing from fastapi.responses and we already have
    # Response imported.  Files are bounded by the screenshot capture size.
    with open(path, "rb") as f:
        data = f.read()
    return Response(content=data, media_type="image/png")


# ===========================================================================
# Assets
# ===========================================================================
@router.get(
    "/assets",
    response_model=StandardResponse[List[AssetRead]],
    status_code=status.HTTP_200_OK,
)
async def list_assets(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    host: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List discovered assets.  Users see their own; admins see all."""
    await _require_module(db, current_user, ModulePermission.ASSETS)
    service = AssetService(db)
    assets = await service.list_assets(
        user_id=current_user.id, is_admin=_is_admin(current_user),
        skip=skip, limit=limit, host_filter=host,
    )
    # Resolve client_name + can_delete for each asset
    from app.repositories.client_repository import ClientRepository
    client_repo = ClientRepository(db)
    cache: dict[int, str] = {}
    data = []
    for a in assets:
        cid = a.client_id
        client_name = None
        if cid is not None:
            if cid not in cache:
                c = await client_repo.get_by_id(cid)
                cache[cid] = c.name if c else None
            client_name = cache.get(cid)
        can_delete = _is_admin(current_user) or (a.ownership_type or OwnershipType.USER_MANUAL) not in OwnershipType.PROTECTED
        data.append(AssetRead.from_orm_asset(a, is_admin=_is_admin(current_user), can_delete=can_delete, client_name=client_name))
    return StandardResponse(success=True, message="Assets retrieved.", data=data)


@router.get(
    "/assets/host/{host}",
    response_model=StandardResponse[List[AssetRead]],
    status_code=status.HTTP_200_OK,
)
async def get_assets_by_host(
    host: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return every asset row whose ``host`` exactly matches the path param."""
    await _require_module(db, current_user, ModulePermission.ASSETS)
    if not host or not host.strip():
        raise BadRequestError("Host parameter is required.")
    service = AssetService(db)
    assets = await service.list_assets_by_host(
        host.strip(),
        user_id=current_user.id,
        is_admin=_is_admin(current_user),
    )
    from app.repositories.client_repository import ClientRepository
    client_repo = ClientRepository(db)
    cache: dict[int, str] = {}
    data = []
    for a in assets:
        cid = a.client_id
        client_name = None
        if cid is not None:
            if cid not in cache:
                c = await client_repo.get_by_id(cid)
                cache[cid] = c.name if c else None
            client_name = cache.get(cid)
        can_delete = _is_admin(current_user) or (a.ownership_type or OwnershipType.USER_MANUAL) not in OwnershipType.PROTECTED
        data.append(AssetRead.from_orm_asset(a, is_admin=_is_admin(current_user), can_delete=can_delete, client_name=client_name))
    return StandardResponse(success=True, message="Assets retrieved.", data=data)


@router.get(
    "/assets/{asset_id}",
    response_model=StandardResponse[AssetRead],
    status_code=status.HTTP_200_OK,
)
async def get_asset(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a single asset."""
    await _require_module(db, current_user, ModulePermission.ASSETS)
    service = AssetService(db)
    asset = await service.get_asset(
        asset_id, user_id=current_user.id, is_admin=_is_admin(current_user),
    )
    can_delete = _is_admin(current_user) or (asset.ownership_type or OwnershipType.USER_MANUAL) not in OwnershipType.PROTECTED
    return StandardResponse(success=True, message="Asset retrieved.", data=AssetRead.from_orm_asset(asset, is_admin=_is_admin(current_user), can_delete=can_delete))


@router.delete(
    "/assets/{asset_id}",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_asset(
    asset_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an asset.

    Phase 17 ownership rule:
      * USER_MANUAL → user MAY delete.
      * CLIENT / ASSIGNED_TARGET → user may NOT delete.  Admin can.
    """
    await _require_module(db, current_user, ModulePermission.ASSETS)
    from app.core.constants import OwnershipType as OT
    from app.services.audit_service import AuditService
    service = AssetService(db)
    asset = await service.get_asset(
        asset_id, user_id=current_user.id, is_admin=_is_admin(current_user),
    )
    ownership = asset.ownership_type or OT.USER_MANUAL
    is_admin = _is_admin(current_user)
    if not is_admin and ownership in OT.PROTECTED:
        audit = AuditService(db)
        await audit.log(
            user_id=current_user.id, action=AuditAction.ASSET_DELETE_DENIED,
            resource="recon.asset",
            details={"asset_id": asset_id, "ownership_type": ownership},
        )
        await db.commit()
        raise ForbiddenError(
            "This asset belongs to a Client or assigned target and cannot be deleted by a user. "
            "Contact an administrator."
        )
    # Delete
    from app.recon.repositories.asset_repository import AssetRepository
    repo = AssetRepository(db)
    await repo.delete(asset.id)
    audit = AuditService(db)
    await audit.log(
        user_id=current_user.id, action=AuditAction.ASSET_DELETED,
        resource="recon.asset",
        details={"asset_id": asset_id, "ownership_type": ownership},
    )
    await db.commit()
    return StandardResponse(success=True, message="Asset deleted.")


# ===========================================================================
# Stats (consumed by the Dashboard)
# ===========================================================================
@router.get(
    "/stats",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
)
async def get_recon_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return aggregated recon stats for the dashboard."""
    from sqlalchemy import select, func
    from app.recon.models.scan import Scan
    from app.recon.models.asset import Asset
    from app.core.constants import ScanStatus

    is_admin = _is_admin(current_user)
    scan_filter = (True,) if is_admin else (Scan.user_id == current_user.id,)
    asset_filter = (True,) if is_admin else (Asset.user_id == current_user.id,)

    async def _count(model, *filters):
        stmt = select(func.count()).select_from(model)
        for f in filters:
            if f is not True:
                stmt = stmt.where(f)
        result = await db.execute(stmt)
        return int(result.scalar_one())

    total_scans = await _count(Scan, *scan_filter)
    running_scans = await _count(
        Scan,
        *scan_filter,
        Scan.status.in_([ScanStatus.QUEUED, ScanStatus.RUNNING]),
    )
    completed_scans = await _count(
        Scan, *scan_filter, Scan.status == ScanStatus.COMPLETED,
    )
    total_assets = await _count(Asset, *asset_filter)
    open_ports = await _count(
        Asset, *asset_filter, Asset.port.is_not(None),
    )

    # Recent scans
    recent_scans_stmt = select(Scan)
    if not is_admin:
        recent_scans_stmt = recent_scans_stmt.where(Scan.user_id == current_user.id)
    recent_scans_stmt = recent_scans_stmt.order_by(Scan.created_at.desc()).limit(5)
    recent_scans = list((await db.execute(recent_scans_stmt)).scalars().all())

    # Recent assets
    recent_assets_stmt = select(Asset)
    if not is_admin:
        recent_assets_stmt = recent_assets_stmt.where(Asset.user_id == current_user.id)
    recent_assets_stmt = recent_assets_stmt.order_by(Asset.last_seen.desc()).limit(5)
    recent_assets = list((await db.execute(recent_assets_stmt)).scalars().all())

    return StandardResponse(
        success=True, message="Recon stats retrieved.",
        data={
            "total_scans": total_scans,
            "running_scans": running_scans,
            "completed_scans": completed_scans,
            "total_assets": total_assets,
            "open_ports": open_ports,
            "recent_scans": [
                {
                    "id": s.id, "target": s.target, "status": s.status,
                    "progress": s.progress,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                }
                for s in recent_scans
            ],
            "recent_assets": [
                {
                    "id": a.id, "host": a.host, "ip_address": a.ip_address,
                    "port": a.port, "service": a.service,
                    "last_seen": a.last_seen.isoformat() if a.last_seen else None,
                }
                for a in recent_assets
            ],
        },
    )


# ===========================================================================
# Phase 17 — Client-level merged report
# ===========================================================================
@router.get(
    "/clients/{client_id}/report/html",
    response_class=HTMLResponse,
    status_code=status.HTTP_200_OK,
)
async def get_client_report_html(
    client_id: int,
    token: Optional[str] = Query(None, description="Signed report URL token (alternative to JWT)"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_or_none),
):
    """Generate a merged HTML report covering every completed scan whose
    ``client_id`` matches.  The user must either be an admin or have an
    active CLIENT assignment for this client.

    Auth paths:
      * JWT (default) — axios attaches the Bearer token automatically.
      * Signed report token — passed as ``?token=`` query param when the
        browser opens this URL in a new tab/iframe.
    """
    user = await _resolve_report_user(
        db, current_user, token, expected_client_id=client_id, fmt="html",
    )
    from app.repositories.client_repository import ClientRepository
    from app.repositories.target_assignment_repository import TargetAssignmentRepository
    from app.recon.repositories.scan_repository import ScanRepository
    client_repo = ClientRepository(db)
    assignment_repo = TargetAssignmentRepository(db)
    scan_repo = ScanRepository(db)

    client = await client_repo.get_by_id(client_id)
    if not client:
        raise NotFoundError("Client not found.")

    is_admin = _is_admin(user)
    if not is_admin:
        # Ensure the user has an active CLIENT assignment AND that
        # the user's per-client permission is enabled (Phase 19).
        from app.repositories.user_client_permission_repository import (
            UserClientPermissionRepository,
        )
        client_perm_repo = UserClientPermissionRepository(db)
        client_enabled = await client_perm_repo.is_enabled(user.id, client_id)
        if not client_enabled:
            raise ForbiddenError("Access to this client has been disabled for your account.")
        active_client_ids = await assignment_repo.list_active_user_client_ids(user.id)
        if client_id not in active_client_ids:
            raise ForbiddenError("You do not have access to this client.")

    # Gather all completed scans for this client
    from sqlalchemy import select
    from app.recon.models.scan import Scan as ScanModel
    from app.core.constants import ScanStatus
    stmt = (
        select(ScanModel)
        .where(ScanModel.client_id == client_id)
        .where(ScanModel.status == ScanStatus.COMPLETED)
        .order_by(ScanModel.created_at.asc())
    )
    result = await db.execute(stmt)
    scans = list(result.scalars().all())
    if not scans:
        raise NotFoundError("No completed scans exist for this client yet.")

    # Use the ReportService to build a merged HTML view
    report_service = ReportService(db)
    html_content = await report_service.generate_client_html(client, scans)
    audit = AuditService(db)
    await audit.log(
        user_id=user.id, action=AuditAction.REPORT_GENERATED,
        resource="recon.client_report",
        details={"client_id": client_id, "format": "html", "scan_count": len(scans)},
    )
    await db.commit()
    return HTMLResponse(content=html_content, status_code=200)


@router.get(
    "/clients/{client_id}/scans",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
)
async def list_client_scans(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all scans belonging to a client.  Access-controlled same as
    the merged report endpoint above."""
    from app.repositories.client_repository import ClientRepository
    from app.repositories.target_assignment_repository import TargetAssignmentRepository
    client_repo = ClientRepository(db)
    assignment_repo = TargetAssignmentRepository(db)

    client = await client_repo.get_by_id(client_id)
    if not client:
        raise NotFoundError("Client not found.")
    is_admin = _is_admin(current_user)
    if not is_admin:
        active_client_ids = await assignment_repo.list_active_user_client_ids(current_user.id)
        if client_id not in active_client_ids:
            raise ForbiddenError("You do not have access to this client.")

    from sqlalchemy import select
    from app.recon.models.scan import Scan as ScanModel
    stmt = (
        select(ScanModel)
        .where(ScanModel.client_id == client_id)
        .order_by(ScanModel.created_at.desc())
        .limit(200)
    )
    result = await db.execute(stmt)
    scans = list(result.scalars().all())
    return StandardResponse(
        success=True, message="Client scans retrieved.",
        data=[
            {
                "id": s.id, "target": s.target, "status": s.status,
                "ownership_type": s.ownership_type,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in scans
        ],
    )
