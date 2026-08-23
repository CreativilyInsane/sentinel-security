# backend/app/recon/models/scan_result.py
from sqlalchemy import String, Integer, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, Optional, Dict, Any

from app.db.base import Base
from app.models.base import BaseMixin

if TYPE_CHECKING:
    from app.recon.models.scan import Scan


class ScanResult(Base, BaseMixin):
    """A typed result block produced by a recon module for a given scan."""
    __tablename__ = "recon_scan_results"

    scan_id: Mapped[int] = mapped_column(Integer, ForeignKey("recon_scans.id", ondelete="CASCADE"), nullable=False, index=True)
    result_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # HOST_DISCOVERY / PORT_SCAN / SERVICE / WHOIS / DNS / SSL / HTTP / SCREENSHOT
    data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    scan: Mapped["Scan"] = relationship("Scan", back_populates="results")

    def __repr__(self) -> str:
        return f"<ScanResult(id={self.id}, scan_id={self.scan_id}, type={self.result_type})>"
