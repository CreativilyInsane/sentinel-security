# Sentinel Security — Network Reconnaissance Management System

Sentinel Security is a role-based reconnaissance platform that lets an
administrator manage **clients**, **client assets** (IP / CIDR / domain),
and **users**, then assign specific clients to specific users and
control which recon modules each user is allowed to run.

The application follows a simple, explicit authorization chain:

```
ADMIN  →  USER  →  CLIENT  →  MODULE PERMISSIONS  →  RECON  →  REPORTS
```

Only two roles exist in this version — **ADMIN** and **USER**.  There
are no team leads, client viewers, organisations, or other complex RBAC
structures.  Every protected operation is authorized on the backend;
the frontend only hides/disables controls for usability, never for
security.

---

## Table of Contents

1. [Technology Stack](#technology-stack)
2. [Architecture](#architecture)
3. [Admin Workflow](#admin-workflow)
4. [User Workflow](#user-workflow)
5. [Client Workflow](#client-workflow)
6. [Module Permission Workflow](#module-permission-workflow)
7. [Recon Workflow](#recon-workflow)
8. [Report Workflow](#report-workflow)
9. [Screenshot Persistence](#screenshot-persistence)
10. [Environment Variables](#environment-variables)
11. [Database Setup](#database-setup)
12. [Docker Setup](#docker-setup)
13. [Development Commands](#development-commands)
14. [Testing Commands](#testing-commands)
15. [Default Development Credentials](#default-development-credentials)
16. [Troubleshooting](#troubleshooting)

---

## Technology Stack

| Component        | Technology                          |
| ---------------- | ----------------------------------- |
| Backend          | Python 3.13 + FastAPI               |
| Frontend         | React 18 + TypeScript + Vite        |
| Database         | PostgreSQL 16                       |
| ORM              | SQLAlchemy 2 (async)                |
| Migrations       | Alembic                             |
| Authentication   | JWT (access + refresh tokens)       |
| Background Jobs  | Celery + Redis                      |
| Recon: DNS       | dnspython                           |
| Recon: WHOIS     | python-whois                        |
| Recon: SSL       | pyOpenSSL + cryptography            |
| Recon: HTTP      | httpx                               |
| Recon: Screenshot| Playwright (Chromium)               |
| Reports: PDF     | ReportLab                           |
| Reports: HTML    | server-rendered, escaped            |
| Containerization | Docker + docker-compose             |
| Reverse Proxy    | Nginx                               |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         Browser (User)                           │
└───────────────────────────────┬──────────────────────────────────┘
                                │ HTTPS
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                          Nginx :80                               │
│  ┌─────────────────────┐    ┌─────────────────────────────────┐  │
│  │  / → frontend:80    │    │  /api/* → backend:8000          │  │
│  └─────────────────────┘    └─────────────────────────────────┘  │
└───────────────────────────────┬──────────────────────────────────┘
                                │
       ┌────────────────────────┼─────────────────────────────┐
       ▼                        ▼                             ▼
┌──────────────┐       ┌──────────────────┐         ┌──────────────────┐
│  Frontend    │       │  Backend (FastAPI)│         │  Worker (Celery) │
│  React/Vite  │       │  uvicorn :8000   │         │  recon queue     │
│  nginx :80   │       │                  │         │                  │
└──────────────┘       └────────┬─────────┘         └────────┬─────────┘
                                │                            │
                                ▼                            ▼
                       ┌──────────────────┐        ┌──────────────────┐
                       │  PostgreSQL :5432│        │  Redis :6379     │
                       │  (internal only) │        │  (internal only) │
                       └──────────────────┘        └──────────────────┘

                       ┌──────────────────────────────┐
                       │  recon_screenshots volume     │
                       │  (mounted on backend + worker)│
                       │  /app/recon_storage/screenshots│
                       └──────────────────────────────┘
```

**Backend layout** (`backend/app/`):

```
app/
├── main.py                      # FastAPI factory + app instance
├── core/                        # config, constants, logging
├── db/                          # session, base, seed, redis
├── models/                      # SQLAlchemy ORM models
│   ├── role.py                  #   Role (Administrator / User)
│   ├── user.py                  #   User (no private_scan_enabled — DB perm instead)
│   ├── client.py                #   Client + ClientAsset
│   ├── target_assignment.py     #   TargetAssignment + Notification
│   ├── user_module_permission.py#   per-user module toggles (single source of truth)
│   ├── user_network.py          #   per-user allowed private CIDRs
│   ├── user_active_target.py    #   user-level target selection
│   └── audit_log.py             #   audit trail
├── auth/                        # JWT + password hashing
├── api/v1/endpoints/            # FastAPI route handlers
│   ├── auth.py                  #   login / refresh / logout / me
│   ├── users.py                 #   user CRUD + module perms API
│   ├── clients.py               #   client + asset CRUD
│   ├── targets.py               #   assignments + my-targets
│   ├── network_permissions.py   #   per-user CIDR allow-list (no toggle-private-scan)
│   ├── recon.py                 #   scans / results / reports / screenshots / assets
│   └── dashboard.py             #   dashboard aggregates
├── services/                    # business logic
│   ├── auth_service.py
│   ├── user_service.py
│   ├── client_service.py
│   ├── module_permission_service.py     # ← central module-permission lookup
│   ├── target_authorization_service.py  # ← central authz engine (DB private-network perm)
│   ├── audit_service.py
│   └── dashboard_service.py
├── recon/                       # reconnaissance subsystem
│   ├── models/                  #   Scan, ScanResult, Asset
│   ├── schemas/                 #   Pydantic request/response
│   ├── repositories/            #   DB access
│   ├── services/                #   scan_service, report_service,
│   │                            #   host_discovery, port_scanner,
│   │                            #   service_detection, dns_service,
│   │                            #   whois_service, ssl_service,
│   │                            #   http_service, screenshot_service
│   ├── validators/              #   target + SSRF validation
│   └── workers/                 #   Celery tasks
├── repositories/                # generic DB repositories
├── schemas/                     # shared Pydantic schemas
└── middleware/                  # error handlers
```

**Frontend layout** (`frontend/src/`):

```
src/
├── App.tsx                      # Routes (incl. /admin/users/:userId/modules)
├── main.tsx                     # Entry point
├── routes/paths.ts              # Route constants
├── context/                     # Auth / Theme / Toast providers
├── api/                         # Axios client + typed API helpers
├── hooks/                       # React Query hooks
├── components/
│   ├── layout/                  # Sidebar, Navbar, DashboardLayout
│   ├── protected/               # ProtectedRoute, AdminRoute
│   ├── ui/                      # Button, Input, Modal, Badge, …
│   ├── users/                   # UserTable, UserFormModal, NetworkPermissionsModal
│   └── dashboard/               # StatCard, RecentActivityTable
├── pages/
│   ├── Login.tsx
│   ├── Dashboard.tsx
│   ├── Users.tsx                # admin only — list + manage
│   ├── UserModuleSettings.tsx   # admin only — dedicated module-permission page
│   ├── Clients.tsx              # admin only
│   ├── ClientDetail.tsx         # admin only
│   ├── Targets.tsx              # users
│   ├── NetworkScan.tsx
│   ├── PreviousScans.tsx
│   ├── ScanDetails.tsx
│   ├── Assets.tsx
│   ├── AssetDetails.tsx
│   ├── Reports.tsx
│   ├── Settings.tsx
│   └── NotFound.tsx
└── types/                       # TypeScript type definitions
```

---

## Admin Workflow

The administrator is the only role that can:

1. **Manage users** — create, edit, disable/enable, reset passwords, delete.
2. **Manage clients** — create, edit, deactivate.
3. **Manage client assets** — add/edit/remove IP, CIDR, or domain assets
   for any client.
4. **Assign clients to users** — a `TargetAssignment` row of type
   `CLIENT` grants the user access to every active asset belonging to
   that client.
5. **Assign direct targets** — a `TargetAssignment` of type
   `DIRECT_TARGET` grants the user access to a single IP/CIDR/domain
   without requiring a client.
6. **Configure per-user module permissions** — toggle each module
   (host_discovery, dns, port_scan, ssl, service_detection, http,
   whois, screenshot, assets, reports, private_network_scan) on/off
   per user.  This is done on the **dedicated User Module Settings
   page** at `/admin/users/:userId/modules`.
7. **Configure per-user allowed private networks** — grant a user the
   ability to scan specific private CIDR ranges (fine-grained CIDR
   allow-list, separate from the broad `private_network_scan` permission).
8. **View everything** — all clients, assets, scans, results, reports
   across all users.
9. **Access audit logs** — every authorization decision is recorded.

Admin pages in the UI:

- `/dashboard` — global stats + recent activity
- `/clients` — client list
- `/clients/:clientId` — client detail (assets, assignments)
- `/users` — user management
- `/admin/users/:userId/modules` — **User Module Settings page**
  (dedicated page, not a modal)
- `/network-scan` — start scans (admin sees all targets)
- `/previous-scans` — every scan in the system
- `/assets` — every discovered asset
- `/reports` — every report
- `/settings` — profile + security + appearance (no private-scan toggle —
  that lives on the User Module Settings page now)

---

## User Workflow

A normal user has restricted access.  The user can **only** see:

1. **Clients assigned to that user** — surfaced via `/targets/my-clients`.
2. **Assets belonging to those clients** — same endpoint, expanded.
3. **Modules enabled for that user** — fetched from
   `/users/{me}/allowed-modules`.
4. **Scans the user created** — never another user's scans.
5. **Reports for the user's scans** — never another user's reports.

A user **cannot**:

- See unassigned clients (the API returns 403).
- Access unassigned assets by guessing an ID (the API returns 403).
- Run a disabled module (the backend rejects with 403 even if the
  frontend button is somehow clicked).
- View another user's scan / report by changing the URL ID (403).
- Delete scans that originated from a Client assignment (only
  admin can delete protected scans).
- Scan private/internal network targets unless the admin has enabled
  the `private_network_scan` module permission for them — **even if
  the target is explicitly assigned to them via a Client**.

User pages in the UI:

- `/dashboard` — personal stats
- `/targets` — assigned clients + direct targets, with notifications
- `/network-scan` — start scans (only authorized targets shown)
- `/previous-scans` — own scans only
- `/assets` — own discovered assets only (only if `assets` perm is ON)
- `/reports` — own reports only (only if `reports` perm is ON)
- `/settings` — profile + security + appearance

---

## Client Workflow

A **Client** represents the organisation / customer / network
environment being assessed.  The lifecycle is:

1. **Admin creates a client** — `POST /api/v1/clients` with a name,
   optional company name, description, and active flag.
2. **Admin adds assets** — `POST /api/v1/clients/{id}/assets` with an
   `asset_type` of `IP`, `IP_RANGE`, or `DOMAIN`, plus the
   corresponding value and optional metadata (name, description,
   network_name, vlan_name).
3. **Admin assigns the client to a user** —
   `POST /api/v1/targets/assign/client` creates a `TargetAssignment`
   of type `CLIENT`.  The user immediately receives a notification
   and the client appears in their `/targets` page.
4. **User runs scans against assigned assets** — the user selects one
   or more authorized targets on the Network Scan page.  The backend
   re-validates every selection against the user's active assignments.
5. **Scans are tagged with `ownership_type = CLIENT`** and linked to
   the client + asset.  This propagates to results, assets, and
   reports so the chain of custody is preserved.
6. **Admin can deactivate a client** — soft-deletes the client,
   deactivates all assignments, and notifies each affected user.

---

## Module Permission Workflow

The admin decides which modules each user can access.  There are
**11** permissions in total, grouped into 4 categories:

### Network Module (recon engine modules)
| Identifier           | Label                | Description                                     |
| -------------------- | -------------------- | ----------------------------------------------- |
| `host_discovery`     | Host Discovery       | DNS resolution + TCP reachability check         |
| `dns`                | DNS Lookup           | A, AAAA, MX, NS, TXT, SOA, CAA, PTR records     |
| `port_scan`          | Port Scan            | TCP connect scan against common/web/custom ports|
| `ssl`                | SSL/TLS Analysis     | Certificate inspection, expiry, chain status    |
| `service_detection`  | Service Detection    | Identify services and versions from open ports  |
| `http`               | HTTPS Header         | Security header assessment (CSP, HSTS, …)       |
| `whois`              | WHOIS                | Registrar and registrant metadata               |
| `screenshot`         | Website Screenshot   | Browser screenshot capture (Playwright)         |

### Assets
| Identifier | Label  | Description                                |
| ---------- | ------ | ------------------------------------------ |
| `assets`   | Assets | View and manage discovered assets          |

### Reports
| Identifier | Label   | Description                                      |
| ---------- | ------- | ------------------------------------------------ |
| `reports`  | Reports | View, generate, and download HTML / PDF reports  |

### Features
| Identifier              | Label                 | Description                                                            |
| ----------------------- | --------------------- | ---------------------------------------------------------------------- |
| `private_network_scan`  | Private Network Scan  | Allow scanning private/internal targets (10/8, 172.16/12, 192.168/16)  |

### Default-open semantics

If a user has *no* `UserModulePermission` rows, **all 11 permissions are
allowed**.  As soon as the admin saves any permission set (even a single
row), only modules with an explicit `is_allowed = True` row remain
accessible.  This lets the admin start from a blank slate and lock the
user down, or start from a fully-locked-down user and grant modules one
at a time.

### Backend enforcement

When the user submits a scan request, the `ScanService.create_scan`
method:

1. Re-runs the full target-authorization pipeline (see below).
2. Loads the user's `UserModulePermission` rows via
   `ModulePermissionService.get_allowed_modules()`.
3. If any rows exist and the user is not an admin, computes the set of
   allowed modules and rejects the request with `403 Forbidden` if any
   requested module is not in the allowed set.
4. The frontend also hides/disables unauthorized module cards, but
   this is **only for usability** — the backend is the source of truth.

For `assets` and `reports` permissions, the recon API endpoints
(`GET /api/v1/recon/assets`, `GET /api/v1/recon/scans/{id}/report/html`,
etc.) call `_require_module(db, current_user, ModulePermission.ASSETS)`
or `_require_module(..., ModulePermission.REPORTS)` before doing any
work.

### Private Network Scan

This permission is checked by `TargetAuthorizationService.authorize()`
when the target is a private/internal IP or CIDR:

- If the target is **explicitly assigned** to the user (via a Client
  assignment whose ClientAsset covers the target) AND the target is
  private/internal → the user must ALSO have
  `private_network_scan = ON` or the scan is rejected with 403.
- If the target is private/internal AND NOT assigned → the user must
  have `private_network_scan = ON` for the scan to be allowed.

Admins always bypass this check.

**Important distinction:** Client authorization and Private Network
Scan permission are **two separate checks**.  A user assigned to a
Client whose assets include `192.168.1.0/24` will STILL be blocked
from scanning that CIDR unless they also have
`private_network_scan = ON`.

### Admin bypass

Administrators are never subject to module permission checks.  An admin
can run any module regardless of their own `UserModulePermission` rows.

### Dedicated User Module Settings page

Module permissions are configured on a **dedicated page** at:

```
/admin/users/:userId/modules
```

This page is **not a modal**.  It loads the user's current permissions,
displays them in a hierarchical layout grouped by category, and lets
the admin toggle each permission on/off with a switch.  The page
includes:

- A header with the user's name and role
- A "default-open" banner explaining the current mode
- Four groups (Network Module, Assets, Reports, Features) with toggle
  switches for each permission
- A "Reset to Default (All Allowed)" button
- A "Save Permissions" button (disabled when no changes are pending)
- An "Unsaved changes" indicator

---

## Recon Workflow

Every scan goes through this pipeline:

```
User submits scan request
        ↓
JWT validated → User identified
        ↓
TargetAuthorizationService.authorize()
   ├── Target syntax validated (IP / CIDR / DOMAIN / URL)
   ├── SSRF guard (loopback / link-local / private / metadata blocked)
   ├── Assignment check — is the target explicitly assigned?
   │     └── YES → ownership_type = CLIENT | ASSIGNED_TARGET
   │            └── If target is private → check private_network_scan perm
   │                  └── NO → 403 Forbidden
   └── Private target without assignment?
         └── Check private_network_scan module permission
               └── YES → ownership_type = USER_MANUAL
               └── NO  → 403 Forbidden
        ↓
Module permission check (users only)
   └── Any denied module? → 403 Forbidden
        ↓
Rate-limit check (max 2 active scans per user)
        ↓
Scan row persisted with ownership_type + client_id + assignment_id
        ↓
Celery task dispatched → recon queue
        ↓
Worker picks up task
   ├── Re-validate target + authorization (defence in depth)
   ├── For each requested module:
   │     ├── Run the module's service (host_discovery, port_scan, …)
   │     ├── Persist ScanResult row(s)
   │     └── Upsert discovered Asset rows
   └── Update scan status → COMPLETED or FAILED
        ↓
Results available via API + report generation
```

---

## Report Workflow

Reports are generated on-demand from persisted `ScanResult` rows.  Two
formats are supported, both containing equivalent information:

- **HTML** — `GET /api/v1/recon/scans/{scan_id}/report/html` returns a
  standalone, self-styled HTML document.  All target-controlled
  content is escaped via `html.escape` to prevent XSS.
- **PDF** — `GET /api/v1/recon/scans/{scan_id}/report/pdf` returns a
  downloadable PDF (ReportLab, A4).  Includes the same sections as
  the HTML report **plus embedded screenshot PNG bytes** so the PDF
  is self-contained.

**Report sections:**

1. Cover (target, scan ID, generated by, timestamp, status)
2. Executive Summary
3. Target Information
4. Host Discovery (table)
5. Open Ports (table)
6. Services (table)
8. DNS Records (table)
9. WHOIS (key-value)
10. SSL / TLS Analysis (key-value)
11. HTTP Security Headers (table)
12. **Screenshots** (embedded PNG images — PDF includes the actual
    image bytes; HTML uses the screenshot API URL)
13. Errors & Warnings (if any)

**Authorization.** Both report endpoints call `_require_module(db,
current_user, ModulePermission.REPORTS)` first (403 if the user lacks
the `reports` permission), then `ScanService.get_scan()` to enforce
ownership: a user can only generate reports for their own scans; an
admin can generate reports for any scan.

**Merged client reports.** A merged HTML report covering every
completed scan for a client is available at
`GET /api/v1/recon/clients/{client_id}/report/html`.  Access is
granted if the user is an admin OR has an active `CLIENT` assignment
for that client AND has the `reports` permission.

---

## Screenshot Persistence

Screenshots are persisted to a Docker named volume so they survive
container restarts and `docker compose down && docker compose up`.

### Pipeline

```
User starts scan with `screenshot` module enabled
        ↓
Celery worker picks up the scan task
        ↓
ScreenshotService.capture() called with the validated target
        ↓
SSRF guard #2: re-resolve DNS, block private IPs at resolution layer
        ↓
Playwright Chromium opens the URL, captures a PNG screenshot
        ↓
File written to /app/recon_storage/screenshots/{uuid}.png
        ↓
Service verifies file exists + is non-empty (no fake success)
        ↓
Returns {screenshot_id, screenshot_url, captured: True, status: COMPLETED}
        ↓
ScanResult row persisted with the screenshot metadata in JSON
        ↓
Frontend displays screenshot via GET /api/v1/recon/screenshots/{uuid}
        ↓
Report includes screenshot (HTML: URL; PDF: embedded PNG bytes)
```

### Docker volume

The `recon_screenshots` named volume is mounted on both the `backend`
and `worker` services at `/app/recon_storage/screenshots/`.  This means:

- The Celery worker writes screenshot files to the volume.
- The FastAPI backend reads them from the same volume when serving
  `GET /api/v1/recon/screenshots/{uuid}`.
- The files persist across `docker compose down && docker compose up`
  (the volume is only destroyed by `docker compose down -v`).

### Screenshot status

The `ScreenshotService.capture()` method returns a `status` field with
one of these values:

- `PENDING` — not used in the current implementation (the capture is
  synchronous within the Celery task).
- `RUNNING` — not used in the current implementation.
- `COMPLETED` — the file was successfully written and verified to
  exist + be non-empty.
- `FAILED` — the file was NOT written; the `error` field contains a
  human-readable explanation.

The service **never** reports `captured: True` unless `os.path.isfile()`
returns True AND the file size is greater than zero.

### Retrieval API

```
GET /api/v1/recon/screenshots/{screenshot_id}
```

- Validates the `screenshot_id` is a valid UUID hex string.
- Looks up the file at `/app/recon_storage/screenshots/{screenshot_id}.png`.
- Returns 404 if the file does not exist.
- Returns the file as `image/png`.

---

## Environment Variables

Three env files are used:

1. **`.env`** (project root) — read by `docker-compose.yml` for the
   PostgreSQL container initialisation.
2. **`backend/.env`** — read by the backend + worker containers and
   by the local dev server.
3. **`frontend/.env`** — read by Vite at build time.

### Root `.env`

| Variable             | Default                  | Purpose                              |
| -------------------- | ------------------------ | ------------------------------------ |
| `POSTGRES_USER`      | `sms_admin`              | PostgreSQL superuser name            |
| `POSTGRES_PASSWORD`  | `ChangeMeDbPassword`     | PostgreSQL superuser password        |
| `POSTGRES_DB`        | `sms_db`                 | Database created on first boot       |
| `COMPOSE_EXPOSE_DB`  | `false`                  | If `true`, publishes 5432 to the host|

### Backend `.env`

| Variable                                | Default                          | Purpose                              |
| --------------------------------------- | -------------------------------- | ------------------------------------ |
| `DATABASE_URL`                          | `postgresql+asyncpg://…@db:5432/sms_db` | SQLAlchemy async URL           |
| `REDIS_URL`                             | `redis://redis:6379/0`           | Redis URL (token blacklist)          |
| `JWT_SECRET_KEY`                        | (placeholder)                    | HMAC secret for JWT signing          |
| `JWT_ALGORITHM`                         | `HS256`                          | JWT algorithm                        |
| `ACCESS_TOKEN_EXPIRE_MINUTES`           | `30`                             | Access token TTL                     |
| `REFRESH_TOKEN_EXPIRE_DAYS`             | `7`                              | Refresh token TTL                    |
| `CORS_ORIGINS`                          | `["http://localhost:8080",…]`    | Allowed CORS origins                 |
| `ADMIN_USERNAME`                        | `admin`                          | Initial admin username               |
| `ADMIN_PASSWORD`                        | `ChangeMeAdmin123!`              | Initial admin password               |
| `ADMIN_EMAIL`                           | `admin@example.com`              | Initial admin email                  |
| `RECON_MAX_HOSTS`                       | `256`                            | Max hosts per scan                   |
| `RECON_MAX_PORTS`                       | `100`                            | Max ports per port-scan run          |
| `RECON_TIMEOUT`                         | `10`                             | Per-operation network timeout (s)    |
| `RECON_MAX_CONCURRENT_CONNECTIONS`      | `50`                             | TCP concurrency for scanning         |
| `RECON_MAX_ACTIVE_SCANS`                | `2`                              | Max concurrent active scans per user |
| `RECON_HTTP_MAX_RESPONSE_SIZE`          | `5242880`                        | Max HTTP response body size (bytes)  |
| `RECON_MAX_REDIRECTS`                   | `5`                              | Max HTTP redirects followed          |
| `RECON_SCREENSHOT_TIMEOUT`              | `30`                             | Screenshot capture timeout (s)       |
| `RECON_SCREENSHOT_STORAGE_PATH`         | `/app/recon_storage/screenshots` | Where screenshot PNGs are stored     |
| `CELERY_BROKER_URL`                     | `redis://redis:6379/1`           | Celery broker                        |
| `CELERY_RESULT_BACKEND`                 | `redis://redis:6379/2`           | Celery result backend                |

> **NOTE:** `RECON_ALLOWED_PRIVATE_NETWORKS` has been **REMOVED**.
> Private-network scan access is now controlled per-user via the
> `private_network_scan` module permission on the User Module Settings
> page (`/admin/users/:userId/modules`).

### Frontend `.env`

| Variable        | Default    | Purpose                                       |
| --------------- | ---------- | --------------------------------------------- |
| `VITE_API_URL`  | `/api/v1`  | API base URL (relative works behind nginx)    |

---

## Database Setup

The database is managed by Alembic.  Migrations live in
`backend/alembic/versions/` and are numbered `0001` through `0009`:

| #     | Description                                                                 |
| ----- | --------------------------------------------------------------------------- |
| 0001  | Initial schema: roles, users, audit_logs                                    |
| 0002  | Recon tables: scans, scan_results, assets                                   |
| 0003  | User network permissions (UserAllowedNetwork) + private_scan_enabled flag   |
| 0004  | Clients + ClientAssets                                                      |
| 0005  | Ownership columns on Scan + Asset (client_id, ownership_type, …)            |
| 0006  | ClientAsset.domain column                                                   |
| 0007  | UserActiveTarget                                                            |
| 0008  | UserModulePermission                                                        |
| 0009  | **Drop private_scan_enabled, backfill private_network_scan + assets + reports perms** |

**Migration 0009** is the key migration for the new architecture.  It:

1. Reads the legacy `users.private_scan_enabled` column.
2. For each user, inserts a `user_module_permissions` row with
   `module_name = 'private_network_scan'` and `is_allowed` set to the
   user's previous `private_scan_enabled` value.
3. Inserts `assets` and `reports` rows (default `True`) for every
   existing user so the new permission checks do not lock them out.
4. Drops the `private_scan_enabled` column from the `users` table.

**Inside Docker**, migrations run automatically on container start
(see the `backend` service `command` in `docker-compose.yml`):

```bash
alembic upgrade head && python -m app.db.seed && uvicorn …
```

**Local development** (without Docker):

```bash
cd backend
# Create / activate venv
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Make sure PostgreSQL is running and DATABASE_URL points to it
export DATABASE_URL="postgresql+asyncpg://sms_admin:password@localhost:5432/sms_db"

# Apply migrations
alembic upgrade head

# Seed the initial admin user
python -m app.db.seed
```

**Resetting the database.** To start from scratch:

```bash
# Inside Docker
docker compose down -v   # removes the postgres_data volume
docker compose up -d      # re-creates everything
```

---

## Docker Setup

The project ships with a complete `docker-compose.yml` that brings up
the full stack:

| Service    | Image                  | Port | Purpose                              |
| ---------- | ---------------------- | ---- | ------------------------------------ |
| `db`       | `postgres:16-alpine`   | —    | PostgreSQL (internal only by default)|
| `redis`    | `redis:7-alpine`       | —    | Redis (internal only)                |
| `backend`  | built from `backend/`  | 8000 | FastAPI (uvicorn) — runs migrations + seed on start |
| `worker`   | built from `backend/`  | —    | Celery worker on the `recon` queue   |
| `frontend` | built from `frontend/` | 80   | Static build served by nginx         |
| `nginx`    | `nginx:alpine`         | 80   | Reverse proxy — the only public port |

### Persistent volumes

| Volume               | Mounted on                | Purpose                              |
| -------------------- | ------------------------- | ------------------------------------ |
| `postgres_data`      | `db:/var/lib/postgresql/data` | PostgreSQL data                 |
| `recon_screenshots`  | `backend` + `worker` at `/app/recon_storage/screenshots` | Screenshot PNG files (survive `docker compose down`) |

### First-time start

```bash
# 1. Copy the env templates
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# 2. Edit backend/.env and set:
#    - JWT_SECRET_KEY (generate with: python -c "import secrets; print(secrets.token_hex(32))")
#    - ADMIN_PASSWORD (change from the default)
#    - DATABASE_URL password must match POSTGRES_PASSWORD in root .env

# 3. Build and start
docker compose build
docker compose up -d

# 4. Verify
docker compose ps             # all services should be "healthy" / "running"
curl http://localhost/health  # → {"status":"healthy",…}
open http://localhost/         # → login page
```

### Logs

```bash
docker compose logs -f backend   # backend logs
docker compose logs -f worker    # celery worker logs
docker compose logs -f nginx     # reverse proxy logs
docker compose logs -f           # everything
```

### Stopping

```bash
docker compose down              # stop containers, keep volumes
docker compose down -v           # stop containers + DELETE data volumes
```

---

## Development Commands

### Backend (local, without Docker)

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Required env vars (or copy backend/.env.example to backend/.env)
export DATABASE_URL="postgresql+asyncpg://sms_admin:password@localhost:5432/sms_db"
export REDIS_URL="redis://localhost:6379/0"
export JWT_SECRET_KEY="dev-secret-change-me"
export ADMIN_USERNAME="admin"
export ADMIN_PASSWORD="Admin@123!"
export ADMIN_EMAIL="admin@example.com"

# Apply migrations
alembic upgrade head

# Seed admin user
python -m app.db.seed

# Start the API
uvicorn app.main:app --reload --port 8000

# In a separate terminal, start the Celery worker
celery -A app.recon.workers.celery_app.celery_app worker --loglevel=info --concurrency=4 -Q recon
```

### Frontend (local, without Docker)

```bash
cd frontend
npm install
npm run dev    # starts Vite dev server on :5173
```

The Vite dev server proxies `/api/*` to `http://localhost:8000` (see
`vite.config.ts`).  Make sure the backend is running first.

### Building the frontend

```bash
cd frontend
npm run build   # outputs to frontend/dist/
npm run preview # serve the production build locally
```

---

## Testing Commands

### Backend tests

```bash
cd backend
source venv/bin/activate   # if using a venv

# Full suite
pytest

# With coverage
pytest --cov=app --cov-report=term-missing

# Specific file
pytest tests/test_module_permissions.py -v

# Specific test
pytest tests/test_module_permissions.py::TestModulePermissionService::test_is_private_network_scan_denied -v
```

The suite contains 151 tests covering:

- Target validation (IP, CIDR, URL, domain, SSRF guards)
- Service parsing (port-scan + service-detection result iteration)
- PDF generation (no NameError on `mm`, valid PDF bytes)
- HTML generation (port-scan + screenshot URL inclusion)
- Recon endpoint imports (ForbiddenError, uuid)
- Screenshot endpoint contract
- Target authorization (single IP, CIDR, unauthorized, loopback, metadata)
- Auth self-service endpoints (change-password, update-email)
- Audit action constants
- Role model (only ADMIN + USER, no permissions field on Role)
- Module permission enforcement (admin bypass, default-open, denied module → 403)
- Authorization flow (JWT required, require_admin rejects USER, ownership checks)
- Client-asset hierarchy (Client, ClientAsset, Scan, ScanResult schema)
- Recon modules (exactly the 8 required modules, no extras)
- Report authorization (HTML + PDF + merged client report)
- API surface (every protected endpoint uses get_current_user; admin endpoints use require_admin)
- Environment hygiene (no real secrets, Docker service names used)
- **NEW: ModulePermission constants (11 permissions including private_network_scan)**
- **NEW: Legacy config removal (RECON_ALLOWED_PRIVATE_NETWORKS + private_scan_enabled gone)**
- **NEW: ModulePermissionService (admin bypass, default-open, explicit rows, deny checks)**
- **NEW: Private Network Scan enforcement (DB permission, not config flag)**
- **NEW: Recon endpoint module enforcement (assets + reports)**
- **NEW: Screenshot service contract (API URL, file verification, status constants)**
- **NEW: Alembic migration 0009 (drops private_scan_enabled, backfills perms)**

### Frontend type-check + build

```bash
cd frontend
npm install
npx tsc --noEmit   # type-check
npm run build      # production build (runs tsc -b && vite build)
```

---

## Default Development Credentials

The initial admin user is seeded on first boot from the
`ADMIN_*` environment variables in `backend/.env`:

| Field    | Default value          |
| -------- | ---------------------- |
| Username | `admin`                |
| Password | `ChangeMeAdmin123!`    |
| Email    | `admin@example.com`    |

> ⚠️ **Change these immediately after first login.**  The defaults
> are intentionally placeholders.  Open the Settings → Security tab
> to set a new password.

There are no seeded regular users.  After logging in as admin, create
one via the Users page (`/users`).

---

## Troubleshooting

### `docker compose up` fails to start the backend

Check the backend logs:

```bash
docker compose logs backend
```

Common causes:

- **`Could not parse SQLAlchemy URL`** — the `DATABASE_URL` in
  `backend/.env` is malformed.  Make sure it follows
  `postgresql+asyncpg://USER:PASSWORD@db:5432/DB`.
- **`password authentication failed for user "sms_admin"`** — the
  `POSTGRES_PASSWORD` in the root `.env` does not match the password
  embedded in `backend/.env`'s `DATABASE_URL`.  Both must be identical.
- **`alembic upgrade head` fails** — usually means the database volume
  contains a stale schema.  Reset with `docker compose down -v` then
  `docker compose up -d`.

### Celery worker cannot connect to Redis

The worker uses `CELERY_BROKER_URL=redis://redis:6379/1`.  Inside
Docker, `redis` resolves to the redis service.  If you're running the
worker locally, change this to `redis://localhost:6379/1`.

### Screenshots fail with "Screenshot not found"

Screenshots are stored in a Docker named volume
(`recon_screenshots`) mounted at
`/app/recon_storage/screenshots/` inside both the backend and worker
containers.  If you see "Screenshot not found" errors, verify the
volume is shared:

```bash
docker compose exec backend ls /app/recon_storage/screenshots/
docker compose exec worker  ls /app/recon_storage/screenshots/
```

Both should list the same UUID-named PNG files.  Screenshots survive
`docker compose down` (without `-v`) and `docker compose up`.

### Private IP scan returns 403

By default, ALL private / loopback / link-local / CGNAT / metadata
IPs are rejected.  To scan a private network:

1. **Create a Client** with the CIDR as a ClientAsset, then assign
   the Client to the user.
2. **Enable the `Private Network Scan` permission** on the User Module
   Settings page (`/admin/users/:userId/modules`).  Without this
   permission, even assigned private targets will be rejected with 403.
3. **Optionally** use the Network Permissions modal (Users page) to
   grant the user a per-user allowed CIDR (fine-grained allow-list
   that the SSRF guard consults).

> **NOTE:** The legacy `RECON_ALLOWED_PRIVATE_NETWORKS` env var has
> been **REMOVED**.  It is no longer consulted.

### 401 Unauthorized on every API call

The frontend stores access + refresh tokens in `localStorage`.  If the
access token expires and the refresh token is also expired (or was
blacklisted on logout), the API client redirects to `/login`.  If
this happens repeatedly, check:

- The system clock on the backend container is correct (`docker compose
  exec backend date`).
- `JWT_SECRET_KEY` has not changed between restarts (changing it
  invalidates all existing tokens).
- `ACCESS_TOKEN_EXPIRE_MINUTES` is not unreasonably short.

### 403 Forbidden on an admin endpoint

Only users with `role.name == "Administrator"` can call admin
endpoints.  If you're sure the user is an admin, verify in the
database:

```sql
SELECT u.username, r.name FROM users u JOIN roles r ON u.role_id = r.id;
```

The role name must be exactly `Administrator` (case-sensitive).

### 403 Forbidden on reports or assets

Users need the `reports` or `assets` module permission to access
those endpoints.  Admin can grant them on the User Module Settings
page (`/admin/users/:userId/modules`).  Admins always bypass this
check.

### Frontend shows a blank page

Open the browser console.  The most common cause is a mismatched
`VITE_API_URL` — if the frontend was built with one value and the
backend moved, API calls will fail silently.  Rebuild the frontend
with the correct `VITE_API_URL` in `frontend/.env`.

### Resetting everything

```bash
docker compose down -v          # stop + delete volumes
docker compose build --no-cache # rebuild images
docker compose up -d            # fresh start
```

---

## Phase 19 — Real-Time Scans, Hierarchical Permissions, and Per-User Asset Toggles

This section documents the production-hardening changes introduced in
Phase 19.  All changes are backward-compatible — existing scans,
clients, assignments, and module permissions continue to work as
before, with the new behaviour layered on top.

### 1. Real-Time Scan Module Progress (SSE)

Each scan now tracks per-module lifecycle states in a new
`recon_scan_module_status` table (migration `0010`).  Each row
represents one selected module for one scan and moves through:

```
QUEUED → RUNNING → COMPLETED | FAILED | CANCELLED
```

The overall scan status is derived from these per-module states; one
module failing does NOT mark the scan as failed.

A new SSE endpoint at `GET /api/v1/recon/scans/{id}/events` streams
named events to the browser:

| Event              | Payload                                                |
| ------------------ | ----------------------------------------------------- |
| `snapshot`         | Initial scan + module_statuses (sent on connection)   |
| `scan_started`     | `{scan_id, target}`                                   |
| `module_started`   | `{scan_id, module}`                                   |
| `module_completed` | `{scan_id, module}`                                   |
| `module_failed`    | `{scan_id, module, error}`                             |
| `scan_completed`   | `{scan_id, target}`                                   |
| `scan_cancelled`   | `{scan_id, target}`                                   |
| `scan_failed`      | `{scan_id, error}`                                    |

The frontend (`ScanDetails.tsx`) opens an `EventSource` connection
when the user navigates to a scan that is still `QUEUED` or
`RUNNING`, updates local React state on every event, and falls back
to the existing 3-second polling if SSE is blocked or the Redis
pub/sub connection is lost.  The 3-second polling is always on, so
the UI stays correct even if SSE is unavailable.

Nginx is configured to disable proxy buffering on the `/api/`
location so SSE chunks reach the browser immediately.

### 2. Scan Details — Selected-Module Tabs Only

The Scan Details page (`/scans/:id`) now renders tabs dynamically
based on the modules that were actually selected for that scan.
The backend persists the selected module list in the `Scan.modules`
JSON column at scan-create time, so the correct tabs appear even
after a page reload or a return visit.

Previously the page always showed all 9 possible module tabs
(Overview, Hosts, Ports, Services, DNS, WHOIS, SSL, HTTP,
Screenshots).  Now only Overview + the tabs for selected modules
are visible.

### 3. Hierarchical Module Permission Toggles

The User Module Settings page (`/admin/users/:id/modules`) now
shows a **parent Network Module toggle** at the top of the Network
Module group.  Behaviour:

- Turning the parent **OFF** snapshots the current child states
  (so they can be restored later) and disables all 8 Network
  submodules.  Children are visually dimmed and disabled while
  the parent is OFF.
- Turning the parent **ON** restores the previous child states
  from the snapshot (or defaults to all-on if no snapshot exists).

Modules without submodules (Assets, Reports, Private Network Scan)
still use a single checkbox — no fake submodules are rendered.

The parent toggle is **not stored in the database**.  Its state is
computed by `ModulePermissionService.get_permissions_read` as
`network_module_enabled = any(child.is_allowed for child in NETWORK_RECON_MODULES)`.
This avoids the contradictory states described in the spec
(e.g. `Network Module = OFF` while `Port Scan = ON`).

### 4. Per-User Client / Asset Permission Toggles

Two new tables (migration `0011`):

- `user_client_permissions(user_id, client_id, enabled)`
- `user_asset_permissions(user_id, client_asset_id, enabled)`

Both use **default-open** semantics: if no row exists for a
`(user_id, client_id)` or `(user_id, asset_id)` pair, access is
allowed.  An admin or the user themselves can create a row with
`enabled=false` to revoke access for that user only — the
underlying `Client` / `ClientAsset` record is untouched.

Parent cascade rule: when a Client is disabled for a user, all of
the user's per-asset permissions for that client are also marked
disabled (enforced server-side by
`UserClientPermissionRepository.disable_all_for_client`).  When
re-enabled, the previous child asset states are preserved (i.e.
assets that were individually disabled remain disabled).

The Targets page (`/targets`) now shows hierarchical ON/OFF toggles:

```
Client A                          [ON]
  Asset 1                        [ON]
  Asset 2                        [OFF]
Client B                          [OFF]
  Asset 1                        [OFF]   (disabled because parent is OFF)
  Asset 2                        [OFF]   (disabled because parent is OFF)
```

Per-asset toggles are disabled while the parent Client is OFF.

`TargetAuthorizationService.authorize()` consults both tables on
every scan-create and scan-execute call.  Admins bypass the check.

### 5. Report Authentication Fix (Signed URL Tokens)

Previously, opening the merged client report in a new browser tab
via `window.open('/api/v1/recon/clients/{id}/report/html')` caused
a `401 Not authenticated` error because the browser cannot attach
the JWT Bearer token to a top-level navigation request.

The fix introduces **short-lived signed URL tokens**:

- `POST /api/v1/recon/scans/{scan_id}/report/token?fmt=html` —
  issues a 5-minute, single-use JWT that authorises the bearer to
  view the scan report.
- `POST /api/v1/recon/clients/{client_id}/report/token?fmt=html` —
  same for the merged client report.
- `GET /api/v1/recon/scans/{scan_id}/report/html?token=…` and
  `GET /api/v1/recon/clients/{client_id}/report/html?token=…` —
  accept either a JWT (Authorization header, as before) or a
  signed token in the `?token=` query param.

The token is single-use: its `jti` is recorded in Redis with the
same TTL, and the report endpoint rejects any token whose `jti`
has already been consumed.

The frontend (`ClientDetail.tsx`, `Targets.tsx`) was updated to
fetch the report as a `Blob` via axios (which automatically attaches
the JWT) and then open the object URL in a new tab.  This is the
recommended approach for opening authenticated content in a new
browser tab.

### 6. Admin Grid Option Removed

The "grid icon" navigation button in the Users table that previously
linked to the User Module Settings page has been replaced with a
clearer "module-permissions" icon (`AdjustmentsHorizontalIcon`).
The Settings page text that referred to "the grid icon" was updated
to "the module-permissions icon".  No grid-related functionality
remains in the codebase.

### 7. Database Migrations

Two new migrations are included:

- `0010_scan_module_status.py` — creates the
  `recon_scan_module_status` table.
- `0011_user_client_asset_permissions.py` — creates the
  `user_client_permissions` and `user_asset_permissions` tables.

Run `alembic upgrade head` to apply them.  The Docker entrypoint
already does this automatically on container start.

### 8. Backend Enforcement Summary

The backend is the source of truth for every authorization decision.
The frontend toggles are conveniences only — every scan is
re-validated by `TargetAuthorizationService.authorize()` inside
both `ScanService.create_scan()` and `ScanService.execute_scan()`
(defence in depth).

The full authorization chain for a single scan:

```
User
 ↓
Client assignment exists?
 ↓ yes
UserClientPermission.enabled == true?
 ↓ yes
UserAssetPermission.enabled == true?
 ↓ yes
ModulePermission (private_network_scan if target is private)?
 ↓ yes
ModulePermission (per-module, e.g. port_scan)?
 ↓ yes
All checks pass → scan is queued
```

If any check fails, the backend returns `403 Forbidden` and the
scan is not created (or, if it was already queued, is marked
`FAILED` inside the worker).

### 9. New Audit Actions

The following audit actions are logged by the new endpoints:

| Action                    | Trigger                                              |
| ------------------------ | --------------------------------------------------- |
| `CLIENT_TOGGLED`         | User/admin toggles their access to a client         |
| `ASSET_TOGGLED`          | User/admin toggles their access to an asset         |
| `REPORT_TOKEN_ISSUED`    | Signed report URL token issued                      |
| `REPORT_TOKEN_USED`      | Signed report URL token consumed                    |
| `MODULE_STATUS_UPDATED`  | Scan module status transition (info-level only)      |

All actions are visible in the existing `audit_logs` table.

### 10. Acceptance Criteria Status

See the spec's section 60 for the full acceptance checklist.  All
items are addressed; see the test summary in the final delivery
report for the test-by-test status.
