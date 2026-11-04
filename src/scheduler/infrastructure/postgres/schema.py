"""SQLAlchemy Core tables mirroring migration 0001 (design §2 ERD, ADR-004).

The migration owns the DDL; these tables exist so adapters build queries without SQL strings.
Constraint names match the database, so an adapter can recognise a violated constraint by name.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, ExcludeConstraint

metadata = MetaData()

# The range every exclusion constraint compares; half-open, so back-to-back bookings coexist.
_RANGE = text("tstzrange(start_at, end_at)")

dealership = Table(
    "dealership",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", Text, nullable=False),
    Column("timezone", Text, nullable=False),
)

opening_hours = Table(
    "opening_hours",
    metadata,
    Column("dealership_id", Integer, ForeignKey("dealership.id"), nullable=False),
    Column("weekday", Integer, nullable=False),  # 0 = Monday
    Column("opens_at", Time, nullable=False),
    Column("closes_at", Time, nullable=False),
    PrimaryKeyConstraint("dealership_id", "weekday"),
    CheckConstraint("opens_at < closes_at", name="same_day_hours"),
    CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday_range"),
)

service_bay = Table(
    "service_bay",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("dealership_id", Integer, ForeignKey("dealership.id"), nullable=False),
    Column("name", Text, nullable=False),
    UniqueConstraint("id", "dealership_id", name="service_bay_id_dealership"),
)

technician = Table(
    "technician",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("dealership_id", Integer, ForeignKey("dealership.id"), nullable=False),
    Column("name", Text, nullable=False),
    UniqueConstraint("id", "dealership_id", name="technician_id_dealership"),
)

skill = Table(
    "skill",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", Text, nullable=False),
    UniqueConstraint("name", name="skill_name_key"),
)

technician_skill = Table(
    "technician_skill",
    metadata,
    Column("technician_id", Integer, ForeignKey("technician.id"), nullable=False),
    Column("skill_id", Integer, ForeignKey("skill.id"), nullable=False),
    PrimaryKeyConstraint("technician_id", "skill_id"),
)

service_type = Table(
    "service_type",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", Text, nullable=False),
    Column("duration_minutes", Integer, nullable=False),
    CheckConstraint("duration_minutes > 0", name="positive_duration"),
)

service_type_required_skill = Table(
    "service_type_required_skill",
    metadata,
    Column("service_type_id", Integer, ForeignKey("service_type.id"), nullable=False),
    Column("skill_id", Integer, ForeignKey("skill.id"), nullable=False),
    PrimaryKeyConstraint("service_type_id", "skill_id"),
)

appointment = Table(
    "appointment",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("dealership_id", Integer, ForeignKey("dealership.id"), nullable=False),
    Column("bay_id", Integer, nullable=False),
    Column("technician_id", Integer, nullable=False),
    Column("service_type_id", Integer, ForeignKey("service_type.id"), nullable=False),
    Column("start_at", DateTime(timezone=True), nullable=False),
    Column("end_at", DateTime(timezone=True), nullable=False),
    Column("status", Text, nullable=False, server_default=text("'confirmed'")),
    Column("customer_id", Text),
    Column("customer_email", Text),
    Column("customer_name", Text),
    Column("vehicle_id", Text),
    Column("vin", Text),
    Column("vehicle_key", Text, nullable=False),
    Column("make", Text),
    Column("model", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    # Tenancy: a bay or technician of another dealership cannot be referenced (ADR-004).
    ForeignKeyConstraint(
        ["bay_id", "dealership_id"],
        ["service_bay.id", "service_bay.dealership_id"],
        name="bay_in_dealership",
    ),
    ForeignKeyConstraint(
        ["technician_id", "dealership_id"],
        ["technician.id", "technician.dealership_id"],
        name="technician_in_dealership",
    ),
    CheckConstraint("end_at > start_at", name="valid_range"),
    ExcludeConstraint(("bay_id", "="), (_RANGE, "&&"), name="no_bay_overlap", using="gist"),
    ExcludeConstraint(
        ("technician_id", "="), (_RANGE, "&&"), name="no_technician_overlap", using="gist"
    ),
    ExcludeConstraint(
        ("dealership_id", "="),
        ("vehicle_key", "="),
        (_RANGE, "&&"),
        name="no_vehicle_overlap",
        using="gist",
    ),
)

idempotency_key = Table(
    "idempotency_key",
    metadata,
    Column("dealership_id", Integer, ForeignKey("dealership.id"), nullable=False),
    Column("key", Uuid, nullable=False),
    Column("request_hash", Text, nullable=False),
    Column("response_code", Text),  # NULL while claimed and not yet recorded
    Column("response_body", JSONB),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    PrimaryKeyConstraint("dealership_id", "key"),
)
