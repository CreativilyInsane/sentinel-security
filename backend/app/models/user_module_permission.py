# backend/app/models/user_module_permission.py
"""Per-user module permissions.

The admin can grant or revoke access to specific recon modules
(host_discovery, port_scan, service_detection, whois, dns, ssl, http,
screenshot) and page-level features (network_scan, assets, reports,
previous_scans, targets) on a per-user basis.

If no UserModulePermission rows exist for a user, ALL modules are
allowed (default-open).  Once the admin creates at least one row,
only explicitly-allowed modules are accessible.
"""
from sqlalchemy import String, Integer, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, Optional

from app.db.base import Base
from app.models.base import BaseMixin

if TYPE_CHECKING:
    from app.models.user import User


class UserModulePermission(Base, BaseMixin):
    __tablename__ = "user_module_permissions"
    __table_args__ = (
        UniqueConstraint("user_id", "module_name", name="uq_user_module"),
    )

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    module_name: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "host_discovery", "port_scan", "assets", "reports"
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="1")

    user: Mapped[Optional["User"]] = relationship("User", backref="module_permissions")

    def __repr__(self) -> str:
        return f"<UserModulePermission(user_id={self.user_id}, module={self.module_name}, allowed={self.is_allowed})>"
