# backend/app/api/v1/endpoints/targets.py
"""Target assignment endpoints.

Admin:
    POST   /targets/assign/client
    POST   /targets/assign/direct
    GET    /targets/assignments
    PUT    /targets/assignments/{id}
    DELETE /targets/assignments/{id}

User:
    GET    /targets/my-targets         (authorized targets + assignments)
    GET    /targets/my-clients          (assigned clients w/ assets)
    GET    /targets/notifications       (new-assignment notifications)
    POST   /targets/notifications/read  (mark as read)
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.core.constants import Roles, OwnershipType
from app.db.session import get_db
from app.models.user import User
from app.repositories.client_repository import ClientRepository, ClientAssetRepository
from app.repositories.target_assignment_repository import (
    TargetAssignmentRepository, AssignmentNotificationRepository,
)
from app.schemas.common import StandardResponse
from app.schemas.target_assignment import (
    AssignClientPayload, AssignDirectTargetPayload,
    AssignmentRead, AssignmentUpdate, AssignmentNotificationRead,
    NotificationMarkRead,
)
from app.services.client_service import ClientService
from app.services.target_authorization_service import TargetAuthorizationService
from app.utils.errors import NotFoundError


router = APIRouter()


def _is_admin(user: User) -> bool:
    return bool(user.role and user.role.name == Roles.ADMIN)


# ===========================================================================
# Admin — assignment management
# ===========================================================================
@router.post(
    "/targets/assign/client",
    response_model=StandardResponse[AssignmentRead],
    status_code=status.HTTP_201_CREATED,
)
async def assign_client(
    payload: AssignClientPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = ClientService(db)
    a = await service.assign_client(admin_id=current_user.id, payload=payload)
    await db.commit()
    refreshed = await service._to_read(a)
    return StandardResponse(success=True, message="Client assigned.", data=refreshed)


@router.post(
    "/targets/assign/direct",
    response_model=StandardResponse[AssignmentRead],
    status_code=status.HTTP_201_CREATED,
)
async def assign_direct_target(
    payload: AssignDirectTargetPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = ClientService(db)
    a = await service.assign_direct_target(admin_id=current_user.id, payload=payload)
    await db.commit()
    refreshed = await service._to_read(a)
    return StandardResponse(success=True, message="Direct target assigned.", data=refreshed)


@router.get(
    "/targets/assignments",
    response_model=StandardResponse[List[AssignmentRead]],
    status_code=status.HTTP_200_OK,
)
async def list_assignments(
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    user_id: Optional[int] = Query(None),
    client_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = ClientService(db)
    rows = await service.list_assignments(
        skip=skip, limit=limit, user_id=user_id, client_id=client_id,
    )
    return StandardResponse(success=True, message="Assignments retrieved.", data=rows)


@router.put(
    "/targets/assignments/{assignment_id}",
    response_model=StandardResponse[AssignmentRead],
    status_code=status.HTTP_200_OK,
)
async def update_assignment(
    assignment_id: int,
    payload: AssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = ClientService(db)
    a = await service.update_assignment(
        assignment_id=assignment_id, admin_id=current_user.id, payload=payload,
    )
    await db.commit()
    refreshed = await service._to_read(a)
    return StandardResponse(success=True, message="Assignment updated.", data=refreshed)


@router.delete(
    "/targets/assignments/{assignment_id}",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
)
async def delete_assignment(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = ClientService(db)
    await service.delete_assignment(assignment_id=assignment_id, admin_id=current_user.id)
    await db.commit()
    return StandardResponse(success=True, message="Assignment removed.")


# ===========================================================================
# User — own assignments / authorized targets / notifications
# ===========================================================================
@router.get(
    "/targets/my-targets",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
)
async def my_targets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the list of authorized targets for the authenticated user.

    Each item is a dict with:
      assignment_id, ownership_type, client_id, client_asset_id,
      target_type, target_value, label, client_name.
    Used by the Network Scan page to populate the assignment dropdown.
    """
    auth_service = TargetAuthorizationService(db)
    items = await auth_service.list_authorized_targets(current_user)

    # Resolve client_name for each item
    client_repo = ClientRepository(db)
    cache: dict[int, str] = {}
    for it in items:
        cid = it.get("client_id")
        if cid is not None:
            if cid not in cache:
                c = await client_repo.get_by_id(cid)
                cache[cid] = c.name if c else None
            it["client_name"] = cache.get(cid)

    # Filter by the user's active-target selections.  If the user has never
    # toggled any targets, all authorized targets are shown (default = active).
    # Once the user toggles at least one target as active, only active ones
    # are returned.
    from sqlalchemy import select
    from app.models.user_active_target import UserActiveTarget
    stmt = select(UserActiveTarget).where(UserActiveTarget.user_id == current_user.id)
    active_rows = list((await db.execute(stmt)).scalars().all())
    if active_rows:
        active_keys = {
            r.target_key for r in active_rows if r.is_active
        }
        items = [
            it for it in items
            if f"{it['assignment_id']}:{it['target_value']}" in active_keys
        ]

    return StandardResponse(success=True, message="Authorized targets retrieved.", data=items)


@router.get(
    "/targets/my-clients",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
)
async def my_clients(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the list of Clients assigned to the authenticated user with
    their active assets expanded.

    This endpoint merges BOTH ``CLIENT`` assignments (entire Client) and
    ``DIRECT_TARGET`` assignments (specific asset / IP / CIDR) under the
    parent Client.  Direct targets are NEVER returned as a separate
    top-level "Direct Targets" group — they always appear under their
    owning client so the User UI has a single consistent grouping.

    Each client and asset includes an ``enabled`` flag driven by the
    per-user ``user_client_permissions`` and ``user_asset_permissions``
    tables.  Default-open semantics: if no row exists, ``enabled=true``.

    Each asset also carries an ``assigned_via`` field with one of:
      * ``"CLIENT"``         — asset is visible because the entire Client is assigned
      * ``"DIRECT_TARGET"`` — asset is visible because it was directly assigned
    and an ``assignment_id`` field referencing the underlying
    TargetAssignment row (used by the frontend to toggle the active-target
    visibility and to know which assignment to disable/enable).

    Direct targets whose assignment row has ``client_id IS NULL`` (rare —
    only happens if the legacy API created one without a client) are
    surfaced under a synthetic "Direct Targets" pseudo-client entry so
    the User can still see and toggle them.
    """
    from app.repositories.user_client_permission_repository import (
        UserClientPermissionRepository, UserAssetPermissionRepository,
    )

    assignment_repo = TargetAssignmentRepository(db)
    client_repo = ClientRepository(db)
    asset_repo = ClientAssetRepository(db)
    client_perm_repo = UserClientPermissionRepository(db)
    asset_perm_repo = UserAssetPermissionRepository(db)

    client_perms = {p.client_id: p.enabled for p in await client_perm_repo.list_for_user(current_user.id)}
    asset_perms = {p.client_asset_id: p.enabled for p in await asset_perm_repo.list_for_user(current_user.id)}

    # Load ALL active assignments for this user (both CLIENT and DIRECT_TARGET)
    # and group them by client_id.  Orphans (client_id IS NULL) are surfaced
    # separately at the end so the User can still see them.
    all_assignments = await assignment_repo.list_for_user(current_user.id, active_only=True)
    by_client: dict[int, list[TargetAssignment]] = {}
    orphan_assignments: list[TargetAssignment] = []
    for a in all_assignments:
        if a.client_id is None:
            orphan_assignments.append(a)
        else:
            by_client.setdefault(a.client_id, []).append(a)

    out = []
    for cid, assignments in by_client.items():
        client = await client_repo.get_by_id(cid)
        if not client or not client.is_active:
            continue

        has_client_assignment = any(a.assignment_type == "CLIENT" for a in assignments)
        direct_target_assignments = [a for a in assignments if a.assignment_type == "DIRECT_TARGET"]
        # Map client_asset_id -> assignment_id for direct-target assignments.
        direct_target_asset_ids = {
            a.client_asset_id: a.id
            for a in direct_target_assignments
            if a.client_asset_id is not None
        }
        # The CLIENT assignment for this client (if any) — its id is used
        # as the assignment_id for assets that are visible only via the
        # CLIENT assignment.
        client_assignment_id = next(
            (a.id for a in assignments if a.assignment_type == "CLIENT"), None,
        )

        assets_out: list[dict] = []

        if has_client_assignment:
            # Show ALL active client assets — the user has full Client access.
            client_assets = await asset_repo.list_for_client(cid, is_active=True)
            for ca in client_assets:
                assigned_via = (
                    "DIRECT_TARGET"
                    if ca.id in direct_target_asset_ids
                    else "CLIENT"
                )
                # If the asset is BOTH (client-assigned AND directly
                # assigned), prefer the DIRECT_TARGET assignment_id so
                # the user's toggle on this asset maps to the right row.
                assignment_id = direct_target_asset_ids.get(ca.id, client_assignment_id)
                assets_out.append({
                    "id": ca.id,
                    "asset_type": ca.asset_type,
                    "ip_address": ca.ip_address,
                    "cidr": ca.cidr,
                    "domain": ca.domain,
                    "name": ca.name,
                    "description": ca.description,
                    "network_name": ca.network_name,
                    "vlan_name": ca.vlan_name,
                    "value": ca.ip_address or ca.cidr or ca.domain or "",
                    "enabled": asset_perms.get(ca.id, True),
                    "assigned_via": assigned_via,
                    "assignment_id": assignment_id,
                })
        # If the user has NO CLIENT assignment, only directly-assigned
        # assets should appear — not the entire client asset list.
        for a in direct_target_assignments:
            # Skip assets that were already included in the loop above
            # (only happens when has_client_assignment is True).
            if has_client_assignment and a.client_asset_id is not None:
                continue
            if a.client_asset_id is not None:
                ca = await asset_repo.get_by_id(a.client_asset_id)
                if not ca or not ca.is_active:
                    continue
                assets_out.append({
                    "id": ca.id,
                    "asset_type": ca.asset_type,
                    "ip_address": ca.ip_address,
                    "cidr": ca.cidr,
                    "domain": ca.domain,
                    "name": ca.name,
                    "description": ca.description,
                    "network_name": ca.network_name,
                    "vlan_name": ca.vlan_name,
                    "value": ca.ip_address or ca.cidr or ca.domain or "",
                    "enabled": asset_perms.get(ca.id, True),
                    "assigned_via": "DIRECT_TARGET",
                    "assignment_id": a.id,
                })
            else:
                # Ad-hoc direct target whose value is NOT one of the
                # client's existing ClientAsset rows (e.g. the admin
                # typed an IP/CIDR/Domain directly into the direct-target
                # form, with a Client selected as the organising context).
                # Surface it as a synthetic asset entry so the User can
                # still see and toggle it under the parent Client.
                assets_out.append({
                    "id": None,
                    "asset_type": a.target_type,
                    "ip_address": a.target_value if a.target_type == "IP" else None,
                    "cidr": a.target_value if a.target_type in ("CIDR", "IP_RANGE") else None,
                    "domain": a.target_value if a.target_type == "DOMAIN" else None,
                    "name": a.target_label or a.target_value,
                    "description": None,
                    "network_name": None,
                    "vlan_name": None,
                    "value": a.target_value,
                    "enabled": True,  # No asset_perm row exists for synthetic assets
                    "assigned_via": "DIRECT_TARGET",
                    "assignment_id": a.id,
                })

        # Per-user client toggle (default-open: missing row == True).
        client_enabled = client_perms.get(cid, True)
        out.append({
            "id": client.id,
            "name": client.name,
            "description": client.description,
            "company_name": client.company_name,
            "enabled": client_enabled,
            "assets": assets_out,
        })

    # Orphan direct targets (no client context) — surfaced as a
    # synthetic pseudo-client so the User can still see/toggle them.
    if orphan_assignments:
        orphan_assets = []
        for a in orphan_assignments:
            orphan_assets.append({
                "id": None,
                "asset_type": a.target_type,
                "ip_address": a.target_value if a.target_type == "IP" else None,
                "cidr": a.target_value if a.target_type in ("CIDR", "IP_RANGE") else None,
                "domain": a.target_value if a.target_type == "DOMAIN" else None,
                "name": a.target_label or a.target_value,
                "description": None,
                "network_name": None,
                "vlan_name": None,
                "value": a.target_value,
                "enabled": True,
                "assigned_via": "DIRECT_TARGET",
                "assignment_id": a.id,
            })
        out.append({
            "id": None,
            "name": "Direct Targets",
            "description": "Directly assigned targets without an associated client.",
            "company_name": None,
            "enabled": True,
            "assets": orphan_assets,
        })

    return StandardResponse(success=True, message="Assigned clients retrieved.", data=out)


@router.get(
    "/targets/notifications",
    response_model=StandardResponse[List[AssignmentNotificationRead]],
    status_code=status.HTTP_200_OK,
)
async def my_notifications(
    unread_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = AssignmentNotificationRepository(db)
    rows = await repo.list_for_user(current_user.id, unread_only=unread_only, limit=100)
    return StandardResponse(success=True, message="Notifications retrieved.", data=[AssignmentNotificationRead.model_validate(n) for n in rows])


@router.get(
    "/targets/notifications/unread-count",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
)
async def my_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = AssignmentNotificationRepository(db)
    count = await repo.count_unread(current_user.id)
    return StandardResponse(success=True, message="Unread count retrieved.", data={"count": count})


@router.post(
    "/targets/notifications/read",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
)
async def mark_notifications_read(
    payload: NotificationMarkRead,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = AssignmentNotificationRepository(db)
    n = await repo.mark_read(current_user.id, payload.notification_ids)
    await db.commit()
    return StandardResponse(success=True, message=f"{n} notification(s) marked as read.", data={"updated": n})


# ===========================================================================
# User — active targets (user-level selection of which assigned targets
# are visible in the Network Scan dropdown)
# ===========================================================================
@router.get(
    "/targets/active",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
)
async def list_active_targets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the user's active-target selections.

    Each entry has: target_key, assignment_id, target_value, is_active.
    The frontend uses this to decide which authorized targets to show
    in the Network Scan multi-select.
    """
    from sqlalchemy import select
    from app.models.user_active_target import UserActiveTarget
    stmt = (
        select(UserActiveTarget)
        .where(UserActiveTarget.user_id == current_user.id)
        .order_by(UserActiveTarget.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    return StandardResponse(
        success=True, message="Active targets retrieved.",
        data=[
            {
                "target_key": r.target_key,
                "assignment_id": r.assignment_id,
                "target_value": r.target_value,
                "is_active": r.is_active,
            }
            for r in rows
        ],
    )


@router.post(
    "/targets/active/toggle",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
)
async def toggle_active_target(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle a target's active state for the current user.

    Payload: { assignment_id: int, target_value: str, is_active: bool }
    Creates the row if it doesn't exist yet; updates it otherwise.
    """
    from sqlalchemy import select
    from app.models.user_active_target import UserActiveTarget

    assignment_id = payload.get("assignment_id")
    target_value = payload.get("target_value")
    is_active = payload.get("is_active", True)

    if not assignment_id or not target_value:
        from app.utils.errors import BadRequestError
        raise BadRequestError("assignment_id and target_value are required.")

    target_key = f"{assignment_id}:{target_value}"

    stmt = select(UserActiveTarget).where(
        UserActiveTarget.user_id == current_user.id,
        UserActiveTarget.target_key == target_key,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing:
        existing.is_active = is_active
    else:
        row = UserActiveTarget(
            user_id=current_user.id,
            target_key=target_key,
            assignment_id=assignment_id,
            target_value=target_value,
            is_active=is_active,
        )
        db.add(row)
    await db.commit()
    return StandardResponse(
        success=True,
        message=f"Target {'activated' if is_active else 'deactivated'}.",
        data={"target_key": target_key, "is_active": is_active},
    )


# ===========================================================================
# Phase 19 — per-user client/asset enable/disable toggles
# ===========================================================================
@router.post(
    "/targets/clients/{client_id}/toggle",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
)
async def toggle_client_permission(
    client_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enable/disable the current user's access to a Client.

    Payload: { "enabled": bool }

    When ``enabled=false`` is set, the user can no longer scan any of
    the client's assets.  The underlying Client record is untouched —
    other users keep their access.

    When the parent Client is disabled (``enabled=false``), all of the
    user's per-asset permissions for that client are also marked
    disabled (parent cascade rule).  When re-enabled, the previous
    child asset states are restored (i.e., assets that were disabled
    individually remain disabled).
    """
    from app.repositories.client_repository import ClientRepository
    from app.repositories.user_client_permission_repository import (
        UserClientPermissionRepository, UserAssetPermissionRepository,
    )
    from app.services.audit_service import AuditService
    from app.core.constants import AuditAction

    client_repo = ClientRepository(db)
    client = await client_repo.get_by_id(client_id)
    if not client:
        raise NotFoundError("Client not found.")

    # Verify the user has been assigned this client (admins bypass).
    if not _is_admin(current_user):
        assignment_repo = TargetAssignmentRepository(db)
        active_client_ids = await assignment_repo.list_active_user_client_ids(current_user.id)
        if client_id not in active_client_ids:
            from app.utils.errors import ForbiddenError
            raise ForbiddenError("You do not have access to this client.")

    enabled = bool(payload.get("enabled", True))

    client_perm_repo = UserClientPermissionRepository(db)
    asset_perm_repo = UserAssetPermissionRepository(db)

    # Upsert the client permission row.
    await client_perm_repo.set_enabled(current_user.id, client_id, enabled)

    # Parent cascade rule: when disabling, mark all child asset perms
    # disabled.  When re-enabling, do NOT touch child perms — they
    # preserve their previous state.
    if not enabled:
        await client_perm_repo.disable_all_for_client(current_user.id, client_id)

    await AuditService(db).log(
        user_id=current_user.id,
        action=AuditAction.CLIENT_TOGGLED,
        resource="client.permission",
        details={"client_id": client_id, "enabled": enabled},
    )
    await db.commit()

    return StandardResponse(
        success=True,
        message=f"Client access {'enabled' if enabled else 'disabled'}.",
        data={"client_id": client_id, "enabled": enabled},
    )


@router.post(
    "/targets/assets/{asset_id}/toggle",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
)
async def toggle_asset_permission(
    asset_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enable/disable the current user's access to a single ClientAsset.

    Payload: { "enabled": bool }

    The underlying ClientAsset row is untouched — only the per-user
    toggle is updated.  Other users keep their access.

    If the user's per-client permission for the asset's parent client
    is disabled, the asset remains inaccessible regardless of this
    toggle.
    """
    from app.repositories.client_repository import ClientAssetRepository, ClientRepository
    from app.repositories.user_client_permission_repository import (
        UserClientPermissionRepository, UserAssetPermissionRepository,
    )
    from app.repositories.target_assignment_repository import TargetAssignmentRepository
    from app.services.audit_service import AuditService
    from app.core.constants import AuditAction
    from app.utils.errors import BadRequestError, ForbiddenError

    asset_repo = ClientAssetRepository(db)
    # Use the ClientAssetRepository's get_for_client with client_id=0
    # fallback — but the simpler approach is a direct ORM get.
    from sqlalchemy import select
    from app.models.client import ClientAsset
    stmt = select(ClientAsset).where(ClientAsset.id == asset_id)
    asset = (await db.execute(stmt)).scalar_one_or_none()
    if not asset:
        raise NotFoundError("Asset not found.")

    # Verify the user has been assigned this asset's parent client.
    if not _is_admin(current_user):
        assignment_repo = TargetAssignmentRepository(db)
        active_client_ids = await assignment_repo.list_active_user_client_ids(current_user.id)
        if (asset.client_id or 0) not in active_client_ids:
            raise ForbiddenError("You do not have access to this asset's parent client.")

    enabled = bool(payload.get("enabled", True))

    asset_perm_repo = UserAssetPermissionRepository(db)
    await asset_perm_repo.set_enabled(current_user.id, asset_id, enabled)

    await AuditService(db).log(
        user_id=current_user.id,
        action=AuditAction.ASSET_TOGGLED,
        resource="asset.permission",
        details={"asset_id": asset_id, "client_id": asset.client_id, "enabled": enabled},
    )
    await db.commit()

    return StandardResponse(
        success=True,
        message=f"Asset access {'enabled' if enabled else 'disabled'}.",
        data={"asset_id": asset_id, "enabled": enabled},
    )
