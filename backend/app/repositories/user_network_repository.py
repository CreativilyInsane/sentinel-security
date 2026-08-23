# backend/app/repositories/user_network_repository.py
"""Repository for per-user allowed network management."""
from __future__ import annotations

from typing import List

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_network import UserAllowedNetwork


class UserNetworkRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_user(self, user_id: int) -> List[UserAllowedNetwork]:
        stmt = select(UserAllowedNetwork).where(UserAllowedNetwork.user_id == user_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def set_networks(self, user_id: int, networks: List[str]) -> List[UserAllowedNetwork]:
        # Delete existing
        await self.db.execute(
            delete(UserAllowedNetwork).where(UserAllowedNetwork.user_id == user_id)
        )
        # Insert new
        objects = [UserAllowedNetwork(user_id=user_id, network=n) for n in networks]
        if objects:
            self.db.add_all(objects)
            await self.db.flush()
        return objects

    async def get_networks_list(self, user_id: int) -> List[str]:
        rows = await self.list_for_user(user_id)
        return [r.network for r in rows]
