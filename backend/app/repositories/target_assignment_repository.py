# backend/app/repositories/target_assignment_repository.py
"""Repository for TargetAssignment + AssignmentNotification models."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select, func, and_, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.target_assignment import TargetAssignment, AssignmentNotification
from app.repositories.base import BaseRepository


class TargetAssignmentRepository(BaseRepository[TargetAssignment]):
    def __init__(self, db: AsyncSession):
        super().__init__(TargetAssignment, db)

    async def list_for_user(self, user_id: int, *, active_only: bool = True) -> List[TargetAssignment]:
        stmt = select(TargetAssignment).where(TargetAssignment.user_id == user_id)
        if active_only:
            stmt = stmt.where(TargetAssignment.is_active == True)  # noqa: E712
        stmt = stmt.order_by(TargetAssignment.created_at.desc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_all(self, *, skip: int = 0, limit: int = 200, user_id: Optional[int] = None, client_id: Optional[int] = None) -> List[TargetAssignment]:
        stmt = select(TargetAssignment)
        if user_id is not None:
            stmt = stmt.where(TargetAssignment.user_id == user_id)
        if client_id is not None:
            stmt = stmt.where(TargetAssignment.client_id == client_id)
        stmt = stmt.order_by(TargetAssignment.created_at.desc()).offset(skip).limit(limit)
        return list((await self.db.execute(stmt)).scalars().all())

    async def find_client_assignment(self, user_id: int, client_id: int) -> Optional[TargetAssignment]:
        stmt = select(TargetAssignment).where(
            and_(
                TargetAssignment.user_id == user_id,
                TargetAssignment.client_id == client_id,
                TargetAssignment.assignment_type == "CLIENT",
            )
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def find_direct_assignment(self, user_id: int, target_value: str) -> Optional[TargetAssignment]:
        stmt = select(TargetAssignment).where(
            and_(
                TargetAssignment.user_id == user_id,
                TargetAssignment.target_value == target_value,
                TargetAssignment.assignment_type == "DIRECT_TARGET",
            )
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def find_active_assignments_for_target(
        self, user_id: int, target_value: str
    ) -> List[TargetAssignment]:
        """All active assignments whose target_value matches exactly."""
        stmt = (
            select(TargetAssignment)
            .where(
                and_(
                    TargetAssignment.user_id == user_id,
                    TargetAssignment.is_active == True,  # noqa: E712
                    TargetAssignment.target_value == target_value,
                )
            )
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def set_active(self, assignment_id: int, is_active: bool) -> Optional[TargetAssignment]:
        stmt = (
            update(TargetAssignment)
            .where(TargetAssignment.id == assignment_id)
            .values(is_active=is_active)
            .returning(TargetAssignment)
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.scalar_one_or_none()

    async def count_active_for_client(self, client_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(TargetAssignment)
            .where(
                and_(
                    TargetAssignment.client_id == client_id,
                    TargetAssignment.is_active == True,  # noqa: E712
                )
            )
        )
        return int((await self.db.execute(stmt)).scalar_one())

    async def count_users_for_client(self, client_id: int) -> int:
        stmt = (
            select(func.count(func.distinct(TargetAssignment.user_id)))
            .select_from(TargetAssignment)
            .where(
                and_(
                    TargetAssignment.client_id == client_id,
                    TargetAssignment.is_active == True,  # noqa: E712
                )
            )
        )
        return int((await self.db.execute(stmt)).scalar_one())

    async def list_active_user_client_ids(self, user_id: int) -> List[int]:
        """Distinct client_ids the user has an active CLIENT assignment for."""
        stmt = (
            select(TargetAssignment.client_id)
            .where(
                and_(
                    TargetAssignment.user_id == user_id,
                    TargetAssignment.is_active == True,  # noqa: E712
                    TargetAssignment.assignment_type == "CLIENT",
                    TargetAssignment.client_id.is_not(None),
                )
            )
            .distinct()
        )
        rows = (await self.db.execute(stmt)).all()
        return [r[0] for r in rows if r[0] is not None]


class AssignmentNotificationRepository(BaseRepository[AssignmentNotification]):
    def __init__(self, db: AsyncSession):
        super().__init__(AssignmentNotification, db)

    async def create_notification(
        self,
        *,
        user_id: int,
        assignment_id: Optional[int],
        type_: str,
        message: str,
    ) -> AssignmentNotification:
        n = AssignmentNotification(
            user_id=user_id,
            assignment_id=assignment_id,
            type=type_,
            message=message,
        )
        self.db.add(n)
        await self.db.flush()
        await self.db.refresh(n)
        return n

    async def list_for_user(self, user_id: int, *, unread_only: bool = False, limit: int = 100) -> List[AssignmentNotification]:
        stmt = select(AssignmentNotification).where(AssignmentNotification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(AssignmentNotification.is_read == False)  # noqa: E712
        stmt = stmt.order_by(AssignmentNotification.created_at.desc()).limit(limit)
        return list((await self.db.execute(stmt)).scalars().all())

    async def count_unread(self, user_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(AssignmentNotification)
            .where(
                and_(
                    AssignmentNotification.user_id == user_id,
                    AssignmentNotification.is_read == False,  # noqa: E712
                )
            )
        )
        return int((await self.db.execute(stmt)).scalar_one())

    async def mark_read(self, user_id: int, notification_ids: Optional[List[int]] = None) -> int:
        """Mark notifications as read. Returns the number of rows updated."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(AssignmentNotification)
            .where(
                and_(
                    AssignmentNotification.user_id == user_id,
                    AssignmentNotification.is_read == False,  # noqa: E712
                )
            )
            .values(is_read=True, read_at=now)
        )
        if notification_ids:
            stmt = stmt.where(AssignmentNotification.id.in_(notification_ids))
        result = await self.db.execute(stmt)
        await self.db.flush()
        return int(result.rowcount or 0)
