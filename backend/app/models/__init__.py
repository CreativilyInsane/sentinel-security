# backend/app/models/__init__.py
from app.db.base import Base
from app.models.base import BaseMixin
from app.models.role import Role
from app.models.user import User
from app.models.user_network import UserAllowedNetwork
from app.models.audit_log import AuditLog
from app.models.client import Client, ClientAsset
from app.models.target_assignment import TargetAssignment, AssignmentNotification
from app.models.user_active_target import UserActiveTarget
from app.models.user_module_permission import UserModulePermission
from app.models.user_client_permission import UserClientPermission, UserAssetPermission

__all__ = [
    "Base", "BaseMixin",
    "Role", "User", "UserAllowedNetwork", "AuditLog",
    "Client", "ClientAsset",
    "TargetAssignment", "AssignmentNotification",
    "UserActiveTarget",
    "UserModulePermission",
    "UserClientPermission", "UserAssetPermission",
]
