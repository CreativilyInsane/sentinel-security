"""scan module status table

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-15

Adds the ``recon_scan_module_status`` table that tracks per-module
lifecycle for each scan.  Each scan's selected modules get one row
whose status moves through:

    QUEUED -> RUNNING -> COMPLETED | FAILED | CANCELLED

The overall ``recon_scans.status`` is derived from these per-module
rows by the API layer when responding to /scans/{id}.
"""
from alembic import op
import sqlalchemy as sa


revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recon_scan_module_status",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scan_id", sa.Integer(), sa.ForeignKey("recon_scans.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("module_name", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="QUEUED"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("scan_id", "module_name", name="uq_scan_module"),
    )
    op.create_index("ix_scan_module_status_scan", "recon_scan_module_status", ["scan_id"])
    op.create_index("ix_scan_module_status_status", "recon_scan_module_status", ["status"])


def downgrade() -> None:
    op.drop_index("ix_scan_module_status_status", table_name="recon_scan_module_status")
    op.drop_index("ix_scan_module_status_scan", table_name="recon_scan_module_status")
    op.drop_table("recon_scan_module_status")
