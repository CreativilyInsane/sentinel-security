# backend/app/recon/validators/target_validator.py
"""Strict target validation + SSRF protection for the recon module.

Every user-supplied target string MUST pass through ``TargetValidator.validate``
before it is persisted or used in any network operation.  This module is the
single source of truth for what the application considers a safe target.

Blocked targets (unless explicitly allow-listed):

* loopback            (127.0.0.0/8, ::1)
* unspecified         (0.0.0.0, ::)
* private IPv4        (10/8, 172.16/12, 192.168/16)
* link-local          (169.254/16, fe80::/10)
* CGNAT               (100.64/10)
* multicast / reserved
* cloud metadata endpoints (169.254.169.254, fd00:ec2::254, metadata.google.internal, ...)
* internal Docker service hostnames (db, redis, backend, frontend, nginx, ...)
* hostnames resolving to any of the above (DNS rebinding protection)

Allow-list sources (evaluated in order):
1. Per-user allowed networks (set by admin via the network permissions API)
2. Per-user ``private_network_scan`` module permission — when enabled, the
   user may scan any private target that is explicitly assigned to them
   (Client / ClientAsset assignment) or that is in their allowed-networks
   list.  The decision to consult this permission is made by
   :class:`TargetAuthorizationService`, not by this validator; the validator
   only enforces the per-user allow-list passed in via ``user_networks``.

Note: ``RECON_ALLOWED_PRIVATE_NETWORKS`` was a config-based allow-list that
has been REMOVED.  Private-network scan access is now controlled entirely
by the per-user ``private_network_scan`` module permission stored in the
``user_module_permissions`` table.
"""
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urlparse

from app.core.config import settings
from app.core.constants import TargetType


# ---------------------------------------------------------------------------
# Error model
# ---------------------------------------------------------------------------
class ValidationError(Exception):
    """Raised when a target fails validation.

    Attributes:
        code:    Stable machine-readable error code (TARGET_INVALID_DOMAIN ...)
        message: Human-readable message safe to return to the API client.
    """

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


# ---------------------------------------------------------------------------
# Validated target value object
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ValidatedTarget:
    raw: str
    target_type: str          # DOMAIN / IP / URL / CIDR
    host: str                 # canonical hostname (no scheme, no port)
    scheme: Optional[str]     # http / https when target_type == URL
    port: Optional[int]       # explicit port when target_type == URL
    ip_addresses: List[str]   # resolved IPs (empty for IP/CIDR until DNS resolved)
    cidr: Optional[str]       # canonical CIDR when target_type == CIDR


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
INTERNAL_HOSTNAMES: frozenset[str] = frozenset({
    "db", "redis", "backend", "frontend", "nginx", "worker",
    "localhost", "ip6-localhost", "ip6-loopback",
    "metadata", "metadata.google.internal", "metadata.aws.internal",
})

CLOUD_METADATA_HOSTS: frozenset[str] = frozenset({
    "169.254.169.254",
    "fd00:ec2::254",
    "metadata.google.internal",
})

_HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$"
)

_TLD_RE = re.compile(r"\.[A-Za-z]{2,}$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _is_internal_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True for loopback / private / link-local / CGNAT / unspecified / multicast / reserved."""
    is_cgnat = False
    if isinstance(ip, ipaddress.IPv4Address):
        i = int(ip)
        is_cgnat = (i >> 24) == 100 and 64 <= ((i >> 16) & 0xFF) < 128
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_unspecified
        or ip.is_multicast
        or ip.is_reserved
        or is_cgnat
    )


def is_private_ip(ip_str: str) -> bool:
    """Public helper: return True if the given IP string is private/internal.

    Used by the screenshot service's SSRF guard and by the report service.
    """
    try:
        return _is_internal_ip(ipaddress.ip_address(ip_str))
    except ValueError:
        return False


def _is_blocked_ip(
    ip_str: str,
    extra_networks: List[ipaddress.IPv4Network | ipaddress.IPv6Network] | None = None,
) -> bool:
    """Return True if the IP is blocked AND not in any allow-list.

    ``extra_networks`` is the per-user allowed networks list
    (``UserAllowedNetwork`` rows).  The legacy global env-var allow-list
    (``RECON_ALLOWED_PRIVATE_NETWORKS``) has been removed; private-network
    scan access is now controlled by the per-user ``private_network_scan``
    module permission, which the caller (TargetAuthorizationService)
    consults separately.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True

    # Cloud metadata IP must ALWAYS be blocked
    if ip_str in CLOUD_METADATA_HOSTS:
        return True

    if not _is_internal_ip(ip):
        return False  # public IP — never blocked

    # At this point the IP is internal.  Check the allow-lists passed in.
    for net in (extra_networks or []):
        if ip in net:
            return False

    return True


# ---------------------------------------------------------------------------
# Public validator
# ---------------------------------------------------------------------------
class TargetValidator:
    """Validates user-supplied reconnaissance targets."""

    @classmethod
    def validate(
        cls,
        raw: str,
        user_networks: List[str] | None = None,
        *,
        global_allowed_networks: List[ipaddress.IPv4Network | ipaddress.IPv6Network] | None = None,
    ) -> ValidatedTarget:
        """Validate a raw target string.

        Args:
            raw: The target string from the user.
            user_networks: Optional list of CIDR strings this user is allowed
                to scan (per-user ``UserAllowedNetwork`` rows).
            global_allowed_networks: DEPRECATED.  Kept only for backwards
                compatibility with existing callers; passing a value here
                is treated as an additional allow-list.  No code in the
                application populates this any more.
        """
        if not raw or not isinstance(raw, str):
            raise ValidationError("TARGET_REQUIRED", "A target is required.")

        target = raw.strip()
        if not target:
            raise ValidationError("TARGET_REQUIRED", "A target is required.")
        if len(target) > 512:
            raise ValidationError("TARGET_TOO_LONG", "Target exceeds maximum length of 512 characters.")

        # Pre-parse user networks and merge with the optional global list.
        extra_nets = cls._parse_user_networks(user_networks)
        if global_allowed_networks:
            extra_nets = list(extra_nets) + list(global_allowed_networks)

        if "://" in target:
            scheme = target.split("://", 1)[0].lower()
            if scheme not in ("http", "https"):
                raise ValidationError(
                    "UNSUPPORTED_PROTOCOL",
                    f"Unsupported URL scheme '{scheme}'. Only http and https are allowed.",
                )
            return cls._validate_url(target, extra_nets)

        if "/" in target:
            return cls._validate_cidr(target, extra_nets)

        try:
            ipaddress.ip_address(target)
            return cls._validate_ip(target, extra_nets)
        except ValueError:
            pass

        return cls._validate_domain(target)

    # ---- URL --------------------------------------------------------------
    @classmethod
    def _validate_url(cls, raw: str, extra_nets) -> ValidatedTarget:
        parsed = urlparse(raw)
        if parsed.scheme.lower() not in ("http", "https"):
            raise ValidationError(
                "UNSUPPORTED_PROTOCOL",
                f"Unsupported URL scheme '{parsed.scheme}'. Only http and https are allowed.",
            )
        host = parsed.hostname
        if not host:
            raise ValidationError("INVALID_URL", "URL is missing a host component.")
        port = parsed.port
        if port is None:
            port = 443 if parsed.scheme.lower() == "https" else 80
        host_target = cls.validate(host, user_networks=None)
        return ValidatedTarget(
            raw=raw, target_type=TargetType.URL, host=host.lower(),
            scheme=parsed.scheme.lower(), port=port, ip_addresses=[], cidr=None,
        )

    # ---- CIDR -------------------------------------------------------------
    @classmethod
    def _validate_cidr(cls, raw: str, extra_nets) -> ValidatedTarget:
        try:
            network = ipaddress.ip_network(raw, strict=False)
        except ValueError:
            raise ValidationError("INVALID_CIDR", "Invalid CIDR notation. Expected format like 192.168.1.0/24.")
        if cls._is_blocked_network(network, extra_nets):
            raise ValidationError("TARGET_NOT_ALLOWED", "The requested CIDR range is internal and not authorized for assessment.")
        max_hosts = settings.RECON_MAX_HOSTS
        if network.num_addresses > max_hosts:
            raise ValidationError("CIDR_TOO_LARGE", f"CIDR contains {network.num_addresses} addresses which exceeds the limit of {max_hosts}.")
        return ValidatedTarget(
            raw=raw, target_type=TargetType.CIDR, host=str(network.network_address),
            scheme=None, port=None, ip_addresses=[], cidr=str(network),
        )

    # ---- IP ---------------------------------------------------------------
    @classmethod
    def _validate_ip(cls, raw: str, extra_nets) -> ValidatedTarget:
        if _is_blocked_ip(raw, extra_nets):
            raise ValidationError("TARGET_NOT_ALLOWED", "The requested IP address is internal or reserved and not authorized for assessment.")
        return ValidatedTarget(
            raw=raw, target_type=TargetType.IP, host=raw,
            scheme=None, port=None, ip_addresses=[raw], cidr=None,
        )

    # ---- Domain -----------------------------------------------------------
    @classmethod
    def _validate_domain(cls, raw: str) -> ValidatedTarget:
        host = raw.lower().rstrip(".")
        if host in INTERNAL_HOSTNAMES or host in CLOUD_METADATA_HOSTS:
            raise ValidationError("TARGET_NOT_ALLOWED", "The requested hostname is internal and not authorized for assessment.")
        if not _HOSTNAME_RE.match(host):
            raise ValidationError("INVALID_DOMAIN", "Domain name is malformed. Only letters, digits, hyphens and dots are allowed.")
        if not _TLD_RE.search(host):
            raise ValidationError("INVALID_DOMAIN", "Domain must include a valid top-level domain (e.g. .com, .org, .dev).")
        return ValidatedTarget(
            raw=raw, target_type=TargetType.DOMAIN, host=host,
            scheme=None, port=None, ip_addresses=[], cidr=None,
        )

    # ---- network helpers --------------------------------------------------
    @staticmethod
    def _is_blocked_network(
        network: ipaddress.IPv4Network | ipaddress.IPv6Network,
        extra_nets: List[ipaddress.IPv4Network | ipaddress.IPv6Network] | None = None,
    ) -> bool:
        # ``extra_nets`` contains the per-user allow-list.  The legacy
        # global env-var allow-list has been removed.
        for allowed in (extra_nets or []):
            if allowed.overlaps(network):
                return False
        sample = network.network_address
        if _is_internal_ip(sample):
            return True
        if network.num_addresses > 1:
            try:
                if _is_internal_ip(network.broadcast_address):
                    return True
            except Exception:
                pass
        return False

    @staticmethod
    def _parse_user_networks(
        networks: List[str] | None,
    ) -> List[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        """Parse user-specific CIDR strings into network objects."""
        result: List[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        if not networks:
            return result
        for n in networks:
            try:
                result.append(ipaddress.ip_network(n.strip(), strict=False))
            except ValueError:
                pass
        return result

    # ---- runtime DNS-rebinding check -------------------------------------
    @classmethod
    def check_resolved_ips(
        cls,
        ip_addresses: List[str],
        user_networks: List[str] | None = None,
        global_allowed_networks: List[ipaddress.IPv4Network | ipaddress.IPv6Network] | None = None,
    ) -> None:
        """SSRF guard invoked AFTER DNS resolution at scan execution time.

        ``global_allowed_networks`` is DEPRECATED — kept only for backwards
        compatibility.  No code in the application populates it any more.
        """
        extra_nets = cls._parse_user_networks(user_networks)
        if global_allowed_networks:
            extra_nets = list(extra_nets) + list(global_allowed_networks)
        for ip_str in ip_addresses:
            if _is_blocked_ip(ip_str, extra_nets):
                raise ValidationError(
                    "TARGET_NOT_ALLOWED",
                    "Resolved IP address is internal or reserved and not authorized for assessment.",
                )


# ---------------------------------------------------------------------------
# Port validation
# ---------------------------------------------------------------------------
def validate_ports(ports: List[int]) -> List[int]:
    if not ports:
        raise ValidationError("PORTS_REQUIRED", "At least one port is required when using a custom port list.")
    if len(ports) > settings.RECON_MAX_PORTS:
        raise ValidationError("PORTS_TOO_MANY", f"Number of ports ({len(ports)}) exceeds the limit of {settings.RECON_MAX_PORTS}.")
    cleaned: List[int] = []
    seen: set[int] = set()
    for p in ports:
        if not isinstance(p, int) or p < 1 or p > 65535:
            raise ValidationError("PORT_INVALID", f"Port {p!r} is not a valid TCP port (must be 1..65535).")
        if p in seen:
            continue
        seen.add(p)
        cleaned.append(p)
    return cleaned


__all__ = [
    "TargetValidator",
    "ValidatedTarget",
    "ValidationError",
    "validate_ports",
    "is_private_ip",
]
