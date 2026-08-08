# backend/app/schemas/user.py
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from datetime import datetime
from typing import Optional
from app.schemas.role import RoleRead

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)
    role_name: str = Field(default="User", description="Role name e.g. 'Administrator' or 'User'")

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(char.islower() for char in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char in "@$!%*?&" for char in v):
            raise ValueError('Password must contain at least one special character (@$!%*?&)')
        return v

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    role_name: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(char.islower() for char in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char in "@$!%*?&" for char in v):
            raise ValueError('Password must contain at least one special character (@$!%*?&)')
        return v

class UserRead(UserBase):
    id: int
    is_active: bool
    role: RoleRead
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)