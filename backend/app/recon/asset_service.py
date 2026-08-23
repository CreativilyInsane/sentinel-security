# backend/app/recon/asset_service.py
"""AssetService — thin facade over AssetRepository exposed to the API layer.

Keeps the API layer free of direct repository imports.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.recon.models.asset import Asset
from app.recon.repositories.asset_repository import AssetRepository
from app.utils.errors import NotFoundError, ForbiddenError


class AssetService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AssetRepository(db)

    async def list_assets(
        self,
        *,
        user_id: int,
        is_admin: bool,
        skip: int = 0,
        limit: int = 100,
        host_filter: Optional[str] = None,
    ) -> List[Asset]:
        if is_admin:
            return await self.repo.list_all_assets(skip=skip, limit=limit, host_filter=host_filter)
        return await self.repo.list_user_assets(user_id, skip=skip, limit=limit, host_filter=host_filter)

    async def get_asset(self, asset_id: int, *, user_id: int, is_admin: bool) -> Asset:
        if is_admin:
            asset = await self.repo.get_by_id(asset_id)
        else:
            asset = await self.repo.get_user_asset(user_id, asset_id)
        if not asset:
            raise NotFoundError(f"Asset with ID {asset_id} not found.")
        return asset

    async def count_assets(self, *, user_id: int, is_admin: bool) -> int:
        if is_admin:
            return await self.repo.count_all_assets()
        return await self.repo.count_user_assets(user_id)

    async def count_open_ports(self, *, user_id: int, is_admin: bool) -> int:
        if is_admin:
            # Approximation for admin (cross-user) — count all assets with port
            from sqlalchemy import select, func
            from app.recon.models.asset import Asset as A
            stmt = select(func.count()).select_from(A).where(A.port.is_not(None))
            result = await self.db.execute(stmt)
            return int(result.scalar_one())
        return await self.repo.count_user_open_ports(user_id)

    async def recent_assets(self, *, user_id: int, is_admin: bool, limit: int = 5) -> List[Asset]:
        if is_admin:
            from sqlalchemy import select
            from app.recon.models.asset import Asset as A
            stmt = select(A).order_by(A.last_seen.desc()).limit(limit)
            result = await self.db.execute(stmt)
            return list(result.scalars().all())
        return await self.repo.recent_user_assets(user_id, limit=limit)

    async def list_assets_by_host(
        self,
        host: str,
        *,
        user_id: int,
        is_admin: bool,
    ) -> List[Asset]:
        """Return every asset row whose host exactly matches ``host``.

        Users only see their own assets; admins see all assets for the host.
        """
        if is_admin:
            return await self.repo.list_all_assets_by_host(host)
        return await self.repo.list_user_assets_by_host(user_id, host)
