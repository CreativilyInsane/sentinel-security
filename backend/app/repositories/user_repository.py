# backend/app/repositories/user_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional, List
from app.models.user import User
from app.repositories.base import BaseRepository

class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    async def get_by_username(self, username: str) -> Optional[User]:
        # Added selectinload to prevent async lazy-loading crashes
        stmt = select(User).options(selectinload(User.role)).where(User.username == username)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).options(selectinload(User.role)).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_with_role(self, id: int) -> Optional[User]:
        stmt = select(User).options(selectinload(User.role)).where(User.id == id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
        
    async def get_all_with_roles(self, skip: int = 0, limit: int = 100) -> List[User]:
        stmt = select(User).options(selectinload(User.role)).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()