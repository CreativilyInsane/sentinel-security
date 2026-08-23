# backend/app/recon/repositories/asset_repository.py
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import OwnershipType
from app.recon.models.asset import Asset
from app.repositories.base import BaseRepository


class AssetRepository(BaseRepository[Asset]):
    def __init__(self, db: AsyncSession):
        super().__init__(Asset, db)

    async def upsert_asset(
        self,
        *,
        user_id: int,
        scan_id: Optional[int],
        host: str,
        ip_address: Optional[str] = None,
        hostname: Optional[str] = None,
        port: Optional[int] = None,
        protocol: Optional[str] = None,
        service: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ownership_type: str = OwnershipType.USER_MANUAL,
        client_id: Optional[int] = None,
        client_asset_id: Optional[int] = None,
        assignment_id: Optional[int] = None,
    ) -> Asset:
        """Insert a new asset or update last_seen + metadata if it already exists.

        Natural key: (user_id, host, ip_address, port).

        Phase 17: ownership fields are persisted on insert.  On update, we
        preserve the existing ownership_type/client_id/assignment_id so
        that re-scanning an assigned target doesn't accidentally downgrade
        a protected asset to USER_MANUAL.
        """
        conditions = [
            Asset.user_id == user_id,
            Asset.host == host,
        ]
        if ip_address is not None:
            conditions.append(Asset.ip_address == ip_address)
        else:
            conditions.append(Asset.ip_address.is_(None))
        if port is not None:
            conditions.append(Asset.port == port)
        else:
            conditions.append(Asset.port.is_(None))

        stmt = select(Asset).where(and_(*conditions))
        existing = (await self.db.execute(stmt)).scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if existing:
            new_meta = dict(existing.metadata_ or {})
            if metadata:
                new_meta.update(metadata)
            update_stmt = (
                update(Asset)
                .where(Asset.id == existing.id)
                .values(
                    last_seen=now,
                    scan_id=scan_id or existing.scan_id,
                    hostname=hostname or existing.hostname,
                    protocol=protocol or existing.protocol,
                    service=service or existing.service,
                    status=status or existing.status,
                    metadata_=new_meta,
                )
                .returning(Asset)
            )
            result = await self.db.execute(update_stmt)
            await self.db.flush()
            return result.scalar_one()
        else:
            asset = Asset(
                user_id=user_id,
                scan_id=scan_id,
                host=host,
                ip_address=ip_address,
                hostname=hostname,
                port=port,
                protocol=protocol,
                service=service,
                status=status,
                first_seen=now,
                last_seen=now,
                metadata_=metadata or {},
                ownership_type=ownership_type,
                client_id=client_id,
                client_asset_id=client_asset_id,
                assignment_id=assignment_id,
            )
            self.db.add(asset)
            await self.db.flush()
            await self.db.refresh(asset)
            return asset

    async def list_user_assets(
        self,
        user_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
        host_filter: Optional[str] = None,
    ) -> List[Asset]:
        stmt = select(Asset).where(Asset.user_id == user_id)
        if host_filter:
            stmt = stmt.where(
                (Asset.host.ilike(f"%{host_filter}%"))
                | (Asset.ip_address.ilike(f"%{host_filter}%"))
                | (Asset.hostname.ilike(f"%{host_filter}%"))
            )
        stmt = stmt.order_by(Asset.last_seen.desc()).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_all_assets(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        host_filter: Optional[str] = None,
    ) -> List[Asset]:
        stmt = select(Asset)
        if host_filter:
            stmt = stmt.where(
                (Asset.host.ilike(f"%{host_filter}%"))
                | (Asset.ip_address.ilike(f"%{host_filter}%"))
                | (Asset.hostname.ilike(f"%{host_filter}%"))
            )
        stmt = stmt.order_by(Asset.last_seen.desc()).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_user_asset(self, user_id: int, asset_id: int) -> Optional[Asset]:
        stmt = select(Asset).where(and_(Asset.id == asset_id, Asset.user_id == user_id))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def count_user_assets(self, user_id: int) -> int:
        stmt = select(func.count()).select_from(Asset).where(Asset.user_id == user_id)
        return int((await self.db.execute(stmt)).scalar_one())

    async def count_all_assets(self) -> int:
        return await self.count()

    async def count_user_open_ports(self, user_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(Asset)
            .where(
                and_(
                    Asset.user_id == user_id,
                    Asset.port.is_not(None),
                )
            )
        )
        return int((await self.db.execute(stmt)).scalar_one())

    async def recent_user_assets(self, user_id: int, limit: int = 5) -> List[Asset]:
        stmt = (
            select(Asset)
            .where(Asset.user_id == user_id)
            .order_by(Asset.last_seen.desc())
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_user_assets_by_host(
        self,
        user_id: int,
        host: str,
    ) -> List[Asset]:
        stmt = (
            select(Asset)
            .where(and_(Asset.user_id == user_id, Asset.host == host))
            .order_by(Asset.port.asc().nulls_last(), Asset.last_seen.desc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_all_assets_by_host(self, host: str) -> List[Asset]:
        stmt = (
            select(Asset)
            .where(Asset.host == host)
            .order_by(Asset.port.asc().nulls_last(), Asset.last_seen.desc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def delete_user_asset(self, user_id: int, asset_id: int) -> bool:
        """Delete a single asset owned by the user.  Caller is responsible
        for the ownership-based delete rule (USER_MANUAL only)."""
        stmt = select(Asset).where(and_(Asset.id == asset_id, Asset.user_id == user_id))
        asset = (await self.db.execute(stmt)).scalar_one_or_none()
        if not asset:
            return False
        await self.delete(asset.id)
        return True
