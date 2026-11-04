"""Schema: every table of the design §2 ERD and the booking guarantee of ADR-004.

The DDL is given verbatim by SPEC-001 task T2. PostgreSQL holds the invariant: three exclusion
constraints (bay, technician, vehicle) over half-open ``tstzrange`` values, composite tenancy
foreign keys, and the CHECKs that close the empty-range hole. This migration owns the DDL;
``scheduler.infrastructure.postgres.schema`` mirrors it as Core tables for queries.

Revision ID: 0001
Revises:
Create Date: 2026-11-04
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# One statement per entry, in order; the text is the SPEC's DDL unchanged.
UPGRADE: tuple[str, ...] = (
    "CREATE EXTENSION IF NOT EXISTS btree_gist",
    """
CREATE TABLE dealership (
    id        serial PRIMARY KEY,
    name      text NOT NULL,
    timezone  text NOT NULL
)""",
    """
CREATE TABLE opening_hours (
    dealership_id int  NOT NULL REFERENCES dealership (id),
    weekday       int  NOT NULL,                        -- 0 = Monday
    opens_at      time NOT NULL,
    closes_at     time NOT NULL,
    PRIMARY KEY (dealership_id, weekday),
    CONSTRAINT same_day_hours CHECK (opens_at < closes_at),
    CONSTRAINT weekday_range  CHECK (weekday BETWEEN 0 AND 6)
)""",
    """
CREATE TABLE service_bay (
    id            serial PRIMARY KEY,
    dealership_id int  NOT NULL REFERENCES dealership (id),
    name          text NOT NULL,
    CONSTRAINT service_bay_id_dealership UNIQUE (id, dealership_id)
)""",
    """
CREATE TABLE technician (
    id            serial PRIMARY KEY,
    dealership_id int  NOT NULL REFERENCES dealership (id),
    name          text NOT NULL,
    CONSTRAINT technician_id_dealership UNIQUE (id, dealership_id)
)""",
    """
CREATE TABLE skill (
    id   serial PRIMARY KEY,
    name text NOT NULL UNIQUE
)""",
    """
CREATE TABLE technician_skill (
    technician_id int NOT NULL REFERENCES technician (id),
    skill_id      int NOT NULL REFERENCES skill (id),
    PRIMARY KEY (technician_id, skill_id)
)""",
    """
CREATE TABLE service_type (
    id               serial PRIMARY KEY,
    name             text NOT NULL,
    duration_minutes int  NOT NULL,
    CONSTRAINT positive_duration CHECK (duration_minutes > 0)
)""",
    """
CREATE TABLE service_type_required_skill (
    service_type_id int NOT NULL REFERENCES service_type (id),
    skill_id        int NOT NULL REFERENCES skill (id),
    PRIMARY KEY (service_type_id, skill_id)
)""",
    """
CREATE TABLE appointment (
    id              serial PRIMARY KEY,
    dealership_id   int  NOT NULL REFERENCES dealership (id),
    bay_id          int  NOT NULL,
    technician_id   int  NOT NULL,
    service_type_id int  NOT NULL REFERENCES service_type (id),
    start_at        timestamptz NOT NULL,
    end_at          timestamptz NOT NULL,
    status          text NOT NULL DEFAULT 'confirmed',
    customer_id     text,
    customer_email  text,
    customer_name   text,
    vehicle_id      text,
    vin             text,
    vehicle_key     text NOT NULL,
    make            text,
    model           text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    -- Tenancy: a bay or technician of another dealership cannot be referenced (ADR-004).
    CONSTRAINT bay_in_dealership
        FOREIGN KEY (bay_id, dealership_id) REFERENCES service_bay (id, dealership_id),
    CONSTRAINT technician_in_dealership
        FOREIGN KEY (technician_id, dealership_id) REFERENCES technician (id, dealership_id),
    -- An empty or inverted range overlaps nothing and would stack without limit.
    CONSTRAINT valid_range CHECK (end_at > start_at),
    CONSTRAINT no_bay_overlap
        EXCLUDE USING gist (bay_id WITH =, tstzrange(start_at, end_at) WITH &&),
    CONSTRAINT no_technician_overlap
        EXCLUDE USING gist (technician_id WITH =, tstzrange(start_at, end_at) WITH &&),
    CONSTRAINT no_vehicle_overlap
        EXCLUDE USING gist (
            dealership_id WITH =, vehicle_key WITH =, tstzrange(start_at, end_at) WITH &&
        )
)""",
    """
CREATE TABLE idempotency_key (
    dealership_id   int   NOT NULL REFERENCES dealership (id),
    key             uuid  NOT NULL,
    request_hash    text  NOT NULL,
    response_code   text,                               -- NULL while claimed and not yet recorded
    response_body   jsonb,
    created_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (dealership_id, key)
)""",
    """
-- deadlock_timeout is superuser-level; the booking transaction sets it locally (ADR-004).
GRANT SET ON PARAMETER deadlock_timeout TO CURRENT_USER""",
)

# Reverse order of creation, ending with the extension the first statement created.
DOWNGRADE: tuple[str, ...] = (
    "REVOKE SET ON PARAMETER deadlock_timeout FROM CURRENT_USER",
    "DROP TABLE idempotency_key",
    "DROP TABLE appointment",
    "DROP TABLE service_type_required_skill",
    "DROP TABLE service_type",
    "DROP TABLE technician_skill",
    "DROP TABLE skill",
    "DROP TABLE technician",
    "DROP TABLE service_bay",
    "DROP TABLE opening_hours",
    "DROP TABLE dealership",
    "DROP EXTENSION IF EXISTS btree_gist",
)


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE:
        op.execute(statement)
