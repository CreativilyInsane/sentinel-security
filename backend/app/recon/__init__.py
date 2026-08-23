# backend/app/recon/__init__.py
"""Network Reconnaissance domain module.

This package is intentionally separated from the FastAPI route layer:
- models/         SQLAlchemy persistence
- schemas/        Pydantic validation/serialization
- repositories/   DB access (extends app.repositories.base.BaseRepository)
- services/       Business logic (pure Python, no HTTP concerns)
- validators/     Target validation + SSRF protection
- workers/        Celery task definitions
"""
