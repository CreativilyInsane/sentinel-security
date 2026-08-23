# backend/app/core/constants.py
class Roles:
    ADMIN = "Administrator"
    USER = "User"

class TokenType:
    ACCESS = "access"
    REFRESH = "refresh"


class ScanStatus:
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    TERMINAL = {COMPLETED, FAILED, CANCELLED}
    ACTIVE = {QUEUED, RUNNING}


class ScanModuleStatusValue:
    """Lifecycle values for ``recon_scan_module_status.status``."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    TERMINAL = {COMPLETED, FAILED, CANCELLED}
    ACTIVE = {QUEUED, RUNNING}


class TargetType:
    DOMAIN = "DOMAIN"
    IP = "IP"
    URL = "URL"
    CIDR = "CIDR"


class ResultType:
    HOST_DISCOVERY = "HOST_DISCOVERY"
    PORT_SCAN = "PORT_SCAN"
    SERVICE = "SERVICE"
    WHOIS = "WHOIS"
    DNS = "DNS"
    SSL = "SSL"
    HTTP = "HTTP"
    SCREENSHOT = "SCREENSHOT"


class ReconModule:
    """Recon-engine module identifiers (used in Scan.modules JSON column).

    These are the *engine* modules — each one runs an actual network
    operation.  They are a subset of :class:`ModulePermission` (which
    also includes page-level + feature permissions like ``assets``,
    ``reports``, ``private_network_scan``).
    """
    HOST_DISCOVERY = "host_discovery"
    PORT_SCAN = "port_scan"
    SERVICE_DETECTION = "service_detection"
    WHOIS = "whois"
    DNS = "dns"
    SSL = "ssl"
    HTTP = "http"
    SCREENSHOT = "screenshot"

    ALL = [
        HOST_DISCOVERY, PORT_SCAN, SERVICE_DETECTION,
        WHOIS, DNS, SSL, HTTP, SCREENSHOT,
    ]


class ModulePermission:
    """Stable identifiers for every per-user module / feature permission.

    Stored in the ``user_module_permissions`` table as the
    ``module_name`` column.  The admin toggles these via the User Module
    Settings page; the backend consults them in every protected path.

    Identifiers are deliberately namespaced (``network.*``) so the UI
    can group them hierarchically and so future modules can be added
    without colliding with existing names.

    The recon-engine modules (``host_discovery``, ``port_scan``, …) are
    intentionally kept as their bare identifiers for backwards
    compatibility with the ``Scan.modules`` JSON column — existing
    scans in the database reference these names.
    """
    # ---- Recon modules (engine-level) ---------------------------------
    HOST_DISCOVERY        = "host_discovery"
    DNS                   = "dns"
    PORT_SCAN             = "port_scan"
    SSL                   = "ssl"
    SERVICE_DETECTION     = "service_detection"
    HTTP                  = "http"
    WHOIS                 = "whois"
    SCREENSHOT            = "screenshot"

    # ---- Page-level / feature permissions -----------------------------
    ASSETS                = "assets"
    REPORTS               = "reports"
    PRIVATE_NETWORK_SCAN  = "private_network_scan"

    # ---- Parent module identifier (NOT stored in the DB; computed) ----
    # The "Network Module" parent toggle is *derived* from the eight
    # child module permissions.  The frontend treats it as ON when ANY
    # child is ON, and turning it OFF cascades to all children.  We do
    # not persist a separate ``network_module`` row because that would
    # create the contradictory states described in the spec.
    NETWORK_MODULE = "network_module"

    # ---- Group metadata (used by the UI to render hierarchical layout) -
    NETWORK_MODULE_GROUP = "network_module_group"
    ASSETS_GROUP         = "assets_group"
    REPORTS_GROUP        = "reports_group"
    FEATURE_GROUP        = "feature_group"

    # All permission identifiers that can be stored in the DB.
    ALL = [
        HOST_DISCOVERY, DNS, PORT_SCAN, SSL, SERVICE_DETECTION,
        HTTP, WHOIS, SCREENSHOT,
        ASSETS, REPORTS, PRIVATE_NETWORK_SCAN,
    ]

    # Recon-engine modules (subset that maps to Scan.modules JSON)
    RECON_MODULES = [
        HOST_DISCOVERY, DNS, PORT_SCAN, SSL, SERVICE_DETECTION,
        HTTP, WHOIS, SCREENSHOT,
    ]

    # UI grouping — drives the layout of the User Module Settings page.
    UI_GROUPS = [
        {
            "id": "network_module_group",
            "label": "Network Module",
            "permissions": [
                HOST_DISCOVERY, DNS, PORT_SCAN, SSL,
                SERVICE_DETECTION, HTTP, WHOIS, SCREENSHOT,
            ],
        },
        {
            "id": "assets_group",
            "label": "Assets",
            "permissions": [ASSETS],
        },
        {
            "id": "reports_group",
            "label": "Reports",
            "permissions": [REPORTS],
        },
        {
            "id": "feature_group",
            "label": "Features",
            "permissions": [PRIVATE_NETWORK_SCAN],
        },
    ]

    # Human-friendly labels for the UI
    LABELS = {
        HOST_DISCOVERY:       "Host Discovery",
        DNS:                  "DNS Lookup",
        PORT_SCAN:            "Port Scan",
        SSL:                  "SSL/TLS Analysis",
        SERVICE_DETECTION:    "Service Detection",
        HTTP:                 "HTTPS Header",
        WHOIS:                "WHOIS",
        SCREENSHOT:           "Website Screenshot",
        ASSETS:               "Assets",
        REPORTS:              "Reports",
        PRIVATE_NETWORK_SCAN: "Private Network Scan",
    }

    DESCRIPTIONS = {
        HOST_DISCOVERY:       "DNS resolution + TCP reachability check",
        DNS:                  "A, AAAA, MX, NS, TXT, SOA, CAA, PTR records",
        PORT_SCAN:            "TCP connect scan against common / web / custom ports",
        SSL:                  "Certificate inspection, expiry, chain status",
        SERVICE_DETECTION:    "Identify services and versions from open ports",
        HTTP:                 "Security header assessment (CSP, HSTS, …)",
        WHOIS:                "Registrar and registrant metadata",
        SCREENSHOT:           "Browser screenshot capture (Playwright)",
        ASSETS:               "View and manage discovered assets",
        REPORTS:              "View, generate, and download HTML / PDF reports",
        PRIVATE_NETWORK_SCAN: "Allow scanning private/internal network targets (10/8, 172.16/12, 192.168/16)",
    }


# ---------------------------------------------------------------------------
# Phase 17 — Clients, assignments, ownership
# ---------------------------------------------------------------------------
class ClientAssetType:
    IP = "IP"
    IP_RANGE = "IP_RANGE"
    DOMAIN = "DOMAIN"

    ALL = [IP, IP_RANGE, DOMAIN]


class AssignmentType:
    CLIENT = "CLIENT"
    DIRECT_TARGET = "DIRECT_TARGET"

    ALL = [CLIENT, DIRECT_TARGET]


class OwnershipType:
    """Provenance of a scan / asset / report.

    * ``CLIENT``          — originated from a Client assignment
    * ``ASSIGNED_TARGET`` — originated from a direct target assignment
    * ``USER_MANUAL``     — the user manually entered the target
    """
    CLIENT = "CLIENT"
    ASSIGNED_TARGET = "ASSIGNED_TARGET"
    USER_MANUAL = "USER_MANUAL"

    ALL = [CLIENT, ASSIGNED_TARGET, USER_MANUAL]

    # Ownership types that the *user* is NOT allowed to delete.
    PROTECTED = [CLIENT, ASSIGNED_TARGET]


class AssignmentNotificationType:
    CLIENT_ASSIGNED = "CLIENT_ASSIGNED"
    TARGET_ASSIGNED = "TARGET_ASSIGNED"
    TARGET_REMOVED = "TARGET_REMOVED"
    CLIENT_REMOVED = "CLIENT_REMOVED"

    ALL = [CLIENT_ASSIGNED, TARGET_ASSIGNED, TARGET_REMOVED, CLIENT_REMOVED]


class AuditAction:
    # Existing
    SCAN_CREATED = "SCAN_CREATED"
    SCAN_STARTED = "SCAN_STARTED"
    SCAN_COMPLETED = "SCAN_COMPLETED"
    SCAN_FAILED = "SCAN_FAILED"
    SCAN_CANCELLED = "SCAN_CANCELLED"
    SCAN_DELETED = "SCAN_DELETED"
    REPORT_GENERATED = "REPORT_GENERATED"
    ASSET_DISCOVERED = "ASSET_DISCOVERED"

    # Phase 17 — client / asset lifecycle
    CLIENT_CREATED = "CLIENT_CREATED"
    CLIENT_UPDATED = "CLIENT_UPDATED"
    CLIENT_DELETED = "CLIENT_DELETED"
    CLIENT_ASSET_CREATED = "CLIENT_ASSET_CREATED"
    CLIENT_ASSET_UPDATED = "CLIENT_ASSET_UPDATED"
    CLIENT_ASSET_DELETED = "CLIENT_ASSET_DELETED"

    # Phase 17 — assignment lifecycle
    CLIENT_ASSIGNED = "CLIENT_ASSIGNED"
    CLIENT_UNASSIGNED = "CLIENT_UNASSIGNED"
    TARGET_ASSIGNED = "TARGET_ASSIGNED"
    TARGET_UNASSIGNED = "TARGET_UNASSIGNED"

    # Phase 17 — permissions
    PRIVATE_SCAN_ENABLED = "PRIVATE_SCAN_ENABLED"
    PRIVATE_SCAN_DISABLED = "PRIVATE_SCAN_DISABLED"
    AUTHORIZED_PRIVATE_SCAN = "AUTHORIZED_PRIVATE_SCAN"
    DENIED_PRIVATE_SCAN = "DENIED_PRIVATE_SCAN"

    # Phase 17 — scan origin
    SCAN_FROM_CLIENT = "SCAN_FROM_CLIENT"
    SCAN_FROM_ASSIGNED_TARGET = "SCAN_FROM_ASSIGNED_TARGET"
    USER_MANUAL_SCAN = "USER_MANUAL_SCAN"

    # Phase 17 — ownership enforcement
    ASSET_DELETED = "ASSET_DELETED"
    ASSET_DELETE_DENIED = "ASSET_DELETE_DENIED"
    REPORT_DELETED = "REPORT_DELETED"
    REPORT_DELETE_DENIED = "REPORT_DELETE_DENIED"

    # Phase 18 — self-service account actions
    USER_UPDATED = "USER_UPDATED"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    EMAIL_CHANGED = "EMAIL_CHANGED"

    # Phase 19 — per-user client/asset toggles + signed report tokens
    CLIENT_TOGGLED = "CLIENT_TOGGLED"
    ASSET_TOGGLED = "ASSET_TOGGLED"
    REPORT_TOKEN_ISSUED = "REPORT_TOKEN_ISSUED"
    REPORT_TOKEN_USED = "REPORT_TOKEN_USED"
    MODULE_STATUS_UPDATED = "MODULE_STATUS_UPDATED"


class PortPreset:
    COMMON = "common"
    WEB = "web"
    CUSTOM = "custom"

    COMMON_PORTS = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 587, 993, 995, 3306, 3389, 5432, 6379, 8080, 8443]
    WEB_PORTS = [80, 443, 8000, 8080, 8443, 3000, 5000, 9000]
