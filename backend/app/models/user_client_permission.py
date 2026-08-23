# backend/app/models/user_client_permission.py
"""Per-user, per-client access toggle.

Default-open semantics: if no row exists for (user_id, client_id),
the user is allowed.  An admin can explicitly create a row with
``enabled=false`` to revoke access for that user only, without
affecting other users or the underlying Client record itself.
"""
from sqlalchemy import String, Integer, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, Optional

from app.db.base import Base
from app.models.base import BaseMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.client import Client


class UserClientPermission(Base, BaseMixin):
    __tablename__ = "user_client_permissions"
    __table_args__ = (
        UniqueConstraint("user_id", "client_id", name="uq_user_client_perm"),
    )

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    client_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="1")

    user: Mapped[Optional["User"]] = relationship("User", backref="client_permissions")
    client: Mapped[Optional["Client"]] = relationship("Client", backref="user_permissions")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UserClientPermission(user_id={self.user_id}, client_id={self.client_id}, enabled={self.enabled})>"


class UserAssetPermission(Base, BaseMixin):
    """Per-user, per-asset access toggle (asset = ClientAsset row)."""

    __tablename__ = "user_asset_permissions"
    __table_args__ = (
        UniqueConstraint("user_id", "client_asset_id", name="uq_user_asset_perm"),
    )

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    client_asset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("client_assets.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="1")

    user: Mapped[Optional["User"]] = relationship("User", backref="asset_permissions")
    client_asset: Mapped[Optional["Client"]] = relationship("ClientAsset", backref="user_permissions")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<UserAssetPermission(user_id={self.user_id}, "
            f"client_asset_id={self.client_asset_id}, enabled={self.enabled})>"
        )
