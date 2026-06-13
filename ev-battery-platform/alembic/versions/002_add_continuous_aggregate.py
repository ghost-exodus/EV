"""add_continuous_aggregate

Revision ID: 002
Revises: 001
Create Date: 2026-06-13 13:24:37.487168

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Drop constraints on soh_snapshots to prepare for hypertable conversion ──
    # TimescaleDB requires any unique/primary constraints to include the time partitioning column.
    op.drop_constraint("soh_snapshots_pkey", "soh_snapshots", type_="primary")
    op.drop_constraint("uq_battery_cycle", "soh_snapshots", type_="unique")

    # ── 2. Re-create primary key as composite including the time column ─────
    op.create_primary_key(
        "soh_snapshots_pkey",
        "soh_snapshots",
        ["id", "snapshot_at"]
    )

    # ── 3. Convert soh_snapshots to a TimescaleDB hypertable ──────────────────
    op.execute("SELECT create_hypertable('soh_snapshots', 'snapshot_at');")

    # ── 4. Create index on snapshot_at for efficient aggregate querying ─────
    op.create_index(
        "ix_soh_snapshots_snapshot_at",
        "soh_snapshots",
        ["snapshot_at"]
    )

    # ── 5. Create continuous aggregate view ──────────────────────────────────
    op.execute("""
        CREATE MATERIALIZED VIEW hourly_soh_avg
        WITH (timescaledb.continuous) AS
        SELECT battery_id,
               time_bucket('1 hour', snapshot_at) AS hour_bucket,
               AVG(soh_percent) AS avg_soh,
               MIN(soh_percent) AS min_soh
        FROM soh_snapshots
        GROUP BY battery_id, hour_bucket;
    """)

    # ── 6. Add policy to refresh aggregate view periodically ──────────────────
    op.execute("""
        SELECT add_continuous_aggregate_policy('hourly_soh_avg',
          start_offset => INTERVAL '3 hours',
          end_offset => INTERVAL '1 hour',
          schedule_interval => INTERVAL '1 hour');
    """)


def downgrade() -> None:
    # ── 1. Remove continuous aggregate and policy ────────────────────────────
    # In TimescaleDB, dropping the materialized view automatically removes its policy
    op.execute("DROP MATERIALIZED VIEW IF EXISTS hourly_soh_avg;")

    # ── 2. Revert soh_snapshots to standard table ────────────────────────────
    # Since hypertable conversion cannot be undone directly in TimescaleDB,
    # we drop the table and recreate it in its original 001 state.
    op.drop_table("soh_snapshots")
    op.create_table(
        "soh_snapshots",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "battery_id",
            sa.String(32),
            sa.ForeignKey("batteries.battery_id"),
            nullable=False,
        ),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cycle_number", sa.Integer, nullable=False),
        sa.Column("soh_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("capacity_mah", sa.Numeric(10, 2), nullable=False),
        sa.UniqueConstraint("battery_id", "cycle_number", name="uq_battery_cycle"),
    )
