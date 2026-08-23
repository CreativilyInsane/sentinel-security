# backend/app/recon/models/asset.py
from sqlalchemy import String, Integer, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, Optional, Dict, Any
from datetime import datetime

from app.db.base import Base
from app.models.base import BaseMixin

if TYPE_CHECKING:
    from app.recon.models.scan import Scan


class Asset(Base, BaseMixin):
    """A discovered host/system persisted across scans.

    Assets are upserted from scan results so the inventory accumulates over
    time.  The (user_id, host, ip_address, port) tuple is treated as the
    natural uniqueness key — when a scan re-discovers an existing asset we
    update last_seen and metadata instead of inserting a duplicate row.
    """
    __tablename__ = "recon_assets"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    scan_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("recon_scans.id", ondelete="SET NULL"), nullable=True, index=True)

    host: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    hostname: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    protocol: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # tcp / udp
    service: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # up / down / open / closed
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)

    # --- Phase 17 ownership / provenance fields ----------------------------
    ownership_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="USER_MANUAL", server_default="USER_MANUAL", index=True,
    )
    # CLIENT | ASSIGNED_TARGET | USER_MANUAL
    client_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)
    client_asset_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("client_assets.id", ondelete="SET NULL"), nullable=True)
    assignment_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("target_assignments.id", ondelete="SET NULL"), nullable=True)

    scan: Mapped[Optional["Scan"]] = relationship("Scan", back_populates="assets")

    def __repr__(self) -> str:
        return f"<Asset(id={self.id}, host={self.host}, ip={self.ip_address}, port={self.port})>"
