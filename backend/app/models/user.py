# backend/app/models/user.py
from sqlalchemy import String, Boolean, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.base import BaseMixin
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.models.role import Role

class User(Base, BaseMixin):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationship: Many Users belong to One Role
    role: Mapped["Role"] = relationship("Role", back_populates="users")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"