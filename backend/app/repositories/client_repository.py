# backend/app/repositories/client_repository.py
"""Repository for the Client + ClientAsset models."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client, ClientAsset
from app.repositories.base import BaseRepository


class ClientRepository(BaseRepository[Client]):
    def __init__(self, db: AsyncSession):
        super().__init__(Client, db)

    async def get_by_name(self, name: str) -> Optional[Client]:
        stmt = select(Client).where(Client.name == name)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_clients(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[Client]:
        stmt = select(Client)
        if search:
            like = f"%{search}%"
            stmt = stmt.where(
                (Client.name.ilike(like)) | (Client.company_name.ilike(like))
            )
        if is_active is not None:
            stmt = stmt.where(Client.is_active == is_active)
        stmt = stmt.order_by(Client.created_at.desc()).offset(skip).limit(limit)
        return list((await self.db.execute(stmt)).scalars().all())


class ClientAssetRepository(BaseRepository[ClientAsset]):
    def __init__(self, db: AsyncSession):
        super().__init__(ClientAsset, db)

    async def list_for_client(self, client_id: int, *, is_active: Optional[bool] = None) -> List[ClientAsset]:
        stmt = select(ClientAsset).where(ClientAsset.client_id == client_id)
        if is_active is not None:
            stmt = stmt.where(ClientAsset.is_active == is_active)
        stmt = stmt.order_by(ClientAsset.asset_type.asc(), ClientAsset.created_at.asc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_for_client(self, client_id: int, asset_id: int) -> Optional[ClientAsset]:
        stmt = select(ClientAsset).where(
            and_(ClientAsset.id == asset_id, ClientAsset.client_id == client_id)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def find_duplicate(
        self,
        client_id: int,
        asset_type: str,
        ip_address: Optional[str],
        cidr: Optional[str],
        domain: Optional[str] = None,
        exclude_id: Optional[int] = None,
    ) -> Optional[ClientAsset]:
        """Return an existing asset matching the same (client, type, value)."""
        conditions = [ClientAsset.client_id == client_id, ClientAsset.asset_type == asset_type]
        if asset_type == "IP":
            conditions.append(ClientAsset.ip_address == ip_address)
        elif asset_type == "IP_RANGE":
            conditions.append(ClientAsset.cidr == cidr)
        elif asset_type == "DOMAIN":
            conditions.append(ClientAsset.domain == domain)
        if exclude_id is not None:
            conditions.append(ClientAsset.id != exclude_id)
        stmt = select(ClientAsset).where(and_(*conditions))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def count_for_client(self, client_id: int) -> int:
        stmt = select(func.count()).select_from(ClientAsset).where(ClientAsset.client_id == client_id)
        return int((await self.db.execute(stmt)).scalar_one())
