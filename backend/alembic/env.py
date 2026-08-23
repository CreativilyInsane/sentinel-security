# backend/alembic/env.py
import asyncio
import sys
import os
from logging.config import fileConfig

# Add the parent directory to sys.path so Alembic can find the 'app' module
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import application settings and Base
from app.core.config import settings
from app.db.base import Base
# IMPORTANT: Import all models here so Alembic can detect them for autogeneration
from app.models import User, Role, AuditLog
from app.models.client import Client, ClientAsset
from app.models.target_assignment import TargetAssignment, AssignmentNotification
from app.models.user_active_target import UserActiveTarget
from app.models.user_module_permission import UserModulePermission
from app.recon.models.scan import Scan
from app.recon.models.scan_result import ScanResult
from app.recon.models.asset import Asset

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())