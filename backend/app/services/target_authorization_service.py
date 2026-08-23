# backend/app/services/target_authorization_service.py
"""Centralized scan-target authorization service.

Single source of truth for whether a given user is allowed to scan a
given target.  Used by:

* ``ScanService.create_scan``      — when the API receives the request
* ``ScanService.execute_scan``     — re-validated inside the Celery worker
* (Frontend dropdowns are NOT a security boundary — backend is authoritative)

Authorization algorithm (applied in order):

1. Authenticate user (handled by the route's ``get_current_user`` dep).
2. Parse target syntax (IP / CIDR / DOMAIN / URL) — does NOT reject
   private IPs at this stage; the private-network decision is made
   later based on the user's permissions.
3. Reject targets that are ALWAYS blocked regardless of permissions:
   loopback, link-local, cloud-metadata, internal Docker hostnames,
   unspecified, multicast.
4. Determine target classification (public / private / loopback / ...).
5. Check whether target belongs to an explicit assignment for the user
   (CLIENT assignment whose ClientAsset covers the target, or DIRECT_TARGET
   assignment whose value matches the target).
6. If explicitly assigned → check the ``private_network_scan`` module
   permission (only if the target is private).  If missing → DENY with
   403.  Admins bypass.
7. If target is private AND not assigned → require the
   ``private_network_scan`` module permission.  If missing → DENY.
8. Public target → ALLOW (ownership_type = USER_MANUAL).

The service returns a ``TargetAuthorization`` value object containing the
decision and the provenance metadata (ownership_type, client_id,
assignment_id, etc.) that the caller persists onto the Scan/Asset row.

NOTE: ``RECON_ALLOWED_PRIVATE_NETWORKS`` has been REMOVED.  Private-network
scan access is now controlled entirely by the per-user
``private_network_scan`` module permission stored in the
``user_module_permissions`` table.
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    AssignmentType, ClientAssetType, OwnershipType, ModulePermission, Roles,
)
from app.core.logging import logger
from app.models.client import ClientAsset
from app.models.target_assignment import TargetAssignment
from app.models.user import User
from app.repositories.client_repository import ClientAssetRepository
from app.repositories.target_assignment_repository import (
    TargetAssignmentRepository,
)
from app.repositories.user_network_repository import UserNetworkRepository
from app.repositories.user_client_permission_repository import (
    UserClientPermissionRepository, UserAssetPermissionRepository,
)
from app.recon.validators.target_validator import (
    TargetValidator, ValidatedTarget, ValidationError,
    is_private_ip, _is_internal_ip,
    INTERNAL_HOSTNAMES, CLOUD_METADATA_HOSTS,
)
from app.services.module_permission_service import ModulePermissionService


# ---------------------------------------------------------------------------
# Public value object
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TargetAuthorization:
    allowed: bool
    ownership_type: str = OwnershipType.USER_MANUAL
    client_id: Optional[int] = None
    client_asset_id: Optional[int] = None
    assignment_id: Optional[int] = None
    reason: str = ""
    target_classification: str = "public"  # public | private | loopback | link-local | reserved
    validated: Optional[ValidatedTarget] = field(default=None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _classify_ip(ip_str: str) -> str:
    """Return one of: loopback / link-local / private / reserved / public."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return "public"  # let TargetValidator handle syntax errors
    if ip.is_loopback:
        return "loopback"
    if ip.is_link_local:
        return "link-local"
    if ip.is_reserved:
        return "reserved"
    if ip.is_private or _is_cgnat(ip):
        return "private"
    return "public"


def _is_cgnat(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv4Address):
        i = int(ip)
        return (i >> 24) == 100 and 64 <= ((i >> 16) & 0xFF) < 128
    return False


def _is_private_target(validated: ValidatedTarget) -> Tuple[bool, str]:
    """Return (is_private, classification) for a validated target."""
    if validated.target_type == "CIDR":
        try:
            net = ipaddress.ip_network(validated.cidr, strict=False)
            sample = net.network_address
            cls = _classify_ip(str(sample))
            return cls != "public", cls
        except ValueError:
            return False, "public"
    if validated.target_type == "IP":
        cls = _classify_ip(validated.host)
        return cls != "public", cls
    if validated.target_type == "URL":
        # URL is private only if the host portion resolves to a private IP —
        # but DNS resolution happens at scan time.  For URL targets the
        # private-network permission is enforced inside the worker via the
        # SSRF guard.  Here we treat the URL itself as "public" for the
        # assignment check.
        return False, "public"
    # DOMAIN — same as URL: the DNS-rebinding guard in TargetValidator
    # already checks resolved IPs against the allow-list at scan time.
    return False, "public"


def _is_always_blocked(ip_str: str) -> bool:
    """Return True for IPs that are ALWAYS blocked regardless of permissions.

    This includes loopback, link-local, cloud-metadata, and unspecified
    addresses.  Private IPs (10/8, 172.16/12, 192.168/16) are NOT always
    blocked — they are gated by the ``private_network_scan`` permission.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    if ip_str in CLOUD_METADATA_HOSTS:
        return True
    if ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast:
        return True
    return False


def _is_always_blocked_network(network: ipaddress.IPv4Network | ipaddress.IPv6Network) -> bool:
    """Return True if the network's sample address is always blocked."""
    sample = network.network_address
    return _is_always_blocked(str(sample))


def _ip_in_network(ip_str: str, cidr_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
        net = ipaddress.ip_network(cidr_str, strict=False)
        return ip in net
    except ValueError:
        return False


def _networks_overlap(a: str, b: str) -> bool:
    try:
        na = ipaddress.ip_network(a, strict=False)
        nb = ipaddress.ip_network(b, strict=False)
        return na.overlaps(nb)
    except ValueError:
        return False


def _is_admin(user: User) -> bool:
    return bool(user and user.role and user.role.name == Roles.ADMIN)


# ---------------------------------------------------------------------------
# Soft syntax validator — allows private IPs through
# ---------------------------------------------------------------------------
def _soft_validate_target(raw_target: str) -> ValidatedTarget:
    """Parse the target syntax WITHOUT applying the private-IP block.

    The standard ``TargetValidator.validate`` rejects private IPs unless
    they appear in the per-user allowed-networks list.  But for the
    authorization pipeline we want to allow private IPs through the
    syntax check and decide allow/deny based on the user's
    ``private_network_scan`` module permission + Client assignment.

    This function performs:
    * Basic syntax validation (length, scheme, hostname format)
    * Rejects ALWAYS-blocked targets (loopback, link-local, metadata,
      internal Docker hostnames, multicast, unspecified)
    * Does NOT reject private IPs (10/8, 172.16/12, 192.168/16) — those
      are decided later based on permissions.
    * Does NOT reject private CIDRs — same reason.
    """
    from app.core.config import settings
    from app.core.constants import TargetType
    from urllib.parse import urlparse
    import re

    if not raw_target or not isinstance(raw_target, str):
        raise ValidationError("TARGET_REQUIRED", "A target is required.")
    target = raw_target.strip()
    if not target:
        raise ValidationError("TARGET_REQUIRED", "A target is required.")
    if len(target) > 512:
        raise ValidationError("TARGET_TOO_LONG", "Target exceeds maximum length of 512 characters.")

    # URL?
    if "://" in target:
        scheme = target.split("://", 1)[0].lower()
        if scheme not in ("http", "https"):
            raise ValidationError(
                "UNSUPPORTED_PROTOCOL",
                f"Unsupported URL scheme '{scheme}'. Only http and https are allowed.",
            )
        parsed = urlparse(target)
        host = parsed.hostname
        if not host:
            raise ValidationError("INVALID_URL", "URL is missing a host component.")
        port = parsed.port
        if port is None:
            port = 443 if parsed.scheme.lower() == "https" else 80
        # Check the host portion
        if host.lower() in INTERNAL_HOSTNAMES or host in CLOUD_METADATA_HOSTS:
            raise ValidationError("TARGET_NOT_ALLOWED", "The requested hostname is internal and not authorized for assessment.")
        return ValidatedTarget(
            raw=target, target_type=TargetType.URL, host=host.lower(),
            scheme=parsed.scheme.lower(), port=port, ip_addresses=[], cidr=None,
        )

    # CIDR?
    if "/" in target:
        try:
            network = ipaddress.ip_network(target, strict=False)
        except ValueError:
            raise ValidationError("INVALID_CIDR", "Invalid CIDR notation. Expected format like 192.168.1.0/24.")
        # Block always-blocked networks (loopback, link-local, metadata)
        if _is_always_blocked_network(network):
            raise ValidationError("TARGET_NOT_ALLOWED", "The requested CIDR range is internal and not authorized for assessment.")
        max_hosts = settings.RECON_MAX_HOSTS
        if network.num_addresses > max_hosts:
            raise ValidationError("CIDR_TOO_LARGE", f"CIDR contains {network.num_addresses} addresses which exceeds the limit of {max_hosts}.")
        return ValidatedTarget(
            raw=target, target_type=TargetType.CIDR, host=str(network.network_address),
            scheme=None, port=None, ip_addresses=[], cidr=str(network),
        )

    # Bare IP?
    try:
        ipaddress.ip_address(target)
        # Block always-blocked IPs (loopback, link-local, metadata)
        if _is_always_blocked(target):
            raise ValidationError("TARGET_NOT_ALLOWED", "The requested IP address is internal or reserved and not authorized for assessment.")
        return ValidatedTarget(
            raw=target, target_type=TargetType.IP, host=target,
            scheme=None, port=None, ip_addresses=[target], cidr=None,
        )
    except ValueError:
        pass

    # Domain
    _HOSTNAME_RE = re.compile(
        r"^(?=.{1,253}$)"
        r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)"
        r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$"
    )
    _TLD_RE = re.compile(r"\.[A-Za-z]{2,}$")
    host = target.lower().rstrip(".")
    if host in INTERNAL_HOSTNAMES or host in CLOUD_METADATA_HOSTS:
        raise ValidationError("TARGET_NOT_ALLOWED", "The requested hostname is internal and not authorized for assessment.")
    if not _HOSTNAME_RE.match(host):
        raise ValidationError("INVALID_DOMAIN", "Domain name is malformed. Only letters, digits, hyphens and dots are allowed.")
    if not _TLD_RE.search(host):
        raise ValidationError("INVALID_DOMAIN", "Domain must include a valid top-level domain (e.g. .com, .org, .dev).")
    return ValidatedTarget(
        raw=target, target_type=TargetType.DOMAIN, host=host,
        scheme=None, port=None, ip_addresses=[], cidr=None,
    )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
class TargetAuthorizationService:
    """Authorize scan targets against assignments + private-scan permission."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.assignment_repo = TargetAssignmentRepository(db)
        self.client_asset_repo = ClientAssetRepository(db)
        self.network_repo = UserNetworkRepository(db)
        self.perm_service = ModulePermissionService(db)
        # Phase 19 — per-user client/asset toggle repos.
        self.client_perm_repo = UserClientPermissionRepository(db)
        self.asset_perm_repo = UserAssetPermissionRepository(db)

    async def authorize(
        self,
        user: User,
        raw_target: str,
        *,
        assignment_id: Optional[int] = None,
    ) -> TargetAuthorization:
        """Run the full authorization pipeline for ``raw_target``.

        Steps 1..8 from the module docstring.
        """
        # ----- Step 2: soft-parse target syntax (allows private IPs) -----
        try:
            validated = _soft_validate_target(raw_target)
        except ValidationError as exc:
            return TargetAuthorization(
                allowed=False,
                reason=exc.message,
                target_classification="invalid",
            )

        is_private, cls = _is_private_target(validated)

        # ----- Step 5: explicit assignment check -----
        # Load all active assignments for this user once.
        assignments = await self.assignment_repo.list_for_user(user.id, active_only=True)

        # If the caller specified assignment_id, ensure it actually belongs
        # to this user and is active.  We still walk all assignments so that
        # a malicious caller cannot scan a different private target by
        # passing a different assignment_id.
        match = await self._find_matching_assignment(validated, assignments, assignment_id)

        if match is not None:
            # The target IS explicitly assigned to this user.  But if the
            # target is private/internal, the user must ALSO have the
            # ``private_network_scan`` module permission.  Admins bypass.
            if is_private and not _is_admin(user):
                private_ok = await self.perm_service.is_private_network_scan_allowed(user)
                if not private_ok:
                    return TargetAuthorization(
                        allowed=False,
                        reason=(
                            "This target belongs to an assigned client asset but is a "
                            "private/internal network address.  Your account does not "
                            "have the 'Private Network Scan' module permission, so the "
                            "scan is rejected.  Ask an administrator to enable it."
                        ),
                        target_classification=cls,
                        validated=validated,
                    )

            # Phase 19 — per-user client/asset toggle check.
            # If the user has a row in user_client_permissions(client_id,
            # enabled=False) for the matched client, deny.  Same for
            # user_asset_permissions(client_asset_id, enabled=False).
            # Admins bypass this check (they manage the toggles themselves).
            if not _is_admin(user):
                if match.client_id is not None:
                    client_ok = await self.client_perm_repo.is_enabled(user.id, match.client_id)
                    if not client_ok:
                        return TargetAuthorization(
                            allowed=False,
                            reason=(
                                "Access to this client has been disabled for your account. "
                                "Contact an administrator."
                            ),
                            target_classification=cls,
                            validated=validated,
                        )
                if match.client_asset_id is not None:
                    asset_ok = await self.asset_perm_repo.is_enabled(user.id, match.client_asset_id)
                    if not asset_ok:
                        return TargetAuthorization(
                            allowed=False,
                            reason=(
                                "Access to this asset has been disabled for your account. "
                                "Contact an administrator."
                            ),
                            target_classification=cls,
                            validated=validated,
                        )

            ownership = (
                OwnershipType.CLIENT
                if match.assignment_type == AssignmentType.CLIENT
                else OwnershipType.ASSIGNED_TARGET
            )
            return TargetAuthorization(
                allowed=True,
                ownership_type=ownership,
                client_id=match.client_id,
                client_asset_id=match.client_asset_id,
                assignment_id=match.id,
                reason="Target is explicitly assigned to this user.",
                target_classification=cls,
                validated=validated,
            )

        # ----- Step 7: private target without assignment -----
        if is_private:
            # The user must have the private_network_scan module permission
            # to scan a private target that is NOT explicitly assigned.
            # Admins always have private scan access.
            private_ok = _is_admin(user) or await self.perm_service.is_private_network_scan_allowed(user)

            if private_ok:
                return TargetAuthorization(
                    allowed=True,
                    ownership_type=OwnershipType.USER_MANUAL,
                    reason="Private network scan permission is enabled for this user.",
                    target_classification=cls,
                    validated=validated,
                )

            # Truly unauthorised private target.
            return TargetAuthorization(
                allowed=False,
                reason=(
                    "Private network scanning is disabled for your account. "
                    "Only targets explicitly assigned to you (with the "
                    "Private Network Scan permission enabled) or targets in "
                    "your allowed networks list may be scanned."
                ),
                target_classification=cls,
                validated=validated,
            )

        # ----- Step 8: public target → USER_MANUAL -----
        return TargetAuthorization(
            allowed=True,
            ownership_type=OwnershipType.USER_MANUAL,
            reason="Public target — manual scan.",
            target_classification=cls,
            validated=validated,
        )

    # -------------------------------------------------------------------
    # Assignment matching
    # -------------------------------------------------------------------
    async def _find_matching_assignment(
        self,
        validated: ValidatedTarget,
        assignments: List[TargetAssignment],
        preferred_assignment_id: Optional[int],
    ) -> Optional[TargetAssignment]:
        """Find the assignment that covers ``validated``.

        Order of preference:
        1. The assignment whose id == preferred_assignment_id AND covers target.
        2. Any DIRECT_TARGET assignment whose value matches exactly.
        3. Any CLIENT assignment whose ClientAsset covers the target.
        """
        # Build a quick lookup of client_id -> active ClientAsset rows we
        # need to inspect.
        client_assignments = [a for a in assignments if a.assignment_type == AssignmentType.CLIENT and a.client_id is not None]
        client_assets_by_client: dict[int, List[ClientAsset]] = {}
        if client_assignments:
            client_ids = list({a.client_id for a in client_assignments if a.client_id is not None})
            for cid in client_ids:
                client_assets_by_client[cid] = await self.client_asset_repo.list_for_client(cid, is_active=True)

        # First: try the preferred assignment if it covers the target.
        if preferred_assignment_id is not None:
            for a in assignments:
                if a.id == preferred_assignment_id:
                    if self._assignment_covers_target(a, validated, client_assets_by_client.get(a.client_id or -1, [])):
                        return a
                    break  # if preferred doesn't cover, fall through

        # Second: DIRECT_TARGET exact match.
        for a in assignments:
            if a.assignment_type != AssignmentType.DIRECT_TARGET:
                continue
            if self._direct_assignment_covers(a, validated):
                return a

        # Third: CLIENT assignment whose assets cover the target.
        for a in client_assignments:
            assets = client_assets_by_client.get(a.client_id, [])
            if self._client_assignment_covers(validated, assets):
                # Populate client_asset_id onto the returned assignment so
                # the caller can persist it.
                for ca in assets:
                    if self._asset_covers_target(ca, validated):
                        a.client_asset_id = ca.id
                        return a
        return None

    @staticmethod
    def _direct_assignment_covers(a: TargetAssignment, validated: ValidatedTarget) -> bool:
        """A DIRECT_TARGET covers when target_value matches exactly OR the
        target is an IP inside an IP_RANGE assignment."""
        tv = a.target_value.strip()
        if a.target_type == ClientAssetType.IP:
            if validated.target_type == "IP":
                return validated.host == tv
            return validated.raw.strip() == tv
        if a.target_type == ClientAssetType.IP_RANGE:
            if validated.target_type == "CIDR":
                return _networks_overlap(validated.cidr or "", tv)
            if validated.target_type == "IP":
                return _ip_in_network(validated.host, tv)
        if a.target_type == ClientAssetType.DOMAIN:
            if validated.target_type == "DOMAIN":
                return validated.host.lower() == tv.lower()
            if validated.target_type == "URL":
                return validated.host.lower() == tv.lower()
        return False

    @staticmethod
    def _assignment_covers_target(
        a: TargetAssignment,
        validated: ValidatedTarget,
        client_assets: List[ClientAsset],
    ) -> bool:
        if a.assignment_type == AssignmentType.DIRECT_TARGET:
            return TargetAuthorizationService._direct_assignment_covers(a, validated)
        if a.assignment_type == AssignmentType.CLIENT:
            return TargetAuthorizationService._client_assignment_covers(validated, client_assets)
        return False

    @staticmethod
    def _client_assignment_covers(validated: ValidatedTarget, assets: List[ClientAsset]) -> bool:
        return any(
            TargetAuthorizationService._asset_covers_target(ca, validated)
            for ca in assets
        )

    @staticmethod
    def _asset_covers_target(ca: ClientAsset, validated: ValidatedTarget) -> bool:
        if ca.asset_type == ClientAssetType.IP:
            if validated.target_type == "IP":
                return validated.host == (ca.ip_address or "")
            return False
        if ca.asset_type == ClientAssetType.IP_RANGE:
            cidr = ca.cidr or ""
            if validated.target_type == "CIDR":
                return _networks_overlap(validated.cidr or "", cidr)
            if validated.target_type == "IP":
                return _ip_in_network(validated.host, cidr)
        if ca.asset_type == ClientAssetType.DOMAIN:
            domain = (ca.domain or "").lower()
            if validated.target_type == "DOMAIN":
                return validated.host == domain
            if validated.target_type == "URL":
                return validated.host == domain
        return False

    # -------------------------------------------------------------------
    # Convenience: list authorized targets for a user (used by the
    # frontend dropdown)
    # -------------------------------------------------------------------
    async def list_authorized_targets(self, user: User) -> List[dict]:
        """Return a list of {label, value, assignment_id, ownership_type, ...}
        dicts representing everything the user is currently authorised to
        scan via assignments.

        Phase 19: rows for which the user has a per-user client/asset
        permission row with ``enabled=False`` are filtered out.
        """
        assignments = await self.assignment_repo.list_for_user(user.id, active_only=True)
        is_admin = _is_admin(user)

        # Pre-load the user's per-user client/asset permission rows
        # (only for non-admins — admins see everything).
        disabled_client_ids: set[int] = set()
        disabled_asset_ids: set[int] = set()
        if not is_admin:
            client_perms = await self.client_perm_repo.list_for_user(user.id)
            asset_perms = await self.asset_perm_repo.list_for_user(user.id)
            disabled_client_ids = {p.client_id for p in client_perms if not p.enabled}
            disabled_asset_ids = {p.client_asset_id for p in asset_perms if not p.enabled}

        out: List[dict] = []
        for a in assignments:
            if a.assignment_type == AssignmentType.DIRECT_TARGET:
                # Check the per-user asset permission if the assignment
                # is linked to a client_asset_id.
                if a.client_asset_id is not None and a.client_asset_id in disabled_asset_ids:
                    continue
                if a.client_id is not None and a.client_id in disabled_client_ids:
                    continue
                out.append({
                    "assignment_id": a.id,
                    "ownership_type": OwnershipType.ASSIGNED_TARGET,
                    "client_id": a.client_id,
                    "client_asset_id": a.client_asset_id,
                    "target_type": a.target_type,
                    "target_value": a.target_value,
                    "label": a.target_label or a.target_value,
                    "client_name": None,
                })
            elif a.assignment_type == AssignmentType.CLIENT and a.client_id is not None:
                if a.client_id in disabled_client_ids:
                    continue
                assets = await self.client_asset_repo.list_for_client(a.client_id, is_active=True)
                for ca in assets:
                    if ca.id in disabled_asset_ids:
                        continue
                    value = ca.ip_address or ca.cidr or ca.domain or ""
                    if not value:
                        continue
                    if ca.asset_type == ClientAssetType.IP:
                        tt = "IP"
                    elif ca.asset_type == ClientAssetType.IP_RANGE:
                        tt = "CIDR"
                    else:
                        tt = "DOMAIN"
                    label_parts = []
                    label_parts.append(str(a.client_id))
                    if ca.name:
                        label_parts.append(ca.name)
                    label_parts.append(value)
                    out.append({
                        "assignment_id": a.id,
                        "ownership_type": OwnershipType.CLIENT,
                        "client_id": a.client_id,
                        "client_asset_id": ca.id,
                        "target_type": tt,
                        "target_value": value,
                        "label": " — ".join(label_parts),
                        "client_name": None,
                    })
        return out
