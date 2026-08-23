# backend/app/services/user_service.py
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.repositories.user_repository import UserRepository
from app.repositories.role_repository import RoleRepository
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserRead
from app.auth.passwords import hash_password
from app.utils.errors import ConflictError, NotFoundError, BadRequestError
from typing import List, Optional

class UserService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db
        self.user_repo = UserRepository(db)
        self.role_repo = RoleRepository(db)

    async def create_user(self, user_data: UserCreate) -> UserRead:
        # Check if username exists
        if await self.user_repo.get_by_username(user_data.username):
            raise ConflictError(f"Username '{user_data.username}' is already taken")
            
        # Check if email exists
        if await self.user_repo.get_by_email(user_data.email):
            raise ConflictError(f"Email '{user_data.email}' is already registered")
            
        # Fetch role
        role = await self.role_repo.get_by_name(user_data.role_name)
        if not role:
            raise BadRequestError(f"Role '{user_data.role_name}' does not exist")
            
        # Create user entity (FIXED: instantiating the model instead of passing a dict)
        new_user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=hash_password(user_data.password),
            role_id=role.id,
            is_active=True
        )
        
        user = await self.user_repo.create(new_user)
        
        # Load role relationship for response schema
        await self.db.refresh(user, attribute_names=["role"])
        return UserRead.model_validate(user)

    async def get_users(self, skip: int = 0, limit: int = 100) -> List[UserRead]:
        users = await self.user_repo.get_all_with_roles(skip, limit)
        return [UserRead.model_validate(u) for u in users]

    async def get_user_by_id(self, user_id: int) -> UserRead:
        user = await self.user_repo.get_user_with_role(user_id)
        if not user:
            raise NotFoundError(f"User with ID {user_id} not found")
        return UserRead.model_validate(user)

    async def update_user(self, user_id: int, update_data: UserUpdate) -> UserRead:
        user = await self.user_repo.get_user_with_role(user_id)
        if not user:
            raise NotFoundError(f"User with ID {user_id} not found")
            
        update_dict = update_data.model_dump(exclude_unset=True)
        
        # Handle password update
        if "password" in update_dict and update_dict["password"]:
            update_dict["password_hash"] = hash_password(update_dict.pop("password"))
            
        # Handle role update
        if "role_name" in update_dict and update_dict["role_name"]:
            role = await self.role_repo.get_by_name(update_dict["role_name"])
            if not role:
                raise BadRequestError(f"Role '{update_dict['role_name']}' does not exist")
            update_dict["role_id"] = role.id
            del update_dict["role_name"]
            
        # Check for email conflicts if email is being updated
        if "email" in update_dict and update_dict["email"] != user.email:
            existing = await self.user_repo.get_by_email(update_dict["email"])
            if existing:
                raise ConflictError(f"Email '{update_dict['email']}' is already registered")
                
        updated_user = await self.user_repo.update(user_id, update_dict)
        if not updated_user:
            raise NotFoundError(f"User with ID {user_id} not found during update")
            
        await self.db.refresh(updated_user, attribute_names=["role"])
        return UserRead.model_validate(updated_user)

    async def delete_user(self, user_id: int) -> bool:
        success = await self.user_repo.delete(user_id)
        if not success:
            raise NotFoundError(f"User with ID {user_id} not found")
        return True