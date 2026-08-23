# backend/app/services/module_permission_service.py
"""Per-user module permission lookup service.

This is the SINGLE source of truth for "does this user have permission
to use module X?".  All backend authorization checks for module-level
permissions MUST go through this service.

The service reads from the ``user_module_permissions`` PostgreSQL table.
Admins always bypass module permission checks (they have unrestricted
access).  For regular users:

* If NO rows exist for the user → ALL modules are allowed (default-open).
  This preserves backwards compatibility for users created before the
  admin configured their permissions.
* If at least one row exists → only modules with an explicit
  ``is_allowed = True`` row are permitted.

The service caches the permission set per-user per-request via the
``_cache`` dict on the AsyncSession.  In a multi-worker deployment the
cache is per-worker, which is fine because permissions are re-checked
on every API call.
"""
from __future__ import annotations

from typing import Optional, Set

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import Roles, ModulePermission
from app.core.logging import logger
from app.models.user import User
from app.models.user_module_permission import UserModulePermission


class ModulePermissionService:
    """Lookup per-user module permissions from the database."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Low-level row loader
    # ------------------------------------------------------------------
    async def _load_rows(self, user_id: int) -> list[UserModulePermission]:
        stmt = select(UserModulePermission).where(
            UserModulePermission.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def get_permission_map(self, user: User) -> dict[str, bool]:
        """Return ``{module_name: is_allowed}`` for the given user.

        * Admins → every permission in ``ModulePermission.ALL`` is True.
        * Users with no rows → every permission is True (default-open).
        * Users with rows → only the modules with an explicit True row
          are True; everything else is False.
        """
        if user is None:
            return {}

        # Admin bypass
        if user.role and user.role.name == Roles.ADMIN:
            return {m: True for m in ModulePermission.ALL}

        rows = await self._load_rows(user.id)
        if not rows:
            # Default-open
            return {m: True for m in ModulePermission.ALL}

        # Only explicit True rows are allowed
        out: dict[str, bool] = {m: False for m in ModulePermission.ALL}
        for r in rows:
            if r.module_name in out:
                out[r.module_name] = bool(r.is_allowed)
            else:
                # Unknown module name in DB — preserve it but don't grant
                out[r.module_name] = bool(r.is_allowed)
        return out

    async def is_allowed(self, user: User, module_name: str) -> bool:
        """Return True if ``user`` is allowed to use ``module_name``.

        Admins always return True.  See :meth:`get_permission_map` for
        the user-side semantics.
        """
        if user is None:
            return False
        if user.role and user.role.name == Roles.ADMIN:
            return True
        perm_map = await self.get_permission_map(user)
        return perm_map.get(module_name, False)

    async def get_allowed_modules(self, user: User) -> Set[str]:
        """Return the set of module names the user is allowed to use."""
        perm_map = await self.get_permission_map(user)
        return {m for m, allowed in perm_map.items() if allowed}

    async def is_private_network_scan_allowed(self, user: User) -> bool:
        """Convenience: check the ``private_network_scan`` permission."""
        return await self.is_allowed(user, ModulePermission.PRIVATE_NETWORK_SCAN)

    async def is_assets_allowed(self, user: User) -> bool:
        """Convenience: check the ``assets`` permission."""
        return await self.is_allowed(user, ModulePermission.ASSETS)

    async def is_reports_allowed(self, user: User) -> bool:
        """Convenience: check the ``reports`` permission."""
        return await self.is_allowed(user, ModulePermission.REPORTS)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    async def set_permissions(
        self,
        user_id: int,
        permissions: list[dict],
    ) -> dict[str, bool]:
        """Replace the user's permissions with the provided list.

        ``permissions`` is a list of ``{module_name: str, is_allowed: bool}``
        dicts.  All existing rows are deleted and the new ones inserted.
        An empty list returns the user to default-open.
        """
        from sqlalchemy import delete

        # Delete existing
        await self.db.execute(
            delete(UserModulePermission).where(
                UserModulePermission.user_id == user_id,
            )
        )
        # Insert new
        for item in permissions:
            module_name = item.get("module_name")
            is_allowed = bool(item.get("is_allowed", True))
            if not module_name:
                continue
            # Only persist rows for known module names to avoid junk data
            if module_name not in ModulePermission.ALL:
                logger.warning(
                    f"Ignoring unknown module_name '{module_name}' in "
                    f"set_permissions for user {user_id}",
                )
                continue
            row = UserModulePermission(
                user_id=user_id,
                module_name=module_name,
                is_allowed=is_allowed,
            )
            self.db.add(row)
        await self.db.commit()

        # Return the resulting permission map
        rows = await self._load_rows(user_id)
        if not rows:
            return {m: True for m in ModulePermission.ALL}
        out: dict[str, bool] = {m: False for m in ModulePermission.ALL}
        for r in rows:
            if r.module_name in out:
                out[r.module_name] = bool(r.is_allowed)
        return out

    async def get_permissions_read(self, user_id: int) -> dict:
        """Return the permission map + default-open flag for the API.

        Also includes the computed ``network_module`` parent toggle
        (True if ANY of the eight Network submodules is True; False if
        all are False).  The parent is *not* stored in the DB — its
        state is derived from the children.
        """
        rows = await self._load_rows(user_id)
        is_default_open = len(rows) == 0
        if is_default_open:
            perm_map: dict[str, bool] = {m: True for m in ModulePermission.ALL}
        else:
            perm_map = {m: False for m in ModulePermission.ALL}
            for r in rows:
                if r.module_name in perm_map:
                    perm_map[r.module_name] = bool(r.is_allowed)

        # Compute parent Network Module state.
        network_module_enabled = any(
            perm_map.get(m, False) for m in ModulePermission.RECON_MODULES
        )

        return {
            "user_id": user_id,
            "is_default_open": is_default_open,
            "network_module_enabled": network_module_enabled,
            "permissions": [
                {"module_name": m, "is_allowed": perm_map[m]}
                for m in ModulePermission.ALL
            ],
        }
