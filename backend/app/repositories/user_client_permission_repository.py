# backend/app/repositories/user_client_permission_repository.py
"""Per-user, per-client + per-user, per-asset access toggle repositories.

Default-open semantics: if no row exists for (user_id, client_id) or
(user_id, client_asset_id), the user is allowed.  An admin can create
a row with ``enabled=false`` to revoke access for that user only.
"""
from typing import List, Optional, Dict
from sqlalchemy import select, update, and_, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_client_permission import UserClientPermission, UserAssetPermission
from app.repositories.base import BaseRepository


class UserClientPermissionRepository(BaseRepository[UserClientPermission]):
    def __init__(self, db: AsyncSession):
        super().__init__(UserClientPermission, db)

    async def list_for_user(self, user_id: int) -> List[UserClientPermission]:
        stmt = (
            select(UserClientPermission)
            .where(UserClientPermission.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get(self, user_id: int, client_id: int) -> Optional[UserClientPermission]:
        stmt = select(UserClientPermission).where(
            and_(
                UserClientPermission.user_id == user_id,
                UserClientPermission.client_id == client_id,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def is_enabled(self, user_id: int, client_id: int) -> bool:
        """Default-open: returns True if no row exists, else row.enabled."""
        row = await self.get(user_id, client_id)
        if row is None:
            return True
        return bool(row.enabled)

    async def set_enabled(self, user_id: int, client_id: int, enabled: bool) -> UserClientPermission:
        """Upsert a (user_id, client_id, enabled) row.

        If a row already exists, update its ``enabled`` flag and return it.
        Otherwise, INSERT a new row.
        """
        existing = await self.get(user_id, client_id)
        if existing:
            existing.enabled = enabled
            await self.db.flush()
            return existing
        row = UserClientPermission(
            user_id=user_id, client_id=client_id, enabled=enabled,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def disable_all_for_client(self, user_id: int, client_id: int) -> int:
        """When a parent Client is disabled, mark all its asset perms as
        disabled too (parent cascade rule).

        Returns the number of asset-permission rows updated.
        """
        # We need the list of ClientAsset IDs for the client to scope the update.
        from app.models.client import ClientAsset
        asset_ids_stmt = select(ClientAsset.id).where(ClientAsset.client_id == client_id)
        asset_ids_result = await self.db.execute(asset_ids_stmt)
        asset_ids = [r[0] for r in asset_ids_result]
        if not asset_ids:
            return 0
        stmt = (
            update(UserAssetPermission)
            .where(
                and_(
                    UserAssetPermission.user_id == user_id,
                    UserAssetPermission.client_asset_id.in_(asset_ids),
                )
            )
            .values(enabled=False)
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return int(result.rowcount or 0)


class UserAssetPermissionRepository(BaseRepository[UserAssetPermission]):
    def __init__(self, db: AsyncSession):
        super().__init__(UserAssetPermission, db)

    async def list_for_user(self, user_id: int) -> List[UserAssetPermission]:
        stmt = (
            select(UserAssetPermission)
            .where(UserAssetPermission.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get(self, user_id: int, client_asset_id: int) -> Optional[UserAssetPermission]:
        stmt = select(UserAssetPermission).where(
            and_(
                UserAssetPermission.user_id == user_id,
                UserAssetPermission.client_asset_id == client_asset_id,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def is_enabled(self, user_id: int, client_asset_id: int) -> bool:
        row = await self.get(user_id, client_asset_id)
        if row is None:
            return True
        return bool(row.enabled)

    async def set_enabled(
        self, user_id: int, client_asset_id: int, enabled: bool,
    ) -> UserAssetPermission:
        existing = await self.get(user_id, client_asset_id)
        if existing:
            existing.enabled = enabled
            await self.db.flush()
            return existing
        row = UserAssetPermission(
            user_id=user_id, client_asset_id=client_asset_id, enabled=enabled,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row
