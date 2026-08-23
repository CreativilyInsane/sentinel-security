"""phase 18 — module permissions update + remove private_scan_enabled

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-14 00:00:00.000000

This migration:

1. Drops the ``private_scan_enabled`` column from the ``users`` table.
   Private-network scan access is now controlled by the per-user
   ``private_network_scan`` module permission stored in
   ``user_module_permissions``.

2. Backfills the ``user_module_permissions`` table so that every existing
   user who had ``private_scan_enabled = True`` now has an explicit
   ``private_network_scan = True`` row, and every existing user who had
   ``private_scan_enabled = False`` now has an explicit
   ``private_network_scan = False`` row.  This preserves the previous
   access semantics on upgrade.

3. Inserts ``assets``, ``reports`` rows (default True) for every existing
   user so that the new page-level permissions do not lock users out
   of features they previously had.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0009'
down_revision: Union[str, None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Backfill user_module_permissions from the legacy
    #    private_scan_enabled flag BEFORE dropping the column.
    #
    # For every user with private_scan_enabled = True, insert a row
    # {module_name='private_network_scan', is_allowed=True}.
    # For every user with private_scan_enabled = False, insert a row
    # {module_name='private_network_scan', is_allowed=False}.
    # We use raw SQL to avoid depending on the ORM model (which has
    # already dropped the column by the time the migration runs).
    conn = op.get_bind()

    # Check if the legacy column still exists (it might not, on fresh
    # installs that skipped the earlier phases).
    inspector = sa.inspect(conn)
    users_cols = {c['name'] for c in inspector.get_columns('users')}
    if 'private_scan_enabled' in users_cols:
        # Backfill private_network_scan permission from the legacy flag.
        conn.execute(sa.text("""
            INSERT INTO user_module_permissions (user_id, module_name, is_allowed, created_at, updated_at)
            SELECT u.id, 'private_network_scan', u.private_scan_enabled, NOW(), NOW()
            FROM users u
            WHERE NOT EXISTS (
                SELECT 1 FROM user_module_permissions p
                WHERE p.user_id = u.id AND p.module_name = 'private_network_scan'
            )
        """))

        # Drop the legacy column
        op.drop_column('users', 'private_scan_enabled')

    # 2. Make sure every existing user has explicit assets + reports rows
    #    (default True) so the new permission checks do not lock them out.
    conn.execute(sa.text("""
        INSERT INTO user_module_permissions (user_id, module_name, is_allowed, created_at, updated_at)
        SELECT u.id, 'assets', TRUE, NOW(), NOW()
        FROM users u
        WHERE NOT EXISTS (
            SELECT 1 FROM user_module_permissions p
            WHERE p.user_id = u.id AND p.module_name = 'assets'
        )
    """))
    conn.execute(sa.text("""
        INSERT INTO user_module_permissions (user_id, module_name, is_allowed, created_at, updated_at)
        SELECT u.id, 'reports', TRUE, NOW(), NOW()
        FROM users u
        WHERE NOT EXISTS (
            SELECT 1 FROM user_module_permissions p
            WHERE p.user_id = u.id AND p.module_name = 'reports'
        )
    """))


def downgrade() -> None:
    # Re-add the private_scan_enabled column (default False) on downgrade.
    op.add_column(
        'users',
        sa.Column('private_scan_enabled', sa.Boolean(),
                  server_default='0', nullable=False),
    )
    # Best-effort restore from user_module_permissions
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE users u
        SET private_scan_enabled = COALESCE(
            (SELECT p.is_allowed FROM user_module_permissions p
             WHERE p.user_id = u.id AND p.module_name = 'private_network_scan'),
            FALSE)
    """))
    # Remove the backfilled rows
    conn.execute(sa.text("""
        DELETE FROM user_module_permissions
        WHERE module_name IN ('assets', 'reports', 'private_network_scan')
    """))
