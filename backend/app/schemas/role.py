# backend/app/schemas/role.py
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class RoleRead(BaseModel):
    id: int
    name: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)