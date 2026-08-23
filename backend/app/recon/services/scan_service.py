# backend/app/recon/services/scan_service.py
"""Scan orchestration service.

Two responsibilities:

1. **API-facing** — ``create_scan``, ``list_scans``, ``get_scan``, etc.
   These methods are called from FastAPI route handlers and only deal
   with persistence + Celery dispatch.  They never run network operations.

2. **Worker-facing** — ``execute_scan`` is invoked by the Celery task
   ``recon.tasks.run_scan``.  It owns the full lifecycle of a scan:
   validates the target again (defence in depth), runs each requested
   module in sequence, persists results, updates progress, and upserts
   assets.  Long-running network operations live here, not in the API
   handler.

Phase 17: ``create_scan`` now invokes :class:`TargetAuthorizationService`
to decide whether the requested target is permitted for the user.  The
authorization decision (ownership_type, client_id, client_asset_id,
assignment_id) is persisted onto the ``Scan`` row and propagated to
asset upserts so that the asset delete-rule can be enforced downstream.
"""
from __future__ import annotations

import asyncio
import traceback
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import (
    ScanStatus, ScanModuleStatusValue, ResultType, ReconModule, AuditAction, PortPreset,
    OwnershipType, ModulePermission, Roles,
)
from app.core.logging import logger
from app.db.redis import redis_client
from app.models.client import Client
from app.recon.models.scan import Scan
from app.recon.repositories.scan_repository import ScanRepository, ScanResultRepository, ScanModuleStatusRepository
from app.recon.repositories.asset_repository import AssetRepository
from app.recon.schemas.scan import ScanCreate
from app.recon.validators.target_validator import (
    TargetValidator, ValidatedTarget, ValidationError, validate_ports,
)
from app.repositories.client_repository import ClientRepository
from app.services.audit_service import AuditService
from app.services.module_permission_service import ModulePermissionService
from app.services.target_authorization_service import (
    TargetAuthorizationService, TargetAuthorization,
)
from app.utils.errors import (
    BadRequestError, NotFoundError, ForbiddenError, ConflictError,
)


class ScanService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.scan_repo = ScanRepository(db)
        self.result_repo = ScanResultRepository(db)
        self.module_status_repo = ScanModuleStatusRepository(db)
        self.asset_repo = AssetRepository(db)
        self.audit = AuditService(db)
        self._user_networks: List[str] | None = None
        # Phase 17 — authorization context, populated by create_scan and
        # re-populated by execute_scan.
        self._auth: Optional[TargetAuthorization] = None

    # ===================================================================
    # API-facing methods
    # ===================================================================
    async def create_scan(
        self,
        *,
        user_id: int,
        payload: ScanCreate,
        ip_address: Optional[str] = None,
        user=None,  # User object — required for authorization
    ) -> Scan:
        # ----- Phase 17 — Authorization FIRST -----
        if user is None:
            # Defensive: caller must pass the authenticated user object.
            raise BadRequestError("Authenticated user object is required to create a scan.")

        auth_service = TargetAuthorizationService(self.db)
        authz = await auth_service.authorize(
            user, payload.target, assignment_id=payload.assignment_id,
        )

        if not authz.allowed:
            # Audit the denial
            await self.audit.log(
                user_id=user_id,
                action=AuditAction.DENIED_PRIVATE_SCAN,
                resource="recon.scan",
                ip_address=ip_address,
                details={
                    "target": payload.target,
                    "reason": authz.reason,
                    "classification": authz.target_classification,
                },
            )
            # Raise a 403 so the frontend can surface a clear message.
            raise ForbiddenError(authz.reason)

        # If allowed AND target is private/internal, audit it as
        # AUTHORIZED_PRIVATE_SCAN.  The user must have the
        # ``private_network_scan`` module permission to reach this point.
        if authz.target_classification != "public" and authz.ownership_type == OwnershipType.USER_MANUAL:
            await self.audit.log(
                user_id=user_id,
                action=AuditAction.AUTHORIZED_PRIVATE_SCAN,
                resource="recon.scan",
                ip_address=ip_address,
                details={
                    "target": payload.target,
                    "ownership_type": authz.ownership_type,
                },
            )

        # Validate ports when port_scan is requested
        custom_ports: Optional[List[int]] = None
        if ReconModule.PORT_SCAN in payload.modules:
            if payload.port_preset == PortPreset.CUSTOM:
                if not payload.custom_ports:
                    raise BadRequestError("Custom port list is required when port_preset == 'custom'.")
                try:
                    custom_ports = validate_ports(payload.custom_ports)
                except ValidationError as exc:
                    raise BadRequestError(f"{exc.message} (code={exc.code})")

        # Enforce per-user module permissions via the central service.
        # Admins bypass this check.  If no UserModulePermission rows exist
        # for the user, all modules are allowed (default-open).
        perm_service = ModulePermissionService(self.db)
        is_admin_user = bool(user.role and user.role.name == Roles.ADMIN)
        if not is_admin_user:
            allowed_modules = await perm_service.get_allowed_modules(user)
            denied = [m for m in payload.modules if m not in allowed_modules]
            if denied:
                raise ForbiddenError(
                    f"You do not have permission to use the following module(s): "
                    f"{', '.join(denied)}. Contact an administrator."
                )

        # Rate-limit: max active scans per user
        active = await self.scan_repo.count_active_user_scans(user_id)
        if active >= settings.RECON_MAX_ACTIVE_SCANS:
            raise ConflictError(
                f"You already have {active} active scan(s). "
                f"Maximum allowed is {settings.RECON_MAX_ACTIVE_SCANS}."
            )

        # Persist
        validated = authz.validated
        scan = Scan(
            user_id=user_id,
            name=payload.name,
            target=validated.raw if validated else payload.target,
            target_type=validated.target_type if validated else "DOMAIN",
            status=ScanStatus.QUEUED,
            modules=payload.modules,
            port_preset=payload.port_preset,
            custom_ports=custom_ports,
            progress=0,
            ownership_type=authz.ownership_type,
            client_id=authz.client_id,
            client_asset_id=authz.client_asset_id,
            assignment_id=authz.assignment_id,
        )
        scan = await self.scan_repo.create_scan(scan)

        # Phase 19 — initialise per-module status rows (QUEUED).
        await self.module_status_repo.init_for_scan(scan.id, list(payload.modules))
        await self._publish_scan_event(scan.id, "scan_created", {
            "scan_id": scan.id,
            "target": scan.target,
            "modules": list(payload.modules),
        })

        # Audit creation with provenance
        action = {
            OwnershipType.CLIENT: AuditAction.SCAN_FROM_CLIENT,
            OwnershipType.ASSIGNED_TARGET: AuditAction.SCAN_FROM_ASSIGNED_TARGET,
            OwnershipType.USER_MANUAL: AuditAction.USER_MANUAL_SCAN,
        }.get(authz.ownership_type, AuditAction.SCAN_CREATED)
        await self.audit.log(
            user_id=user_id,
            action=action,
            resource="recon.scan",
            ip_address=ip_address,
            details={
                "scan_id": scan.id, "target": scan.target,
                "ownership_type": authz.ownership_type,
                "client_id": authz.client_id,
                "assignment_id": authz.assignment_id,
            },
        )
        return scan

    async def list_user_scans(
        self,
        user_id: int,
        *,
        skip: int = 0,
        limit: int = 50,
        status_filter: Optional[str] = None,
        target_filter: Optional[str] = None,
    ) -> List[Scan]:
        return await self.scan_repo.get_user_scans(
            user_id, skip=skip, limit=limit,
            status_filter=status_filter, target_filter=target_filter,
        )

    async def list_all_scans(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        status_filter: Optional[str] = None,
        target_filter: Optional[str] = None,
    ) -> List[Scan]:
        return await self.scan_repo.get_all_scans(
            skip=skip, limit=limit,
            status_filter=status_filter, target_filter=target_filter,
        )

    async def get_scan(self, scan_id: int, *, user_id: int, is_admin: bool) -> Scan:
        scan = await self.scan_repo.get_scan_with_results(scan_id)
        if not scan:
            raise NotFoundError(f"Scan with ID {scan_id} not found.")
        if not is_admin and scan.user_id != user_id:
            raise ForbiddenError("You do not have access to this scan.")
        return scan

    async def get_scan_results(self, scan_id: int, *, user_id: int, is_admin: bool) -> List:
        scan = await self.get_scan(scan_id, user_id=user_id, is_admin=is_admin)
        return await self.result_repo.list_for_scan(scan.id)

    async def cancel_scan(self, scan_id: int, *, user_id: int, is_admin: bool) -> Scan:
        scan = await self.get_scan(scan_id, user_id=user_id, is_admin=is_admin)
        if scan.status in (ScanStatus.COMPLETED, ScanStatus.FAILED, ScanStatus.CANCELLED):
            raise BadRequestError(f"Scan is already in terminal state: {scan.status}")
        await self.scan_repo.update_status(
            scan_id, status=ScanStatus.CANCELLED,
            completed_at=datetime.now(timezone.utc),
        )
        # Mark any pending module statuses as CANCELLED.
        await self.module_status_repo.cancel_pending(scan_id)
        await self._publish_scan_event(scan_id, "scan_cancelled", {
            "scan_id": scan_id, "target": scan.target,
        })
        await self.audit.log(
            user_id=user_id, action=AuditAction.SCAN_CANCELLED,
            resource="recon.scan",
            details={"scan_id": scan_id, "target": scan.target},
        )
        return await self.scan_repo.get_by_id(scan_id)

    async def delete_scan(self, scan_id: int, *, user_id: int, is_admin: bool) -> None:
        """Delete a scan + its results.

        Phase 17: a normal user can only delete scans whose
        ``ownership_type == USER_MANUAL``.  Admin can delete any.
        """
        scan = await self.get_scan(scan_id, user_id=user_id, is_admin=is_admin)
        ownership = (scan.ownership_type or OwnershipType.USER_MANUAL)
        if not is_admin and ownership in OwnershipType.PROTECTED:
            await self.audit.log(
                user_id=user_id, action=AuditAction.REPORT_DELETE_DENIED,
                resource="recon.scan",
                details={"scan_id": scan_id, "ownership_type": ownership},
            )
            raise ForbiddenError(
                "This scan belongs to a Client or assigned target and cannot be deleted by a user. "
                "Contact an administrator."
            )
        await self.scan_repo.delete(scan.id)
        await self.audit.log(
            user_id=user_id, action=AuditAction.SCAN_DELETED,
            resource="recon.scan",
            details={"scan_id": scan_id, "target": scan.target, "ownership_type": ownership},
        )

    # ===================================================================
    # Worker-facing method
    # ===================================================================
    async def execute_scan(self, scan_id: int) -> None:
        """Run the full scan pipeline.  Called from the Celery task."""
        scan = await self.scan_repo.get_by_id(scan_id)
        if not scan:
            logger.error(f"execute_scan: scan {scan_id} not found")
            return

        # Cancellation check (in case the user cancelled between queue and worker pickup)
        if scan.status == ScanStatus.CANCELLED:
            logger.info(f"Scan {scan_id} was cancelled before execution; skipping.")
            return

        await self.scan_repo.update_status(
            scan_id, status=ScanStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            progress=0,
        )
        await self._publish_scan_event(scan_id, "scan_started", {
            "scan_id": scan_id, "target": scan.target,
        })
        await self._audit(scan.user_id, AuditAction.SCAN_STARTED, scan)

        try:
            # Re-validate target inside the worker (defence in depth).
            # We do NOT have a User object here, but we can re-validate the
            # raw target and SSRF rules.  The ownership provenance that was
            # captured at create_scan time is trusted because it was
            # produced by TargetAuthorizationService.
            from app.repositories.user_repository import UserRepository
            user_repo = UserRepository(self.db)
            user = await user_repo.get_user_with_role(scan.user_id)
            if not user:
                raise NotFoundError(f"User {scan.user_id} not found while executing scan {scan_id}")

            auth_service = TargetAuthorizationService(self.db)
            self._auth = await auth_service.authorize(
                user, scan.target, assignment_id=scan.assignment_id,
            )

            if not self._auth.allowed:
                # Authorization changed between create and execute — deny.
                raise ForbiddenError(self._auth.reason or "Scan target is no longer authorized.")

            # Re-validate syntax for the worker path.
            user_networks = await self._get_user_networks(scan.user_id)
            self._user_networks = user_networks
            # The legacy global env-var allow-list (RECON_ALLOWED_PRIVATE_NETWORKS)
            # has been removed.  Private-network scan access is now controlled
            # by the per-user `private_network_scan` module permission, which
            # is consulted by TargetAuthorizationService during authorize().
            self._global_allowed_networks = None
            # Use the validated target from the authorization decision (which
            # uses the soft validator that allows private IPs).  Fall back to
            # the soft validator directly if for some reason it's missing.
            validated = self._auth.validated
            if validated is None:
                from app.services.target_authorization_service import _soft_validate_target
                try:
                    validated = _soft_validate_target(scan.target)
                except ValidationError as exc:
                    raise ForbiddenError(f"Target re-validation failed: {exc.message}")

            modules = list(scan.modules)
            step_count = max(len(modules), 1)
            step = 100 // step_count

            # Ensure module status rows exist (idempotent — init_for_scan
            # skips modules that already have a row).
            await self.module_status_repo.init_for_scan(scan_id, modules)

            for module in modules:
                # Re-check cancellation between modules
                fresh = await self.scan_repo.get_by_id(scan_id)
                if fresh and fresh.status == ScanStatus.CANCELLED:
                    logger.info(f"Scan {scan_id} cancelled mid-execution.")
                    # Mark remaining modules as CANCELLED.
                    await self.module_status_repo.cancel_pending(scan_id)
                    return

                # Mark module RUNNING
                await self.module_status_repo.set_module_status(
                    scan_id, module,
                    status=ScanModuleStatusValue.RUNNING,
                    started_at=datetime.now(timezone.utc),
                    progress=50,
                )
                await self._publish_scan_event(scan_id, "module_started", {
                    "scan_id": scan_id, "module": module,
                })

                module_failed = False
                module_error: Optional[str] = None
                try:
                    await self._run_module(module, scan, validated)
                except ValidationError as exc:
                    module_failed = True
                    module_error = f"{exc.message} (code={exc.code})"
                    await self.result_repo.add_result(
                        scan_id=scan_id,
                        result_type=self._module_result_type(module),
                        data={},
                        error=module_error,
                    )
                    logger.warning(f"Module {module} failed for scan {scan_id}: {exc.message}")
                except Exception as exc:  # noqa: BLE001
                    module_failed = True
                    module_error = f"Unexpected error: {exc}"
                    logger.error(f"Module {module} crashed for scan {scan_id}: {exc}\n{traceback.format_exc()}")
                    await self.result_repo.add_result(
                        scan_id=scan_id,
                        result_type=self._module_result_type(module),
                        data={},
                        error=module_error,
                    )
                finally:
                    # Update module status (COMPLETED or FAILED)
                    await self.module_status_repo.set_module_status(
                        scan_id, module,
                        status=ScanModuleStatusValue.FAILED if module_failed
                        else ScanModuleStatusValue.COMPLETED,
                        error_message=module_error,
                        completed_at=datetime.now(timezone.utc),
                        progress=100,
                    )
                    await self._publish_scan_event(
                        scan_id,
                        "module_failed" if module_failed else "module_completed",
                        {
                            "scan_id": scan_id, "module": module,
                            "error": module_error,
                        },
                    )
                    await self.scan_repo.append_progress(scan_id, step)

            await self.scan_repo.update_status(
                scan_id, status=ScanStatus.COMPLETED,
                progress=100,
                completed_at=datetime.now(timezone.utc),
            )
            await self._publish_scan_event(scan_id, "scan_completed", {
                "scan_id": scan_id, "target": scan.target,
            })
            await self._audit(scan.user_id, AuditAction.SCAN_COMPLETED, scan)

        except ValidationError as exc:
            await self.scan_repo.update_status(
                scan_id, status=ScanStatus.FAILED,
                error_message=exc.message,
                completed_at=datetime.now(timezone.utc),
            )
            await self.module_status_repo.cancel_pending(scan_id)
            await self._publish_scan_event(scan_id, "scan_failed", {
                "scan_id": scan_id, "error": exc.message,
            })
            await self._audit(scan.user_id, AuditAction.SCAN_FAILED, scan, error=exc.message)
        except ForbiddenError as exc:
            await self.scan_repo.update_status(
                scan_id, status=ScanStatus.FAILED,
                error_message=exc.message,
                completed_at=datetime.now(timezone.utc),
            )
            await self.module_status_repo.cancel_pending(scan_id)
            await self._publish_scan_event(scan_id, "scan_failed", {
                "scan_id": scan_id, "error": exc.message,
            })
            await self._audit(scan.user_id, AuditAction.SCAN_FAILED, scan, error=exc.message)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Scan {scan_id} failed: {exc}\n{traceback.format_exc()}")
            await self.scan_repo.update_status(
                scan_id, status=ScanStatus.FAILED,
                error_message=str(exc)[:500],
                completed_at=datetime.now(timezone.utc),
            )
            await self.module_status_repo.cancel_pending(scan_id)
            await self._publish_scan_event(scan_id, "scan_failed", {
                "scan_id": scan_id, "error": str(exc)[:500],
            })
            await self._audit(scan.user_id, AuditAction.SCAN_FAILED, scan, error=str(exc))

    async def _get_user_networks(self, user_id: int) -> List[str]:
        from app.repositories.user_network_repository import UserNetworkRepository
        net_repo = UserNetworkRepository(self.db)
        return await net_repo.get_networks_list(user_id)

    # ===================================================================
    # Module dispatch
    # ===================================================================
    async def _run_module(
        self,
        module: str,
        scan: Scan,
        validated: ValidatedTarget,
    ) -> None:
        if module == ReconModule.HOST_DISCOVERY:
            await self._module_host_discovery(scan, validated)
        elif module == ReconModule.PORT_SCAN:
            await self._module_port_scan(scan, validated)
        elif module == ReconModule.SERVICE_DETECTION:
            await self._module_service_detection(scan, validated)
        elif module == ReconModule.WHOIS:
            await self._module_whois(scan, validated)
        elif module == ReconModule.DNS:
            await self._module_dns(scan, validated)
        elif module == ReconModule.SSL:
            await self._module_ssl(scan, validated)
        elif module == ReconModule.HTTP:
            await self._module_http(scan, validated)
        elif module == ReconModule.SCREENSHOT:
            await self._module_screenshot(scan, validated)
        else:
            logger.warning(f"Unknown recon module: {module}")

    def _module_result_type(self, module: str) -> str:
        return {
            ReconModule.HOST_DISCOVERY: ResultType.HOST_DISCOVERY,
            ReconModule.PORT_SCAN: ResultType.PORT_SCAN,
            ReconModule.SERVICE_DETECTION: ResultType.SERVICE,
            ReconModule.WHOIS: ResultType.WHOIS,
            ReconModule.DNS: ResultType.DNS,
            ReconModule.SSL: ResultType.SSL,
            ReconModule.HTTP: ResultType.HTTP,
            ReconModule.SCREENSHOT: ResultType.SCREENSHOT,
        }.get(module, ResultType.HOST_DISCOVERY)

    # ---- individual modules -------------------------------------------
    async def _module_host_discovery(self, scan: Scan, validated: ValidatedTarget) -> None:
        from app.recon.services.host_discovery import HostDiscoveryService
        svc = HostDiscoveryService()
        result = await svc.discover(validated)
        await self.result_repo.add_result(
            scan_id=scan.id, result_type=ResultType.HOST_DISCOVERY, data=result,
        )
        for host in result.get("hosts", []):
            await self.asset_repo.upsert_asset(
                user_id=scan.user_id, scan_id=scan.id,
                host=host.get("host") or validated.host,
                ip_address=host.get("ip"),
                hostname=host.get("hostname"),
                status=host.get("status"),
                metadata={"latency_ms": host.get("latency_ms"), "module": "host_discovery"},
                ownership_type=scan.ownership_type,
                client_id=scan.client_id,
                client_asset_id=scan.client_asset_id,
                assignment_id=scan.assignment_id,
            )
            await self._audit(scan.user_id, AuditAction.ASSET_DISCOVERED, scan,
                              details={"host": host.get("host"), "ip": host.get("ip")})

    async def _module_port_scan(self, scan: Scan, validated: ValidatedTarget) -> None:
        from app.recon.services.port_scanner import PortScannerService
        svc = PortScannerService()

        ips = await self._resolve_ips(validated, user_networks=self._user_networks)
        if not ips:
            await self.result_repo.add_result(
                scan_id=scan.id, result_type=ResultType.PORT_SCAN,
                data={"ports": []}, error="No IP addresses resolved for target.",
            )
            return

        all_results = []
        for ip in ips:
            res = await svc.scan(
                validated, ip,
                port_preset=scan.port_preset,
                custom_ports=scan.custom_ports,
            )
            all_results.append(res)
            for p in res.get("ports", []):
                if p.get("state") == "open":
                    await self.asset_repo.upsert_asset(
                        user_id=scan.user_id, scan_id=scan.id,
                        host=validated.host, ip_address=ip,
                        port=p.get("port"),
                        protocol=p.get("protocol") or "tcp",
                        service=p.get("service_guess"),
                        status="open",
                        metadata={"latency_ms": p.get("latency_ms")},
                        ownership_type=scan.ownership_type,
                        client_id=scan.client_id,
                        client_asset_id=scan.client_asset_id,
                        assignment_id=scan.assignment_id,
                    )
        await self.result_repo.add_result(
            scan_id=scan.id, result_type=ResultType.PORT_SCAN,
            data={"scans": all_results},
        )

    async def _module_service_detection(self, scan: Scan, validated: ValidatedTarget) -> None:
        from app.recon.services.service_detection import ServiceDetectionService
        svc = ServiceDetectionService()

        prior_results = await self.result_repo.list_for_scan(scan.id)
        open_ports_by_ip: Dict[str, List[int]] = {}
        for pr in prior_results:
            if pr.result_type == ResultType.PORT_SCAN:
                for ps in (pr.data or {}).get("scans", []):
                    ip = ps.get("ip")
                    ports = [p["port"] for p in ps.get("ports", []) if p.get("state") == "open"]
                    if ip and ports:
                        open_ports_by_ip.setdefault(ip, []).extend(ports)

        if not open_ports_by_ip:
            ips = await self._resolve_ips(validated, user_networks=self._user_networks)
            for ip in ips:
                open_ports_by_ip[ip] = list(PortPreset.COMMON_PORTS)

        all_services = []
        for ip, ports in open_ports_by_ip.items():
            res = await svc.detect(validated, ip, ports)
            all_services.append(res)
            for svc_entry in res.get("services", []):
                await self.asset_repo.upsert_asset(
                    user_id=scan.user_id, scan_id=scan.id,
                    host=validated.host, ip_address=ip,
                    port=svc_entry.get("port"),
                    protocol=svc_entry.get("protocol") or "tcp",
                    service=svc_entry.get("service"),
                    metadata={"banner": svc_entry.get("banner"), "version": svc_entry.get("version")},
                    ownership_type=scan.ownership_type,
                    client_id=scan.client_id,
                    client_asset_id=scan.client_asset_id,
                    assignment_id=scan.assignment_id,
                )
        await self.result_repo.add_result(
            scan_id=scan.id, result_type=ResultType.SERVICE,
            data={"scans": all_services},
        )

    async def _module_whois(self, scan: Scan, validated: ValidatedTarget) -> None:
        from app.recon.services.whois_service import WhoisService
        if validated.target_type not in ("DOMAIN", "URL"):
            await self.result_repo.add_result(
                scan_id=scan.id, result_type=ResultType.WHOIS, data={},
                error="WHOIS is only applicable to domain targets.",
            )
            return
        svc = WhoisService()
        result = await svc.lookup(validated)
        await self.result_repo.add_result(
            scan_id=scan.id, result_type=ResultType.WHOIS, data=result,
        )

    async def _module_dns(self, scan: Scan, validated: ValidatedTarget) -> None:
        from app.recon.services.dns_service import DnsService
        if validated.target_type == "CIDR":
            await self.result_repo.add_result(
                scan_id=scan.id, result_type=ResultType.DNS, data={},
                error="DNS lookup is not applicable to CIDR targets.",
            )
            return
        svc = DnsService()
        result = await svc.lookup(validated)
        await self.result_repo.add_result(
            scan_id=scan.id, result_type=ResultType.DNS, data=result,
        )

    async def _module_ssl(self, scan: Scan, validated: ValidatedTarget) -> None:
        from app.recon.services.ssl_service import SslService
        if validated.target_type == "CIDR":
            await self.result_repo.add_result(
                scan_id=scan.id, result_type=ResultType.SSL, data={},
                error="SSL analysis is not applicable to CIDR targets.",
            )
            return
        svc = SslService()
        result = await svc.analyze(validated)
        await self.result_repo.add_result(
            scan_id=scan.id, result_type=ResultType.SSL, data=result,
        )

    async def _module_http(self, scan: Scan, validated: ValidatedTarget) -> None:
        from app.recon.services.http_service import HttpService
        if validated.target_type == "CIDR":
            await self.result_repo.add_result(
                scan_id=scan.id, result_type=ResultType.HTTP, data={},
                error="HTTP analysis is not applicable to CIDR targets.",
            )
            return
        svc = HttpService()
        result = await svc.analyze(validated)
        await self.result_repo.add_result(
            scan_id=scan.id, result_type=ResultType.HTTP, data=result,
        )

    async def _module_screenshot(self, scan: Scan, validated: ValidatedTarget) -> None:
        from app.recon.services.screenshot_service import ScreenshotService
        if validated.target_type == "CIDR":
            await self.result_repo.add_result(
                scan_id=scan.id, result_type=ResultType.SCREENSHOT, data={},
                error="Screenshot capture is not applicable to CIDR targets.",
            )
            return
        svc = ScreenshotService()
        result = await svc.capture(validated)
        await self.result_repo.add_result(
            scan_id=scan.id, result_type=ResultType.SCREENSHOT, data=result,
        )
        if result.get("captured"):
            await self._audit(
                scan.user_id, AuditAction.REPORT_GENERATED, scan,
                details={"artifact": "screenshot", "screenshot_id": result.get("screenshot_id")},
            )

    # ---- helpers -------------------------------------------------------
    async def _resolve_ips(self, validated: ValidatedTarget, *, user_networks: List[str] | None = None) -> List[str]:
        """Resolve the target to a list of IP strings, applying the SSRF
        guard to every resolved address."""
        if validated.target_type == "IP":
            return [validated.host]
        if validated.target_type == "CIDR":
            import ipaddress
            net = ipaddress.ip_network(validated.cidr, strict=False)
            return [str(ip) for ip in list(net.hosts())[: settings.RECON_MAX_HOSTS]]
        # DOMAIN or URL — resolve via socket
        import socket
        loop = asyncio.get_running_loop()
        try:
            infos = await loop.run_in_executor(
                None,
                lambda: socket.getaddrinfo(validated.host, None, proto=socket.IPPROTO_TCP),
            )
        except socket.gaierror:
            return []
        ips: List[str] = []
        for info in infos:
            ip_str = info[4][0].split("%", 1)[0]
            if ip_str not in ips:
                ips.append(ip_str)
        # SSRF guard — pass the user's per-user allowed networks.
        # The legacy global env-var allow-list (RECON_ALLOWED_PRIVATE_NETWORKS)
        # has been removed; private-network scan access is now controlled
        # by the per-user `private_network_scan` module permission.
        TargetValidator.check_resolved_ips(
            ips,
            user_networks=user_networks,
        )
        return ips

    async def _audit(
        self,
        user_id: int,
        action: str,
        scan: Scan,
        *,
        error: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        d: Dict[str, Any] = {"scan_id": scan.id, "target": scan.target}
        if details:
            d.update(details)
        if error:
            d["error"] = error
        await self.audit.log(
            user_id=user_id, action=action, resource="recon.scan", details=d,
        )

    # -----------------------------------------------------------------
    # Phase 19 — real-time event broadcasting via Redis pub/sub.
    #
    # The SSE endpoint subscribes to ``scan_events:{scan_id}`` and
    # forwards each published payload to the browser as an SSE event.
    # Failures here are swallowed — pub/sub is best-effort and the
    # polling fallback (which is always on) ensures correctness even
    # if Redis is unreachable.
    # -----------------------------------------------------------------
    async def _publish_scan_event(
        self,
        scan_id: int,
        event_type: str,
        payload: Dict[str, Any],
    ) -> None:
        try:
            import json
            channel = f"scan_events:{scan_id}"
            msg = json.dumps({
                "event": event_type,
                "scan_id": scan_id,
                "payload": payload,
            })
            await redis_client.publish(channel, msg)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Failed to publish scan event {event_type} for scan {scan_id}: {exc}")
