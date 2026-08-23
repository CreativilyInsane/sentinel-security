"""user client/asset permissions

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-15

Adds two tables that let admins toggle per-user, per-client and
per-user, per-asset access independently of the global Client /
ClientAsset ``is_active`` flag:

    user_client_permissions(user_id, client_id, enabled)
    user_asset_permissions(user_id, client_asset_id, enabled)

Both tables default to "enabled=true" when no row exists for a user
(this preserves the existing default-open behaviour).  When an admin
explicitly creates a row with ``enabled=false``, the user can no longer
scan that client/asset, even if the underlying ClientAsset is active.

These tables are consulted by ``TargetAuthorizationService`` in
addition to the existing assignment + ClientAsset.is_active checks.
"""
from alembic import op
import sqlalchemy as sa


revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- user_client_permissions ---------------------------------------
    op.create_table(
        "user_client_permissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "client_id", name="uq_user_client_perm"),
    )

    # --- user_asset_permissions ---------------------------------------
    op.create_table(
        "user_asset_permissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column(
            "client_asset_id",
            sa.Integer(),
            sa.ForeignKey("client_assets.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "client_asset_id", name="uq_user_asset_perm"),
    )


def downgrade() -> None:
    op.drop_table("user_asset_permissions")
    op.drop_table("user_client_permissions")
