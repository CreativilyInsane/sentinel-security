"""recon tables

Revision ID: 0002
Revises: 0001
Create Date: 2024-02-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- recon_scans ---
    op.create_table(
        'recon_scans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('target', sa.String(length=512), nullable=False),
        sa.Column('target_type', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='QUEUED'),
        sa.Column('modules', sa.JSON(), nullable=False),
        sa.Column('port_preset', sa.String(length=20), nullable=True),
        sa.Column('custom_ports', sa.JSON(), nullable=True),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('celery_task_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_recon_scans_id'), 'recon_scans', ['id'], unique=False)
    op.create_index(op.f('ix_recon_scans_user_id'), 'recon_scans', ['user_id'], unique=False)
    op.create_index(op.f('ix_recon_scans_status'), 'recon_scans', ['status'], unique=False)
    op.create_index(op.f('ix_recon_scans_celery_task_id'), 'recon_scans', ['celery_task_id'], unique=False)

    # --- recon_scan_results ---
    op.create_table(
        'recon_scan_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scan_id', sa.Integer(), nullable=False),
        sa.Column('result_type', sa.String(length=30), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['scan_id'], ['recon_scans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_recon_scan_results_id'), 'recon_scan_results', ['id'], unique=False)
    op.create_index(op.f('ix_recon_scan_results_scan_id'), 'recon_scan_results', ['scan_id'], unique=False)
    op.create_index(op.f('ix_recon_scan_results_result_type'), 'recon_scan_results', ['result_type'], unique=False)

    # --- recon_assets ---
    op.create_table(
        'recon_assets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('scan_id', sa.Integer(), nullable=True),
        sa.Column('host', sa.String(length=512), nullable=False),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('hostname', sa.String(length=512), nullable=True),
        sa.Column('port', sa.Integer(), nullable=True),
        sa.Column('protocol', sa.String(length=10), nullable=True),
        sa.Column('service', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=True),
        sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['scan_id'], ['recon_scans.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_recon_assets_id'), 'recon_assets', ['id'], unique=False)
    op.create_index(op.f('ix_recon_assets_user_id'), 'recon_assets', ['user_id'], unique=False)
    op.create_index(op.f('ix_recon_assets_scan_id'), 'recon_assets', ['scan_id'], unique=False)
    op.create_index(op.f('ix_recon_assets_host'), 'recon_assets', ['host'], unique=False)
    op.create_index(op.f('ix_recon_assets_ip_address'), 'recon_assets', ['ip_address'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_recon_assets_ip_address'), table_name='recon_assets')
    op.drop_index(op.f('ix_recon_assets_host'), table_name='recon_assets')
    op.drop_index(op.f('ix_recon_assets_scan_id'), table_name='recon_assets')
    op.drop_index(op.f('ix_recon_assets_user_id'), table_name='recon_assets')
    op.drop_index(op.f('ix_recon_assets_id'), table_name='recon_assets')
    op.drop_table('recon_assets')

    op.drop_index(op.f('ix_recon_scan_results_result_type'), table_name='recon_scan_results')
    op.drop_index(op.f('ix_recon_scan_results_scan_id'), table_name='recon_scan_results')
    op.drop_index(op.f('ix_recon_scan_results_id'), table_name='recon_scan_results')
    op.drop_table('recon_scan_results')

    op.drop_index(op.f('ix_recon_scans_celery_task_id'), table_name='recon_scans')
    op.drop_index(op.f('ix_recon_scans_status'), table_name='recon_scans')
    op.drop_index(op.f('ix_recon_scans_user_id'), table_name='recon_scans')
    op.drop_index(op.f('ix_recon_scans_id'), table_name='recon_scans')
    op.drop_table('recon_scans')
