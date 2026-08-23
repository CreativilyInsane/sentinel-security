# backend/app/schemas/common.py
from pydantic import BaseModel
from typing import Optional, Any, List, Generic, TypeVar

T = TypeVar('T')

class StandardResponse(BaseModel, Generic[T]):
    success: bool = True
    message: str = "Operation successful"
    data: Optional[T] = None

class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    details: Optional[Any] = None

class PaginatedResponse(BaseModel, Generic[T]):
    success: bool = True
    message: str = "Operation successful"
    total: int
    skip: int
    limit: int
    data: List[T]