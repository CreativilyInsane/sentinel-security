# backend/app/recon/workers/celery_app.py
"""Celery application instance for the Basir recon module.

Broker + result backend both live in Redis (using a separate DB index from
the application's main cache to avoid namespace pollution).
"""
from __future__ import annotations

from celery import Celery

from app.core.config import settings


celery_app = Celery(
    "basir_recon",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.recon.workers.tasks"],
)

# Configuration — conservative defaults appropriate for safe recon workloads.
celery_app.conf.update(
    # Serialise args as JSON (cross-language safe, no pickle RCE risk).
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # One scan at a time per worker process — recon modules can be I/O heavy.
    worker_concurrency=4,
    # Discard results after 1 hour to prevent Redis from growing unbounded.
    result_expires=3600,
    # Hard time limit per scan (a scan is a sequence of bounded operations,
    # so 30 minutes is plenty).
    task_time_limit=1800,
    task_soft_time_limit=1500,
    # Auto-ack after the task finishes (not before) — crashed workers will
    # re-queue the task.
    task_acks_late=True,
    # Only ack on success — failed tasks are re-tried up to the limit.
    task_reject_on_worker_lost=True,
    task_default_queue="recon",
)

# Make the celery app importable as `app.recon.workers.celery_app.celery_app`
# and also as `celery_app` from the package root.
