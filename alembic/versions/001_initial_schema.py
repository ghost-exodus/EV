# 

"""Initial schema — batteries, telemetry (hypertable), soh_snapshots

Revision ID: 001
Revises: None
Create Date: 2024-01-15
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check what database engine is currently executing the migration
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # ── 1. batteries: master registry ────────────────────────────────────
    op.create_table(
        "batteries",
        sa.Column("battery_id", sa.String(32), primary_key=True),
        sa.Column("vehicle_id", sa.String(64), nullable=False),
        sa.Column("nominal_capacity_mah", sa.Numeric(10, 2), nullable=False),
        sa.Column("manufacture_date", sa.Date, nullable=True),
        sa.Column("chemistry", sa.String(32), server_default="Li-Ion"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # ── 2. telemetry: raw streaming data ─────────────────────────────────
    # If SQLite, make 'id' a standard independent primary key to allow autoincrement.
    # If Postgres, use the team's composite key setup for TimescaleDB compatibility.
    if is_sqlite:
        op.create_table(
            "telemetry",
            sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column("battery_id", sa.String(32), nullable=False),
            sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("cycle_number", sa.Integer, nullable=False),
            sa.Column("voltage_v", sa.Numeric(8, 4), nullable=False),
            sa.Column("current_a", sa.Numeric(8, 4), nullable=False),
            sa.Column("temperature_c", sa.Numeric(6, 2), nullable=False),
            sa.Column("capacity_mah", sa.Numeric(10, 2), nullable=True),
            sa.Column("cycle_type", sa.String(16), nullable=False),
            sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    else:
        op.create_table(
            "telemetry",
            sa.Column("id", sa.BigInteger, autoincrement=True, nullable=False),
            sa.Column("battery_id", sa.String(32), sa.ForeignKey("batteries.battery_id"), nullable=False),
            sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("cycle_number", sa.Integer, nullable=False),
            sa.Column("voltage_v", sa.Numeric(8, 4), nullable=False),
            sa.Column("current_a", sa.Numeric(8, 4), nullable=False),
            sa.Column("temperature_c", sa.Numeric(6, 2), nullable=False),
            sa.Column("capacity_mah", sa.Numeric(10, 2), nullable=True),
            sa.Column("cycle_type", sa.String(16), nullable=False),
            sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id", "recorded_at"),
        )

    # ── 3. Convert telemetry to a TimescaleDB hypertable ─────────────────
    # Only execute hypertable partitioning if running on a real Postgres engine
    if not is_sqlite:
        op.execute("SELECT create_hypertable('telemetry', 'recorded_at');")

    # ── 4. Composite index for efficient queries ─────────────────────────
    op.create_index(
        "ix_telemetry_battery_recorded",
        "telemetry",
        ["battery_id", sa.text("recorded_at DESC")],
    )

    # ── 5. soh_snapshots: computed SoH per cycle ─────────────────────────
    op.create_table(
        "soh_snapshots",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("battery_id", sa.String(32), sa.ForeignKey("batteries.battery_id"), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cycle_number", sa.Integer, nullable=False),
        sa.Column("soh_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("capacity_mah", sa.Numeric(10, 2), nullable=False),
        sa.UniqueConstraint("battery_id", "cycle_number", name="uq_battery_cycle"),
    )


def downgrade() -> None:
    op.drop_table("soh_snapshots")
    op.drop_index("ix_telemetry_battery_recorded", table_name="telemetry")
    op.drop_table("telemetry")
    op.drop_table("batteries")