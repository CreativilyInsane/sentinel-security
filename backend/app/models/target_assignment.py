# backend/app/models/target_assignment.py
"""TargetAssignment + AssignmentNotification models.

A TargetAssignment records that an administrator has authorised a user
to scan a specific target.  Two assignment types are supported:

* ``CLIENT``         — the entire Client (all of its active ClientAssets)
* ``DIRECT_TARGET``  — a single IP or CIDR, optionally sourced from a
                       ClientAsset but exposed to the user as a direct
                       authorisation.

The TargetAuthorizationService consults these rows when deciding whether
a particular scan target is permitted for a given user.

AssignmentNotification rows drive the "New Assignment" badge on the
user-side Targets page.  Rows are created when an admin assigns a target
and marked as read once the user opens the assignment.
"""
from sqlalchemy import String, Integer, ForeignKey, Boolean, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, Optional
from datetime import datetime

from app.db.base import Base
from app.models.base import BaseMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.client import Client, ClientAsset


class TargetAssignment(Base, BaseMixin):
    __tablename__ = "target_assignments"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=True, index=True)
    client_asset_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("client_assets.id", ondelete="SET NULL"), nullable=True, index=True)

    assignment_type: Mapped[str] = mapped_column(String(20), nullable=False)  # CLIENT | DIRECT_TARGET
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)      # CLIENT | IP | CIDR
    target_value: Mapped[str] = mapped_column(String(255), nullable=False)    # client name | IP | CIDR string
    target_label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # human-friendly label

    assigned_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="1")

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], backref="target_assignments")
    assigner: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assigned_by])
    client: Mapped[Optional["Client"]] = relationship("Client", back_populates="assignments")
    client_asset: Mapped[Optional["ClientAsset"]] = relationship("ClientAsset", back_populates="assignments")

    def __repr__(self) -> str:
        return (
            f"<TargetAssignment(id={self.id}, user_id={self.user_id}, "
            f"type={self.assignment_type}, target={self.target_value})>"
        )


class AssignmentNotification(Base, BaseMixin):
    """Per-user notification that an assignment was created/removed."""
    __tablename__ = "assignment_notifications"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assignment_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("target_assignments.id", ondelete="SET NULL"), nullable=True, index=True)

    type: Mapped[str] = mapped_column(String(40), nullable=False)
    # CLIENT_ASSIGNED | TARGET_ASSIGNED | TARGET_REMOVED | CLIENT_REMOVED
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], backref="assignment_notifications")
    assignment: Mapped[Optional["TargetAssignment"]] = relationship("TargetAssignment", foreign_keys=[assignment_id])

    def __repr__(self) -> str:
        return f"<AssignmentNotification(id={self.id}, user_id={self.user_id}, type={self.type})>"
