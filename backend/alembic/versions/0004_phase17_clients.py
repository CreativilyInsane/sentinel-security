"""phase 17 — clients, client_assets, target_assignments, assignment_notifications

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- clients ---
    op.create_table(
        'clients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('company_name', sa.String(length=200), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_clients_name'),
    )
    op.create_index(op.f('ix_clients_id'), 'clients', ['id'], unique=False)
    op.create_index(op.f('ix_clients_name'), 'clients', ['name'], unique=False)

    # --- client_assets ---
    op.create_table(
        'client_assets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('asset_type', sa.String(length=20), nullable=False),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('cidr', sa.String(length=80), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('network_name', sa.String(length=200), nullable=True),
        sa.Column('vlan_name', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_client_assets_id'), 'client_assets', ['id'], unique=False)
    op.create_index(op.f('ix_client_assets_client_id'), 'client_assets', ['client_id'], unique=False)
    op.create_index(op.f('ix_client_assets_ip_address'), 'client_assets', ['ip_address'], unique=False)
    op.create_index(op.f('ix_client_assets_cidr'), 'client_assets', ['cidr'], unique=False)

    # --- target_assignments ---
    op.create_table(
        'target_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=True),
        sa.Column('client_asset_id', sa.Integer(), nullable=True),
        sa.Column('assignment_type', sa.String(length=20), nullable=False),
        sa.Column('target_type', sa.String(length=20), nullable=False),
        sa.Column('target_value', sa.String(length=255), nullable=False),
        sa.Column('target_label', sa.String(length=255), nullable=True),
        sa.Column('assigned_by', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['client_asset_id'], ['client_assets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_target_assignments_id'), 'target_assignments', ['id'], unique=False)
    op.create_index(op.f('ix_target_assignments_user_id'), 'target_assignments', ['user_id'], unique=False)
    op.create_index(op.f('ix_target_assignments_client_id'), 'target_assignments', ['client_id'], unique=False)
    op.create_index(op.f('ix_target_assignments_client_asset_id'), 'target_assignments', ['client_asset_id'], unique=False)

    # --- assignment_notifications ---
    op.create_table(
        'assignment_notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=True),
        sa.Column('type', sa.String(length=40), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('is_read', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assignment_id'], ['target_assignments.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_assignment_notifications_id'), 'assignment_notifications', ['id'], unique=False)
    op.create_index(op.f('ix_assignment_notifications_user_id'), 'assignment_notifications', ['user_id'], unique=False)
    op.create_index(op.f('ix_assignment_notifications_assignment_id'), 'assignment_notifications', ['assignment_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_assignment_notifications_assignment_id'), table_name='assignment_notifications')
    op.drop_index(op.f('ix_assignment_notifications_user_id'), table_name='assignment_notifications')
    op.drop_index(op.f('ix_assignment_notifications_id'), table_name='assignment_notifications')
    op.drop_table('assignment_notifications')

    op.drop_index(op.f('ix_target_assignments_client_asset_id'), table_name='target_assignments')
    op.drop_index(op.f('ix_target_assignments_client_id'), table_name='target_assignments')
    op.drop_index(op.f('ix_target_assignments_user_id'), table_name='target_assignments')
    op.drop_index(op.f('ix_target_assignments_id'), table_name='target_assignments')
    op.drop_table('target_assignments')

    op.drop_index(op.f('ix_client_assets_cidr'), table_name='client_assets')
    op.drop_index(op.f('ix_client_assets_ip_address'), table_name='client_assets')
    op.drop_index(op.f('ix_client_assets_client_id'), table_name='client_assets')
    op.drop_index(op.f('ix_client_assets_id'), table_name='client_assets')
    op.drop_table('client_assets')

    op.drop_index(op.f('ix_clients_name'), table_name='clients')
    op.drop_index(op.f('ix_clients_id'), table_name='clients')
    op.drop_table('clients')
