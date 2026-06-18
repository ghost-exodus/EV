"""add_rul_predictions

Revision ID: 003
Revises: 002
Create Date: 2026-06-13 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rul_predictions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "battery_id",
            sa.String(32),
            sa.ForeignKey("batteries.battery_id"),
            nullable=False,
        ),
        sa.Column(
            "predicted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("predicted_rul_cycles", sa.Integer, nullable=False),
        sa.Column("confidence_lower", sa.Integer, nullable=True),
        sa.Column("confidence_upper", sa.Integer, nullable=True),
        sa.Column("model_version", sa.String(16), nullable=False),
        sa.Column("input_soh_percent", sa.Numeric(5, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("rul_predictions")
