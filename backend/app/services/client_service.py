# backend/app/services/client_service.py
"""Service layer for Client + ClientAsset management.

Admin-only operations: create / update / delete clients, add / update /
delete client assets, and assign clients / direct targets to users.
"""
from __future__ import annotations

import ipaddress
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    AuditAction, AssignmentType, ClientAssetType, AssignmentNotificationType,
)
from app.core.logging import logger
from app.models.client import Client, ClientAsset
from app.models.target_assignment import TargetAssignment, AssignmentNotification
from app.repositories.client_repository import ClientRepository, ClientAssetRepository
from app.repositories.target_assignment_repository import (
    TargetAssignmentRepository, AssignmentNotificationRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.client import (
    ClientCreate, ClientUpdate, ClientRead, ClientWithStats,
    ClientAssetCreate, ClientAssetUpdate, ClientAssetRead,
)
from app.schemas.target_assignment import (
    AssignClientPayload, AssignDirectTargetPayload,
    AssignmentRead, AssignmentUpdate,
)
from app.services.audit_service import AuditService
from app.utils.errors import (
    BadRequestError, ConflictError, NotFoundError, ForbiddenError,
)


class ClientService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.client_repo = ClientRepository(db)
        self.asset_repo = ClientAssetRepository(db)
        self.assignment_repo = TargetAssignmentRepository(db)
        self.notification_repo = AssignmentNotificationRepository(db)
        self.user_repo = UserRepository(db)
        self.audit = AuditService(db)

    # ===================================================================
    # Clients
    # ===================================================================
    async def create_client(self, *, admin_id: int, payload: ClientCreate) -> Client:
        existing = await self.client_repo.get_by_name(payload.name)
        if existing:
            raise ConflictError(f"A client named '{payload.name}' already exists.")
        client = Client(
            name=payload.name,
            description=payload.description,
            company_name=payload.company_name,
            is_active=payload.is_active,
            created_by=admin_id,
        )
        client = await self.client_repo.create(client)
        await self.audit.log(
            user_id=admin_id, action=AuditAction.CLIENT_CREATED,
            resource="client",
            details={"client_id": client.id, "name": client.name},
        )
        return client

    async def update_client(self, *, client_id: int, admin_id: int, payload: ClientUpdate) -> Client:
        client = await self.client_repo.get_by_id(client_id)
        if not client:
            raise NotFoundError(f"Client with ID {client_id} not found.")
        if payload.name is not None and payload.name != client.name:
            dup = await self.client_repo.get_by_name(payload.name)
            if dup and dup.id != client.id:
                raise ConflictError(f"Another client named '{payload.name}' already exists.")
            client.name = payload.name
        if payload.company_name is not None:
            client.company_name = payload.company_name
        if payload.description is not None:
            client.description = payload.description
        if payload.is_active is not None:
            client.is_active = payload.is_active
        await self.db.flush()
        await self.db.refresh(client)
        await self.audit.log(
            user_id=admin_id, action=AuditAction.CLIENT_UPDATED,
            resource="client",
            details={"client_id": client.id, "name": client.name},
        )
        return client

    async def delete_client(self, *, client_id: int, admin_id: int) -> None:
        client = await self.client_repo.get_by_id(client_id)
        if not client:
            raise NotFoundError(f"Client with ID {client_id} not found.")
        name = client.name
        # Soft-deactivate rather than hard-delete: preserves historical scan
        # integrity (assets/reports retain client_id with ondelete=SET NULL
        # but we prefer to keep the row).
        client.is_active = False
        await self.db.flush()
        # Also deactivate all assignments referencing this client so users
        # lose access immediately.
        assignments = await self.assignment_repo.list_all(client_id=client_id)
        for a in assignments:
            if a.is_active:
                await self.assignment_repo.set_active(a.id, False)
                # Notify each user
                await self.notification_repo.create_notification(
                    user_id=a.user_id, assignment_id=a.id,
                    type_=AssignmentNotificationType.CLIENT_REMOVED,
                    message=f"Client '{name}' is no longer assigned to you.",
                )
        await self.audit.log(
            user_id=admin_id, action=AuditAction.CLIENT_DELETED,
            resource="client",
            details={"client_id": client_id, "name": name, "soft_delete": True},
        )

    async def get_client(self, client_id: int) -> Client:
        c = await self.client_repo.get_by_id(client_id)
        if not c:
            raise NotFoundError(f"Client with ID {client_id} not found.")
        return c

    async def list_clients(
        self, *, skip: int = 0, limit: int = 100, search: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[ClientWithStats]:
        rows = await self.client_repo.list_clients(
            skip=skip, limit=limit, search=search, is_active=is_active,
        )
        out: List[ClientWithStats] = []
        for c in rows:
            asset_count = await self.asset_repo.count_for_client(c.id)
            user_count = await self.assignment_repo.count_users_for_client(c.id)
            active_count = await self.assignment_repo.count_active_for_client(c.id)
            out.append(ClientWithStats(
                id=c.id, name=c.name, description=c.description,
                company_name=c.company_name, is_active=c.is_active,
                created_by=c.created_by, created_at=c.created_at, updated_at=c.updated_at,
                asset_count=asset_count,
                assigned_user_count=user_count,
                active_assignment_count=active_count,
            ))
        return out

    # ===================================================================
    # Client assets
    # ===================================================================
    async def create_asset(
        self, *, client_id: int, admin_id: int, payload: ClientAssetCreate,
    ) -> ClientAsset:
        client = await self.get_client(client_id)
        # Canonicalise value based on asset_type
        cidr_value = None
        ip_value = None
        domain_value = None
        if payload.asset_type == ClientAssetType.IP:
            ip_value = str(ipaddress.ip_address(payload.ip_address))
        elif payload.asset_type == ClientAssetType.IP_RANGE:
            net = ipaddress.ip_network(payload.cidr, strict=False)
            cidr_value = str(net)
        elif payload.asset_type == ClientAssetType.DOMAIN:
            # Already validated + lowercased by the schema
            domain_value = payload.domain

        dup = await self.asset_repo.find_duplicate(
            client_id, payload.asset_type, ip_value, cidr_value, domain_value,
        )
        if dup:
            raise ConflictError("An identical asset already exists for this client.")

        asset = ClientAsset(
            client_id=client_id,
            asset_type=payload.asset_type,
            ip_address=ip_value,
            cidr=cidr_value,
            domain=domain_value,
            name=payload.name,
            description=payload.description,
            network_name=payload.network_name,
            vlan_name=payload.vlan_name,
            is_active=payload.is_active,
        )
        asset = await self.asset_repo.create(asset)
        await self.audit.log(
            user_id=admin_id, action=AuditAction.CLIENT_ASSET_CREATED,
            resource="client_asset",
            details={"client_id": client_id, "asset_id": asset.id, "value": ip_value or cidr_value or domain_value},
        )
        return asset

    async def update_asset(
        self, *, client_id: int, asset_id: int, admin_id: int, payload: ClientAssetUpdate,
    ) -> ClientAsset:
        asset = await self.asset_repo.get_for_client(client_id, asset_id)
        if not asset:
            raise NotFoundError(f"Asset with ID {asset_id} not found for client {client_id}.")

        if payload.asset_type is not None and payload.asset_type != asset.asset_type:
            raise BadRequestError("Cannot change asset_type after creation. Delete and recreate the asset.")

        if payload.ip_address is not None and asset.asset_type == ClientAssetType.IP:
            new_ip = str(ipaddress.ip_address(payload.ip_address))
            dup = await self.asset_repo.find_duplicate(client_id, asset.asset_type, new_ip, None, None, exclude_id=asset.id)
            if dup:
                raise ConflictError("Another asset with this IP already exists.")
            asset.ip_address = new_ip

        if payload.cidr is not None and asset.asset_type == ClientAssetType.IP_RANGE:
            net = ipaddress.ip_network(payload.cidr, strict=False)
            new_cidr = str(net)
            dup = await self.asset_repo.find_duplicate(client_id, asset.asset_type, None, new_cidr, None, exclude_id=asset.id)
            if dup:
                raise ConflictError("Another asset with this CIDR already exists.")
            asset.cidr = new_cidr

        if payload.domain is not None and asset.asset_type == ClientAssetType.DOMAIN:
            new_domain = payload.domain.strip().lower().rstrip(".")
            dup = await self.asset_repo.find_duplicate(client_id, asset.asset_type, None, None, new_domain, exclude_id=asset.id)
            if dup:
                raise ConflictError("Another asset with this domain already exists.")
            asset.domain = new_domain

        if payload.name is not None:
            asset.name = payload.name
        if payload.description is not None:
            asset.description = payload.description
        if payload.network_name is not None:
            asset.network_name = payload.network_name
        if payload.vlan_name is not None:
            asset.vlan_name = payload.vlan_name
        if payload.is_active is not None:
            asset.is_active = payload.is_active

        await self.db.flush()
        await self.db.refresh(asset)
        await self.audit.log(
            user_id=admin_id, action=AuditAction.CLIENT_ASSET_UPDATED,
            resource="client_asset",
            details={"client_id": client_id, "asset_id": asset.id},
        )
        return asset

    async def delete_asset(self, *, client_id: int, asset_id: int, admin_id: int) -> None:
        asset = await self.asset_repo.get_for_client(client_id, asset_id)
        if not asset:
            raise NotFoundError(f"Asset with ID {asset_id} not found for client {client_id}.")
        # Deactivate linked assignments instead of hard-deleting so that
        # historical scans keep their references intact (FK is SET NULL).
        assignments = await self.assignment_repo.list_all(client_id=client_id)
        for a in assignments:
            if a.client_asset_id == asset_id and a.is_active:
                await self.assignment_repo.set_active(a.id, False)
        await self.asset_repo.delete(asset_id)
        await self.audit.log(
            user_id=admin_id, action=AuditAction.CLIENT_ASSET_DELETED,
            resource="client_asset",
            details={"client_id": client_id, "asset_id": asset_id},
        )

    async def list_assets(self, client_id: int) -> List[ClientAsset]:
        await self.get_client(client_id)
        return await self.asset_repo.list_for_client(client_id)

    # ===================================================================
    # Assignments
    # ===================================================================
    async def assign_client(self, *, admin_id: int, payload: AssignClientPayload) -> TargetAssignment:
        client = await self.get_client(payload.client_id)
        user = await self.user_repo.get_user_with_role(payload.user_id)
        if not user:
            raise NotFoundError(f"User with ID {payload.user_id} not found.")

        existing = await self.assignment_repo.find_client_assignment(payload.user_id, payload.client_id)
        if existing:
            if existing.is_active:
                raise ConflictError("This client is already actively assigned to this user.")
            await self.assignment_repo.set_active(existing.id, True)
            assignment = await self.assignment_repo.get_by_id(existing.id)
        else:
            assignment = TargetAssignment(
                user_id=payload.user_id,
                client_id=payload.client_id,
                assignment_type=AssignmentType.CLIENT,
                target_type="CLIENT",
                target_value=client.name,
                target_label=client.name,
                assigned_by=admin_id,
                is_active=True,
            )
            assignment = await self.assignment_repo.create(assignment)

        await self.notification_repo.create_notification(
            user_id=payload.user_id, assignment_id=assignment.id,
            type_=AssignmentNotificationType.CLIENT_ASSIGNED,
            message=f"Client '{client.name}' has been assigned to you.",
        )
        await self.audit.log(
            user_id=admin_id, action=AuditAction.CLIENT_ASSIGNED,
            resource="target_assignment",
            details={"assignment_id": assignment.id, "user_id": payload.user_id, "client_id": payload.client_id},
        )
        return assignment

    async def assign_direct_target(
        self, *, admin_id: int, payload: AssignDirectTargetPayload,
    ) -> TargetAssignment:
        user = await self.user_repo.get_user_with_role(payload.user_id)
        if not user:
            raise NotFoundError(f"User with ID {payload.user_id} not found.")

        # Canonicalise
        if payload.target_type == ClientAssetType.IP:
            value = str(ipaddress.ip_address(payload.target_value))
        elif payload.target_type == ClientAssetType.IP_RANGE:
            value = str(ipaddress.ip_network(payload.target_value, strict=False))
        else:  # DOMAIN — already canonicalised by the schema
            value = payload.target_value

        # Optional client_asset_id lineage
        client_asset: Optional[ClientAsset] = None
        if payload.client_asset_id is not None:
            client_asset = await self.asset_repo.get_by_id(payload.client_asset_id)
            if not client_asset:
                raise NotFoundError(f"ClientAsset with ID {payload.client_asset_id} not found.")

        existing = await self.assignment_repo.find_direct_assignment(payload.user_id, value)
        if existing:
            if existing.is_active:
                raise ConflictError("This exact target is already actively assigned to this user.")
            await self.assignment_repo.set_active(existing.id, True)
            assignment = await self.assignment_repo.get_by_id(existing.id)
        else:
            assignment = TargetAssignment(
                user_id=payload.user_id,
                client_id=payload.client_id,
                client_asset_id=payload.client_asset_id,
                assignment_type=AssignmentType.DIRECT_TARGET,
                target_type=payload.target_type,
                target_value=value,
                target_label=payload.target_label or value,
                assigned_by=admin_id,
                is_active=True,
            )
            assignment = await self.assignment_repo.create(assignment)

        await self.notification_repo.create_notification(
            user_id=payload.user_id, assignment_id=assignment.id,
            type_=AssignmentNotificationType.TARGET_ASSIGNED,
            message=f"Target '{value}' has been directly assigned to you.",
        )
        await self.audit.log(
            user_id=admin_id, action=AuditAction.TARGET_ASSIGNED,
            resource="target_assignment",
            details={
                "assignment_id": assignment.id, "user_id": payload.user_id,
                "target_value": value, "client_asset_id": payload.client_asset_id,
            },
        )
        return assignment

    async def list_assignments(
        self, *, skip: int = 0, limit: int = 200, user_id: Optional[int] = None,
        client_id: Optional[int] = None,
    ) -> List[AssignmentRead]:
        rows = await self.assignment_repo.list_all(
            skip=skip, limit=limit, user_id=user_id, client_id=client_id,
        )
        out: List[AssignmentRead] = []
        for a in rows:
            out.append(await self._to_read(a))
        return out

    async def update_assignment(self, *, assignment_id: int, admin_id: int, payload: AssignmentUpdate) -> TargetAssignment:
        a = await self.assignment_repo.get_by_id(assignment_id)
        if not a:
            raise NotFoundError(f"Assignment with ID {assignment_id} not found.")
        if payload.is_active is not None:
            a.is_active = payload.is_active
        if payload.target_label is not None:
            a.target_label = payload.target_label
        await self.db.flush()
        await self.db.refresh(a)
        return a

    async def delete_assignment(self, *, assignment_id: int, admin_id: int) -> None:
        a = await self.assignment_repo.get_by_id(assignment_id)
        if not a:
            raise NotFoundError(f"Assignment with ID {assignment_id} not found.")
        # Notify user
        notif_type = (
            AssignmentNotificationType.CLIENT_REMOVED
            if a.assignment_type == AssignmentType.CLIENT
            else AssignmentNotificationType.TARGET_REMOVED
        )
        await self.notification_repo.create_notification(
            user_id=a.user_id, assignment_id=None,
            type_=notif_type,
            message=f"Assignment '{a.target_label or a.target_value}' has been removed.",
        )
        action = (
            AuditAction.CLIENT_UNASSIGNED
            if a.assignment_type == AssignmentType.CLIENT
            else AuditAction.TARGET_UNASSIGNED
        )
        await self.audit.log(
            user_id=admin_id, action=action,
            resource="target_assignment",
            details={"assignment_id": a.id, "user_id": a.user_id, "target_value": a.target_value},
        )
        await self.assignment_repo.delete(assignment_id)

    # ===================================================================
    # User-side queries
    # ===================================================================
    async def list_user_assignments(self, user_id: int) -> List[AssignmentRead]:
        rows = await self.assignment_repo.list_for_user(user_id, active_only=True)
        out: List[AssignmentRead] = []
        for a in rows:
            out.append(await self._to_read(a))
        return out

    async def _to_read(self, a: TargetAssignment) -> AssignmentRead:
        client_name: Optional[str] = None
        if a.client_id:
            client = await self.client_repo.get_by_id(a.client_id)
            if client:
                client_name = client.name
        client_asset_name: Optional[str] = None
        if a.client_asset_id:
            ca = await self.asset_repo.get_by_id(a.client_asset_id)
            if ca:
                client_asset_name = ca.name or ca.ip_address or ca.cidr
        assigner_username: Optional[str] = None
        if a.assigned_by:
            assigner = await self.user_repo.get_user_with_role(a.assigned_by)
            if assigner:
                assigner_username = assigner.username
        user_username: Optional[str] = None
        if a.user_id:
            target_user = await self.user_repo.get_user_with_role(a.user_id)
            if target_user:
                user_username = target_user.username
        return AssignmentRead(
            id=a.id, user_id=a.user_id, client_id=a.client_id,
            client_asset_id=a.client_asset_id,
            assignment_type=a.assignment_type,
            target_type=a.target_type, target_value=a.target_value,
            target_label=a.target_label,
            assigned_by=a.assigned_by, is_active=a.is_active,
            created_at=a.created_at, updated_at=a.updated_at,
            client_name=client_name,
            client_asset_name=client_asset_name,
            assigner_username=assigner_username,
            user_username=user_username,
        )
