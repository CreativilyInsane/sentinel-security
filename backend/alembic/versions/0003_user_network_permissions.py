"""user network permissions + admin private scan toggle

Revision ID: 0003
Revises: 0002
Create Date: 2025-02-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add private_scan_enabled column to users
    op.add_column('users', sa.Column('private_scan_enabled', sa.Boolean(), server_default='0', nullable=False))

    # Create user_allowed_networks table
    op.create_table(
        'user_allowed_networks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('network', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'network', name='uq_user_network'),
    )
    op.create_index(op.f('ix_user_allowed_networks_id'), 'user_allowed_networks', ['id'], unique=False)
    op.create_index(op.f('ix_user_allowed_networks_user_id'), 'user_allowed_networks', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_allowed_networks_user_id'), table_name='user_allowed_networks')
    op.drop_index(op.f('ix_user_allowed_networks_id'), table_name='user_allowed_networks')
    op.drop_table('user_allowed_networks')
    op.drop_column('users', 'private_scan_enabled')
