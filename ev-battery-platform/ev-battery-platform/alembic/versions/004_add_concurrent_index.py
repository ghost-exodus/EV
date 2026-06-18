"""add_concurrent_index

Revision ID: 004
Revises: 003
Create Date: 2026-06-13 16:32:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enable DDL transaction as we are running standard DDL now
disable_ddl_transaction = False


def upgrade() -> None:
    # Drop the old index (safe if already dropped in a previous failed run)
    try:
        op.drop_index(
            "ix_telemetry_battery_recorded",
            table_name="telemetry",
        )
    except Exception:
        pass
    # Create the new index
    op.create_index(
        "idx_telemetry_battery_recorded",
        "telemetry",
        ["battery_id", sa.text("recorded_at DESC")],
    )


def downgrade() -> None:
    # Drop the new index
    try:
        op.drop_index(
            "idx_telemetry_battery_recorded",
            table_name="telemetry",
        )
    except Exception:
        pass
    # Recreate the old index
    op.create_index(
        "ix_telemetry_battery_recorded",
        "telemetry",
        ["battery_id", sa.text("recorded_at DESC")],
    )
