"""phase 17 — user_active_targets table for user-level target activation

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-10 00:03:00.000000

Creates the ``user_active_targets`` table.  Users can toggle individual
assigned targets as active/inactive — only active ones appear in the
Network Scan dropdown.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_active_targets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('target_key', sa.String(length=320), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=False),
        sa.Column('target_value', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assignment_id'], ['target_assignments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'target_key', name='uq_user_active_target_key'),
    )
    op.create_index(op.f('ix_user_active_targets_id'), 'user_active_targets', ['id'], unique=False)
    op.create_index(op.f('ix_user_active_targets_user_id'), 'user_active_targets', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_active_targets_assignment_id'), 'user_active_targets', ['assignment_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_active_targets_assignment_id'), table_name='user_active_targets')
    op.drop_index(op.f('ix_user_active_targets_user_id'), table_name='user_active_targets')
    op.drop_index(op.f('ix_user_active_targets_id'), table_name='user_active_targets')
    op.drop_table('user_active_targets')
