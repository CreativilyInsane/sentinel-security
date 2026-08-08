# backend/app/models/audit_log.py
from sqlalchemy import String, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.models.base import BaseMixin
from typing import Optional  # <-- ADD THIS LINE

class AuditLog(Base, BaseMixin):
    """Placeholder model for audit logging."""
    __tablename__ = "audit_logs"

    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=True)