# backend/tests/conftest.py
"""Pytest fixtures shared across the test suite.

The test suite is designed to run WITHOUT a live PostgreSQL/Redis — pure
unit tests of validators, services, and parsing logic.  End-to-end tests
that need a database are kept in separate files marked ``@pytest.mark.asyncio``
and skipped automatically when no ``DATABASE_URL`` env var is set.
"""
import os
import sys
from pathlib import Path

import pytest

# Add the backend root to sys.path so `import app...` works from tests/.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# ---------------------------------------------------------------------------
# Set test env vars at MODULE LOAD time, BEFORE any test collection triggers
# imports of app.main / app.db.session / app.core.config.  The system env
# may contain a DATABASE_URL that pydantic-settings would pick up and which
# would crash SQLAlchemy's create_async_engine (e.g. "file:/...").
# ---------------------------------------------------------------------------
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "testpass123")
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")

# Force-override the system env if it contains an incompatible DATABASE_URL.
# We do this unconditionally (not setdefault) because the system env in some
# CI images sets DATABASE_URL to a sqlite path that asyncpg/SQLAlchemy
# cannot parse, which would crash any test that imports app.main.
os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/test"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch):
    """Re-assert env vars per-test in case anything cleared them."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-pytest-only")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "testpass123")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
