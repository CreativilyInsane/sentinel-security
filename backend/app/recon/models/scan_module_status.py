# backend/app/recon/models/scan_module_status.py
"""Per-module status tracking for scans.

Each scan's selected modules get one row whose status moves through:

    QUEUED -> RUNNING -> COMPLETED | FAILED | CANCELLED

The API layer consults these rows to derive the overall scan status
and to render the real-time progress UI.
"""
from sqlalchemy import String, Integer, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, Optional
from datetime import datetime

from app.db.base import Base
from app.models.base import BaseMixin

if TYPE_CHECKING:
    from app.recon.models.scan import Scan


class ScanModuleStatus(Base, BaseMixin):
    __tablename__ = "recon_scan_module_status"
    __table_args__ = (
        # Unique constraint is declared in the migration; we re-declare
        # it here so SQLAlchemy knows about it for ORM-level operations.
        # The actual constraint name must match the migration.
    )

    scan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recon_scans.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    module_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="QUEUED")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    scan: Mapped[Optional["Scan"]] = relationship("Scan", backref="module_statuses")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ScanModuleStatus(scan_id={self.scan_id}, module={self.module_name}, status={self.status})>"
