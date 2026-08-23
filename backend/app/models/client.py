# backend/app/models/client.py
"""Client and ClientAsset models.

A Client represents a company / customer / network environment whose
assets are being assessed.  An administrator creates Clients and assigns
them (or individual ClientAssets) to users via TargetAssignment.

ClientAsset is intentionally separate from the runtime-discovered
``recon.Asset`` model:

* ``ClientAsset``  — admin-curated inventory declared ahead of scanning
* ``recon.Asset``  — runtime-discovered host/port rows produced by scans

The two are linked through ``ownership_type`` / ``client_asset_id``
columns on ``recon.Asset`` when a scan originated from a Client assignment.
"""
from sqlalchemy import String, Integer, ForeignKey, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, Optional, List

from app.db.base import Base
from app.models.base import BaseMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.target_assignment import TargetAssignment


class Client(Base, BaseMixin):
    """A customer / network environment whose assets are under assessment."""
    __tablename__ = "clients"

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="1")
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    assets: Mapped[List["ClientAsset"]] = relationship(
        "ClientAsset", back_populates="client", cascade="all, delete-orphan",
    )
    assignments: Mapped[List["TargetAssignment"]] = relationship(
        "TargetAssignment", back_populates="client",
    )

    def __repr__(self) -> str:
        return f"<Client(id={self.id}, name={self.name})>"


class ClientAsset(Base, BaseMixin):
    """A single IP or CIDR range belonging to a Client."""
    __tablename__ = "client_assets"
    __table_args__ = (
        # Prevent duplicate (client_id, asset_type, value) tuples.  The
        # ``value`` column is either ip_address or cidr depending on
        # asset_type — enforced at the application layer.
    )

    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False)  # IP | IP_RANGE | DOMAIN
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    cidr: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    domain: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # device / network name
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    network_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    vlan_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="1")

    # Relationships
    client: Mapped["Client"] = relationship("Client", back_populates="assets")
    assignments: Mapped[List["TargetAssignment"]] = relationship(
        "TargetAssignment", back_populates="client_asset",
    )

    def __repr__(self) -> str:
        v = self.ip_address or self.cidr or self.domain or ""
        return f"<ClientAsset(id={self.id}, client_id={self.client_id}, type={self.asset_type}, value={v})>"
