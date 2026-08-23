"""phase 17 — add domain column to client_assets

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-10 00:02:00.000000

Adds a ``domain`` column to ``client_assets`` so administrators can
include domain names (e.g. ``acme.com``) alongside IPs and CIDR ranges
when defining a client's asset inventory.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('client_assets', sa.Column('domain', sa.String(length=512), nullable=True))
    op.create_index(op.f('ix_client_assets_domain'), 'client_assets', ['domain'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_client_assets_domain'), table_name='client_assets')
    op.drop_column('client_assets', 'domain')
