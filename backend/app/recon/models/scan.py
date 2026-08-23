# backend/app/recon/models/scan.py
from sqlalchemy import String, Integer, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, Optional, List
from datetime import datetime

from app.db.base import Base
from app.models.base import BaseMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.recon.models.scan_result import ScanResult
    from app.recon.models.asset import Asset


class Scan(Base, BaseMixin):
    """A single reconnaissance scan launched by an authenticated user."""
    __tablename__ = "recon_scans"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target: Mapped[str] = mapped_column(String(512), nullable=False)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)  # DOMAIN/IP/URL/CIDR
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="QUEUED", index=True)
    modules: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    port_preset: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    custom_ports: Mapped[Optional[List[int]]] = mapped_column(JSON, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0..100
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # --- Phase 17 ownership / provenance fields ----------------------------
    # Where the scan target originated.
    ownership_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="USER_MANUAL", server_default="USER_MANUAL", index=True,
    )
    # CLIENT | ASSIGNED_TARGET | USER_MANUAL
    client_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)
    client_asset_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("client_assets.id", ondelete="SET NULL"), nullable=True)
    assignment_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("target_assignments.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", backref="recon_scans")
    results: Mapped[List["ScanResult"]] = relationship(
        "ScanResult", back_populates="scan", cascade="all, delete-orphan"
    )
    assets: Mapped[List["Asset"]] = relationship(
        "Asset", back_populates="scan", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Scan(id={self.id}, target={self.target}, status={self.status})>"
