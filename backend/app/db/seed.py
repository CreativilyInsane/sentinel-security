# backend/app/db/seed.py
import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.role import Role
from app.models.user import User
from app.core.config import settings
from app.core.constants import Roles
from app.auth.passwords import hash_password
from app.core.logging import logger

async def seed_data():
    """Seeds the database with initial roles and the admin user."""
    async with AsyncSessionLocal() as session:
        async with session.begin():
            # 1. Seed Roles
            roles_to_create = [
                {"name": Roles.ADMIN},
                {"name": Roles.USER}
            ]
            
            for role_data in roles_to_create:
                stmt = select(Role).where(Role.name == role_data["name"])
                result = await session.execute(stmt)
                if not result.scalar_one_or_none():
                    session.add(Role(**role_data))
                    logger.info(f"Created role: {role_data['name']}")
            
            await session.flush()  # Ensure roles are assigned IDs before proceeding
            
            # 2. Seed Admin User
            stmt = select(User).where(User.username == settings.ADMIN_USERNAME)
            result = await session.execute(stmt)
            if not result.scalar_one_or_none():
                # Fetch the Admin role ID
                role_stmt = select(Role).where(Role.name == Roles.ADMIN)
                admin_role = (await session.execute(role_stmt)).scalar_one()
                
                admin_user = User(
                    username=settings.ADMIN_USERNAME,
                    email=settings.ADMIN_EMAIL,
                    password_hash=hash_password(settings.ADMIN_PASSWORD),
                    role_id=admin_role.id,
                    is_active=True
                )
                session.add(admin_user)
                logger.info(f"Created admin user: {settings.ADMIN_USERNAME}")

if __name__ == "__main__":
    logger.info("Starting database seeding...")
    asyncio.run(seed_data())
    logger.info("Database seeding completed.")