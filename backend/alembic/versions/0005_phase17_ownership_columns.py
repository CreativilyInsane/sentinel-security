"""phase 17 — ownership columns on recon_scans + recon_assets

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-10 00:01:00.000000

Adds provenance/ownership columns to existing scan and asset tables.
Existing rows are back-filled with USER_MANUAL so that no historical
data is lost or mis-attributed.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- recon_scans ownership columns ---
    op.add_column('recon_scans', sa.Column('ownership_type', sa.String(length=30), nullable=False, server_default='USER_MANUAL'))
    op.add_column('recon_scans', sa.Column('client_id', sa.Integer(), nullable=True))
    op.add_column('recon_scans', sa.Column('client_asset_id', sa.Integer(), nullable=True))
    op.add_column('recon_scans', sa.Column('assignment_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_recon_scans_ownership_type'), 'recon_scans', ['ownership_type'], unique=False)
    op.create_index(op.f('ix_recon_scans_client_id'), 'recon_scans', ['client_id'], unique=False)
    op.create_foreign_key('fk_recon_scans_client_id', 'recon_scans', 'clients', ['client_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_recon_scans_client_asset_id', 'recon_scans', 'client_assets', ['client_asset_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_recon_scans_assignment_id', 'recon_scans', 'target_assignments', ['assignment_id'], ['id'], ondelete='SET NULL')

    # --- recon_assets ownership columns ---
    op.add_column('recon_assets', sa.Column('ownership_type', sa.String(length=30), nullable=False, server_default='USER_MANUAL'))
    op.add_column('recon_assets', sa.Column('client_id', sa.Integer(), nullable=True))
    op.add_column('recon_assets', sa.Column('client_asset_id', sa.Integer(), nullable=True))
    op.add_column('recon_assets', sa.Column('assignment_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_recon_assets_ownership_type'), 'recon_assets', ['ownership_type'], unique=False)
    op.create_index(op.f('ix_recon_assets_client_id'), 'recon_assets', ['client_id'], unique=False)
    op.create_foreign_key('fk_recon_assets_client_id', 'recon_assets', 'clients', ['client_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_recon_assets_client_asset_id', 'recon_assets', 'client_assets', ['client_asset_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_recon_assets_assignment_id', 'recon_assets', 'target_assignments', ['assignment_id'], ['id'], ondelete='SET NULL')

    # Existing scans/assets are USER_MANUAL by virtue of the server_default —
    # no explicit UPDATE is needed.


def downgrade() -> None:
    op.drop_constraint('fk_recon_assets_assignment_id', 'recon_assets', type_='foreignkey')
    op.drop_constraint('fk_recon_assets_client_asset_id', 'recon_assets', type_='foreignkey')
    op.drop_constraint('fk_recon_assets_client_id', 'recon_assets', type_='foreignkey')
    op.drop_index(op.f('ix_recon_assets_client_id'), table_name='recon_assets')
    op.drop_index(op.f('ix_recon_assets_ownership_type'), table_name='recon_assets')
    op.drop_column('recon_assets', 'assignment_id')
    op.drop_column('recon_assets', 'client_asset_id')
    op.drop_column('recon_assets', 'client_id')
    op.drop_column('recon_assets', 'ownership_type')

    op.drop_constraint('fk_recon_scans_assignment_id', 'recon_scans', type_='foreignkey')
    op.drop_constraint('fk_recon_scans_client_asset_id', 'recon_scans', type_='foreignkey')
    op.drop_constraint('fk_recon_scans_client_id', 'recon_scans', type_='foreignkey')
    op.drop_index(op.f('ix_recon_scans_client_id'), table_name='recon_scans')
    op.drop_index(op.f('ix_recon_scans_ownership_type'), table_name='recon_scans')
    op.drop_column('recon_scans', 'assignment_id')
    op.drop_column('recon_scans', 'client_asset_id')
    op.drop_column('recon_scans', 'client_id')
    op.drop_column('recon_scans', 'ownership_type')
