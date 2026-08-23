# backend/app/recon/workers/tasks.py
"""Celery tasks for the recon module.

The API layer creates a :class:`Scan` row and then enqueues
``run_scan(scan_id)`` on the Celery worker.  The worker owns the full
lifecycle of the scan and writes results / status updates directly back
to PostgreSQL via its own synchronous-ish async session (Celery workers
run in a thread pool, so we bridge into asyncio via ``asyncio.run``).
"""
from __future__ import annotations

import asyncio
import traceback

from app.core.logging import logger
from app.recon.workers.celery_app import celery_app


@celery_app.task(name="recon.tasks.run_scan", bind=True, max_retries=0)
def run_scan(self, scan_id: int) -> dict:
    """Top-level entry point — runs the full scan pipeline for ``scan_id``.

    Returns a small summary dict so the Celery result backend exposes
    something useful for operators inspecting task results.
    """
    logger.info(f"[celery] run_scan(scan_id={scan_id}) starting")
    try:
        asyncio.run(_execute_scan(scan_id))
        return {"scan_id": scan_id, "ok": True}
    except Exception as exc:  # noqa: BLE001
        logger.error(
            f"[celery] run_scan(scan_id={scan_id}) crashed: {exc}\n{traceback.format_exc()}"
        )
        # Persist the failure on the scan row
        try:
            asyncio.run(_mark_failed(scan_id, str(exc)))
        except Exception:  # noqa: BLE001
            pass
        return {"scan_id": scan_id, "ok": False, "error": str(exc)}


# ---- internal helpers -------------------------------------------------

async def _get_worker_session():
    """Create a fresh async engine + session for each Celery task.

    The module-level ``AsyncSessionLocal`` in ``app.db.session`` binds its
    connection pool to the event loop that was active at import time.  When
    ``asyncio.run()`` creates a *new* loop for every task, the pooled
    connections still reference the old (closed) loop, causing
    ``Future attached to a different loop`` errors.

    By building a short-lived engine per invocation we guarantee that all
    connections are created on the *current* loop and disposed when the
    task finishes.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.core.config import settings

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=4,
    )
    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return engine, factory()


async def _execute_scan(scan_id: int) -> None:
    """Open a fresh DB session inside the worker and run the scan."""
    from app.recon.services.scan_service import ScanService

    engine, session = await _get_worker_session()
    try:
        service = ScanService(session)
        await service.execute_scan(scan_id)
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
        await engine.dispose()


async def _mark_failed(scan_id: int, error: str) -> None:
    from datetime import datetime, timezone
    from app.recon.repositories.scan_repository import ScanRepository
    from app.core.constants import ScanStatus

    engine, session = await _get_worker_session()
    try:
        repo = ScanRepository(session)
        await repo.update_status(
            scan_id,
            status=ScanStatus.FAILED,
            error_message=error[:500],
            completed_at=datetime.now(timezone.utc),
        )
        await session.commit()
    except Exception:  # noqa: BLE001
        await session.rollback()
    finally:
        await session.close()
        await engine.dispose()
