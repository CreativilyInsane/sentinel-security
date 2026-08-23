# backend/app/models/user_network.py
"""Per-user allowed network permissions for the recon module.

Allows administrators to grant specific users the ability to scan
private/internal CIDR ranges (e.g. 192.168.1.0/24).
"""
from sqlalchemy import Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, Optional

from app.db.base import Base
from app.models.base import BaseMixin

if TYPE_CHECKING:
    from app.models.user import User


class UserAllowedNetwork(Base, BaseMixin):
    __tablename__ = "user_allowed_networks"
    __table_args__ = (
        UniqueConstraint("user_id", "network", name="uq_user_network"),
    )

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    network: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "192.168.1.0/24"

    user: Mapped[Optional["User"]] = relationship("User", back_populates="allowed_networks")

    def __repr__(self) -> str:
        return f"<UserAllowedNetwork(id={self.id}, user_id={self.user_id}, network={self.network})>"
