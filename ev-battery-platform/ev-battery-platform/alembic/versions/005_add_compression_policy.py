"""add_compression_policy

Revision ID: 005
Revises: 004
Create Date: 2026-06-13 17:03:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# TimescaleDB policy additions cannot run inside a transaction
disable_ddl_transaction = True


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        if connection.in_transaction():
            connection.commit()
        autocommit_conn = connection.execution_options(isolation_level="AUTOCOMMIT")
        # Enable compression and configure segmentby/orderby
        autocommit_conn.execute(sa.text(
            "ALTER TABLE telemetry SET ("
            "  timescaledb.compress,"
            "  timescaledb.compress_segmentby = 'battery_id',"
            "  timescaledb.compress_orderby = 'recorded_at DESC'"
            ");"
        ))
        # Add a policy to compress chunks older than 7 days
        autocommit_conn.execute(sa.text("SELECT add_compression_policy('telemetry', INTERVAL '7 days');"))


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        if connection.in_transaction():
            connection.commit()
        autocommit_conn = connection.execution_options(isolation_level="AUTOCOMMIT")
        # Remove compression policy
        autocommit_conn.execute(sa.text("SELECT remove_compression_policy('telemetry');"))
