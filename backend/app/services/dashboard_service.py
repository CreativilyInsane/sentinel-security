# backend/app/services/dashboard_service.py
"""Dashboard service.

Returns aggregated metrics for the dashboard UI.  Recon stats are pulled
from the live PostgreSQL tables when a db session is provided; otherwise
the service falls back to the original mock data so unit tests that
construct the service without a db session continue to work.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.dashboard import DashboardData, DashboardStats, ActivityItem
from app.core.constants import ScanStatus
from app.core.logging import logger


class DashboardService:
    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db

    async def get_dashboard_data(self) -> DashboardData:
        """Returns dashboard metrics.  Uses live data when a db session is
        available; otherwise returns the original mock data."""
        if self.db is None:
            return self._mock_data()

        try:
            return await self._live_data()
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Dashboard live data failed, falling back to mock: {exc}")
            return self._mock_data()

    # ---- live data -----------------------------------------------------
    async def _live_data(self) -> DashboardData:
        from app.recon.models.scan import Scan
        from app.recon.models.asset import Asset

        db = self.db
        # Counts
        total_scans = int((await db.execute(
            select(func.count()).select_from(Scan)
        )).scalar_one())
        running_scans = int((await db.execute(
            select(func.count()).select_from(Scan).where(
                Scan.status.in_([ScanStatus.QUEUED, ScanStatus.RUNNING])
            )
        )).scalar_one())
        total_assets = int((await db.execute(
            select(func.count()).select_from(Asset)
        )).scalar_one())
        open_ports = int((await db.execute(
            select(func.count()).select_from(Asset).where(Asset.port.is_not(None))
        )).scalar_one())

        # Recent scans (last 5)
        recent_scans_stmt = (
            select(Scan)
            .order_by(Scan.created_at.desc())
            .limit(5)
        )
        recent_scans = list((await db.execute(recent_scans_stmt)).scalars().all())

        recent_activity: list[ActivityItem] = []
        now = datetime.now(timezone.utc)
        for idx, s in enumerate(recent_scans, start=1):
            ts = s.created_at or now
            description = f"Scan #{s.id} on {s.target} — {s.status} ({s.progress}%)"
            recent_activity.append(ActivityItem(
                id=idx, type="Scan", description=description, timestamp=ts,
            ))

        # Recent assets (last 3)
        recent_assets_stmt = (
            select(Asset)
            .order_by(Asset.last_seen.desc())
            .limit(3)
        )
        recent_assets = list((await db.execute(recent_assets_stmt)).scalars().all())
        for idx, a in enumerate(recent_assets, start=len(recent_activity) + 1):
            ts = a.last_seen or now
            description = f"Asset discovered: {a.host}" + (f" ({a.ip_address})" if a.ip_address else "")
            recent_activity.append(ActivityItem(
                id=idx, type="Asset", description=description, timestamp=ts,
            ))

        # Sort by timestamp desc
        recent_activity.sort(key=lambda x: x.timestamp, reverse=True)

        last_scan_str = "Never"
        if recent_scans:
            latest = recent_scans[0]
            if latest.completed_at:
                delta = now - latest.completed_at
                hours = int(delta.total_seconds() // 3600)
                last_scan_str = f"{hours}h ago" if hours > 0 else "just now"
            elif latest.created_at:
                delta = now - latest.created_at
                hours = int(delta.total_seconds() // 3600)
                last_scan_str = f"{hours}h ago" if hours > 0 else "just now"

        system_status = "Operational" if running_scans == 0 else f"{running_scans} active"

        stats = DashboardStats(
            total_assets=total_assets,
            last_scan=last_scan_str,
            reports_generated=total_scans,  # Every completed scan can have a report
            system_status=system_status,
        )
        return DashboardData(stats=stats, recent_activity=recent_activity)

    # ---- mock fallback -------------------------------------------------
    def _mock_data(self) -> DashboardData:
        now = datetime.now(timezone.utc)
        stats = DashboardStats(
            total_assets=0,
            last_scan="Never",
            reports_generated=0,
            system_status="Operational",
        )
        recent_activity = [
            ActivityItem(
                id=1, type="System",
                description="No scans yet — start one from the Network Scan page.",
                timestamp=now,
            ),
        ]
        return DashboardData(stats=stats, recent_activity=recent_activity)
