# backend/app/models/user.py
from sqlalchemy import String, Boolean, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.base import BaseMixin
from typing import TYPE_CHECKING, Optional, List

if TYPE_CHECKING:
    from app.models.role import Role
    from app.models.user_network import UserAllowedNetwork

class User(Base, BaseMixin):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # NOTE: The legacy ``private_scan_enabled`` boolean column has been
    # REMOVED.  Private-network scan access is now controlled by the
    # per-user ``private_network_scan`` module permission stored in the
    # ``user_module_permissions`` table.

    # Relationship: Many Users belong to One Role
    role: Mapped["Role"] = relationship("Role", back_populates="users")

    # Relationship: Allowed networks for this user
    allowed_networks: Mapped[List["UserAllowedNetwork"]] = relationship(
        "UserAllowedNetwork", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"
