"""
SQLAlchemy ORM models for EV Battery Telemetry platform.

Tables:
  - batteries:      Master battery registry
  - telemetry:      Raw streaming telemetry data (TimescaleDB hypertable)
  - soh_snapshots:  Computed State-of-Health per cycle
"""

from sqlalchemy import (
    Column,
    String,
    Integer,
    BigInteger,
    Numeric,
    Date,
    DateTime,
    UniqueConstraint,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class Battery(Base):
    __tablename__ = "batteries"

    battery_id = Column(String(32), primary_key=True)
    vehicle_id = Column(String(64), nullable=False)
    nominal_capacity_mah = Column(Numeric(10, 2), nullable=False)
    manufacture_date = Column(Date, nullable=True)
    chemistry = Column(String(32), default="Li-Ion")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    telemetry_readings = relationship("Telemetry", back_populates="battery")
    soh_snapshots = relationship("SoHSnapshot", back_populates="battery")
    rul_predictions = relationship("RULPrediction", back_populates="battery")

    def __repr__(self) -> str:
        return f"<Battery(battery_id={self.battery_id!r})>"


class Telemetry(Base):
    __tablename__ = "telemetry"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    battery_id = Column(
        String(32),
        ForeignKey("batteries.battery_id"),
        nullable=False,
    )
    recorded_at = Column(DateTime(timezone=True), nullable=False)
    cycle_number = Column(Integer, nullable=False)
    voltage_v = Column(Numeric(8, 4), nullable=False)
    current_a = Column(Numeric(8, 4), nullable=False)
    temperature_c = Column(Numeric(6, 2), nullable=False)
    capacity_mah = Column(Numeric(10, 2), nullable=True)
    cycle_type = Column(String(16), nullable=False)
    internal_resistance_ohm = Column(Numeric(10, 6), nullable=True)
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    battery = relationship("Battery", back_populates="telemetry_readings")

    # Index on (battery_id, recorded_at DESC) is created in the Alembic migration
    # alongside the TimescaleDB hypertable conversion.

    def __repr__(self) -> str:
        return (
            f"<Telemetry(id={self.id}, battery_id={self.battery_id!r}, "
            f"recorded_at={self.recorded_at})>"
        )


class SoHSnapshot(Base):
    __tablename__ = "soh_snapshots"
    __table_args__ = (
        UniqueConstraint("battery_id", "cycle_number", name="uq_soh_battery_cycle"),
    )

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    battery_id = Column(
        String(32),
        ForeignKey("batteries.battery_id"),
        nullable=False,
    )
    snapshot_at = Column(DateTime(timezone=True), nullable=False)
    cycle_number = Column(Integer, nullable=False)
    soh_percent = Column(Numeric(5, 2), nullable=False)
    capacity_mah = Column(Numeric(10, 2), nullable=False)

    # Relationships
    battery = relationship("Battery", back_populates="soh_snapshots")

    def __repr__(self) -> str:
        return (
            f"<SoHSnapshot(battery_id={self.battery_id!r}, "
            f"cycle={self.cycle_number}, soh={self.soh_percent}%)>"
        )


class RULPrediction(Base):
    __tablename__ = "rul_predictions"

    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    battery_id = Column(
        String(32),
        ForeignKey("batteries.battery_id"),
        nullable=False,
    )
    predicted_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    predicted_rul_cycles = Column(Integer, nullable=False)
    confidence_lower = Column(Integer, nullable=True)
    confidence_upper = Column(Integer, nullable=True)
    model_version = Column(String(16), nullable=False)
    input_soh_percent = Column(Numeric(5, 2), nullable=True)

    # Relationships
    battery = relationship("Battery", back_populates="rul_predictions")

    def __repr__(self) -> str:
        return (
            f"<RULPrediction(battery_id={self.battery_id!r}, "
            f"rul={self.predicted_rul_cycles}, model={self.model_version})>"
        )
