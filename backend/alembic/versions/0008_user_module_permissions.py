"""phase 17 — user_module_permissions table

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-10 00:04:00.000000

Creates the ``user_module_permissions`` table.  Admins can grant or
revoke access to specific recon modules and page-level features on a
per-user basis.  Default-open: if no rows exist for a user, all modules
are allowed.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_module_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('module_name', sa.String(length=50), nullable=False),
        sa.Column('is_allowed', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'module_name', name='uq_user_module'),
    )
    op.create_index(op.f('ix_user_module_permissions_id'), 'user_module_permissions', ['id'], unique=False)
    op.create_index(op.f('ix_user_module_permissions_user_id'), 'user_module_permissions', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_module_permissions_user_id'), table_name='user_module_permissions')
    op.drop_index(op.f('ix_user_module_permissions_id'), table_name='user_module_permissions')
    op.drop_table('user_module_permissions')
