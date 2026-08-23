# backend/app/recon/repositories/scan_repository.py
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import select, func, update, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.recon.models.scan import Scan
from app.recon.models.scan_result import ScanResult
from app.recon.models.scan_module_status import ScanModuleStatus
from app.repositories.base import BaseRepository
from app.core.constants import ScanStatus, ScanModuleStatusValue


class ScanRepository(BaseRepository[Scan]):
    def __init__(self, db: AsyncSession):
        super().__init__(Scan, db)

    # ---- queries ---------------------------------------------------------
    async def get_user_scans(
        self,
        user_id: int,
        *,
        skip: int = 0,
        limit: int = 50,
        status_filter: Optional[str] = None,
        target_filter: Optional[str] = None,
    ) -> List[Scan]:
        stmt = select(Scan).where(Scan.user_id == user_id)
        if status_filter:
            stmt = stmt.where(Scan.status == status_filter)
        if target_filter:
            stmt = stmt.where(Scan.target.ilike(f"%{target_filter}%"))
        stmt = stmt.order_by(Scan.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_all_scans(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        status_filter: Optional[str] = None,
        target_filter: Optional[str] = None,
    ) -> List[Scan]:
        stmt = select(Scan)
        if status_filter:
            stmt = stmt.where(Scan.status == status_filter)
        if target_filter:
            stmt = stmt.where(Scan.target.ilike(f"%{target_filter}%"))
        stmt = stmt.order_by(Scan.created_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_user_scans(self, user_id: int) -> int:
        stmt = select(func.count()).select_from(Scan).where(Scan.user_id == user_id)
        result = await self.db.execute(stmt)
        return int(result.scalar_one())

    async def count_all_scans(self) -> int:
        return await self.count()

    async def count_active_user_scans(self, user_id: int) -> int:
        """Return number of scans the user currently has in QUEUED or RUNNING state."""
        stmt = (
            select(func.count())
            .select_from(Scan)
            .where(
                and_(
                    Scan.user_id == user_id,
                    Scan.status.in_([ScanStatus.QUEUED, ScanStatus.RUNNING]),
                )
            )
        )
        result = await self.db.execute(stmt)
        return int(result.scalar_one())

    async def get_scan_with_results(self, scan_id: int) -> Optional[Scan]:
        stmt = (
            select(Scan)
            .options(selectinload(Scan.results), selectinload(Scan.module_statuses))
            .where(Scan.id == scan_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_scan_owner(self, scan_id: int) -> Optional[int]:
        stmt = select(Scan.user_id).where(Scan.id == scan_id)
        result = await self.db.execute(stmt)
        row = result.first()
        return row[0] if row else None

    # ---- mutations -------------------------------------------------------
    async def create_scan(self, scan: Scan) -> Scan:
        return await self.create(scan)

    async def update_status(
        self,
        scan_id: int,
        *,
        status: str,
        error_message: Optional[str] = None,
        progress: Optional[int] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> Optional[Scan]:
        values: Dict[str, Any] = {"status": status}
        if error_message is not None:
            values["error_message"] = error_message
        if progress is not None:
            values["progress"] = max(0, min(100, int(progress)))
        if started_at is not None:
            values["started_at"] = started_at
        if completed_at is not None:
            values["completed_at"] = completed_at
        stmt = update(Scan).where(Scan.id == scan_id).values(**values).returning(Scan)
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.scalar_one_or_none()

    async def set_celery_task_id(self, scan_id: int, task_id: str) -> None:
        stmt = update(Scan).where(Scan.id == scan_id).values(celery_task_id=task_id)
        await self.db.execute(stmt)
        await self.db.flush()

    async def append_progress(self, scan_id: int, progress_delta: int) -> None:
        stmt = (
            update(Scan)
            .where(Scan.id == scan_id)
            .values(progress=func.least(100, Scan.progress + progress_delta))
        )
        await self.db.execute(stmt)
        await self.db.flush()


class ScanResultRepository(BaseRepository[ScanResult]):
    def __init__(self, db: AsyncSession):
        super().__init__(ScanResult, db)

    async def add_result(
        self,
        scan_id: int,
        result_type: str,
        data: Dict[str, Any],
        error: Optional[str] = None,
    ) -> ScanResult:
        result = ScanResult(
            scan_id=scan_id,
            result_type=result_type,
            data=data,
            error=error,
        )
        self.db.add(result)
        await self.db.flush()
        await self.db.refresh(result)
        return result

    async def list_for_scan(self, scan_id: int) -> List[ScanResult]:
        stmt = (
            select(ScanResult)
            .where(ScanResult.scan_id == scan_id)
            .order_by(ScanResult.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class ScanModuleStatusRepository(BaseRepository[ScanModuleStatus]):
    """Per-module lifecycle tracking for scans."""

    def __init__(self, db: AsyncSession):
        super().__init__(ScanModuleStatus, db)

    async def list_for_scan(self, scan_id: int) -> List[ScanModuleStatus]:
        stmt = (
            select(ScanModuleStatus)
            .where(ScanModuleStatus.scan_id == scan_id)
            .order_by(ScanModuleStatus.id.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def init_for_scan(self, scan_id: int, modules: List[str]) -> None:
        """Create QUEUED rows for each module in ``modules``.

        Existing rows for the (scan_id, module_name) pair are left
        untouched (idempotent — safe to call if rows already exist).
        """
        existing_stmt = select(ScanModuleStatus).where(
            ScanModuleStatus.scan_id == scan_id
        )
        existing = list((await self.db.execute(existing_stmt)).scalars().all())
        existing_names = {row.module_name for row in existing}
        for name in modules:
            if name in existing_names:
                continue
            self.db.add(
                ScanModuleStatus(
                    scan_id=scan_id,
                    module_name=name,
                    status=ScanModuleStatusValue.QUEUED,
                    progress=0,
                )
            )
        await self.db.flush()

    async def set_module_status(
        self,
        scan_id: int,
        module_name: str,
        *,
        status: str,
        error_message: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        progress: Optional[int] = None,
    ) -> Optional[ScanModuleStatus]:
        stmt = (
            update(ScanModuleStatus)
            .where(
                and_(
                    ScanModuleStatus.scan_id == scan_id,
                    ScanModuleStatus.module_name == module_name,
                )
            )
            .values(
                status=status,
                error_message=error_message,
                started_at=started_at,
                completed_at=completed_at,
                progress=progress if progress is not None else ScanModuleStatus.progress,
            )
            .returning(ScanModuleStatus)
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.scalar_one_or_none()

    async def cancel_pending(self, scan_id: int) -> int:
        """Mark any QUEUED or RUNNING module rows for this scan as CANCELLED.

        Returns the number of rows updated.
        """
        stmt = (
            update(ScanModuleStatus)
            .where(
                and_(
                    ScanModuleStatus.scan_id == scan_id,
                    ScanModuleStatus.status.in_(
                        [ScanModuleStatusValue.QUEUED, ScanModuleStatusValue.RUNNING]
                    ),
                )
            )
            .values(
                status=ScanModuleStatusValue.CANCELLED,
                completed_at=datetime.utcnow(),
            )
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return int(result.rowcount or 0)
