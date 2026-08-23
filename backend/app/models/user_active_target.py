# backend/app/models/user_active_target.py
"""UserActiveTarget — user-level selection of which assigned targets are
"active" (visible in the Network Scan dropdown).

When an admin assigns a Client or direct target to a user, all its assets
appear on the Targets page.  The user can then toggle individual targets
as "active" — only active ones show up in the Network Scan multi-select.

This is distinct from the admin-controlled ``TargetAssignment.is_active``
flag: the admin controls whether an assignment exists at all; the user
controls which of their assigned targets they want to scan right now.
"""
from sqlalchemy import Integer, String, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, Optional

from app.db.base import Base
from app.models.base import BaseMixin

if TYPE_CHECKING:
    from app.models.user import User


class UserActiveTarget(Base, BaseMixin):
    __tablename__ = "user_active_targets"
    __table_args__ = (
        UniqueConstraint("user_id", "target_key", name="uq_user_active_target_key"),
    )

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # Composite key that uniquely identifies an authorized target entry:
    # "{assignment_id}:{target_value}".  This matches the frontend's
    # targetKey() function.
    target_key: Mapped[str] = mapped_column(String(320), nullable=False)
    assignment_id: Mapped[int] = mapped_column(Integer, ForeignKey("target_assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    target_value: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="1")

    user: Mapped[Optional["User"]] = relationship("User", backref="active_targets")

    def __repr__(self) -> str:
        return f"<UserActiveTarget(id={self.id}, user_id={self.user_id}, key={self.target_key}, active={self.is_active})>"
