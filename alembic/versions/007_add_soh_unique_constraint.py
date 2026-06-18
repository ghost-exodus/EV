"""add_soh_unique_constraint

Revision ID: 007
Revises: 006
Create Date: 2026-06-14 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add unique constraint to prevent duplicate SoH snapshots per battery+cycle.
    # This enables safe ON CONFLICT DO UPDATE upserts and eliminates the
    # select-then-insert TOCTOU race condition under concurrent ingestion.
    op.create_unique_constraint(
        'uq_soh_battery_cycle',
        'soh_snapshots',
        ['battery_id', 'cycle_number']
    )


def downgrade() -> None:
    op.drop_constraint('uq_soh_battery_cycle', 'soh_snapshots', type_='unique')
