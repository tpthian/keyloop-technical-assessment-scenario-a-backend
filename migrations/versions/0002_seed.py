"""Seed: the reference world of the demo and the tests (ADR-006, ADR-009, D-041 item 4).

Dealership 1 "Riverside Motors" (``Europe/London``, Mon-Sat 08:00-18:00, Sunday closed) has
bays 1 and 2 and technicians Ada (1: general, bodywork) and Grace (2: general). Dealership 2
"Harbour Motors" (``Asia/Ho_Chi_Minh``, Mon-Fri 08:00-17:00) has bay 3 and technician Minh
(3: general). Service types: Oil change 60 min and Major service 180 min need ``general``;
Bodywork 4,320 min needs ``bodywork``. Opening hours are local wall time; ``weekday`` is 0..6
with 0 = Monday (L-004), and a missing weekday is closed (ADR-009).

Ids are explicit and below 100; the seeded tables' sequences then move to 99, so the next
generated id is 100 and never collides with a seed row. Hours change by migration (ADR-009).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-04
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONDAY_TO_SATURDAY = range(6)  # 0 = Monday .. 5 = Saturday; Sunday (6) closed
MONDAY_TO_FRIDAY = range(5)  # 0 = Monday .. 4 = Friday; weekend closed


def _hours(dealership_id: int, weekdays: range, opens_at: str, closes_at: str) -> str:
    return ", ".join(f"({dealership_id}, {wd}, '{opens_at}', '{closes_at}')" for wd in weekdays)


# Tables whose serial sequence moves past the seed ids.
SEEDED_TABLES: tuple[str, ...] = (
    "dealership",
    "service_bay",
    "technician",
    "skill",
    "service_type",
)

UPGRADE: tuple[str, ...] = (
    "INSERT INTO dealership (id, name, timezone) VALUES"
    " (1, 'Riverside Motors', 'Europe/London'),"
    " (2, 'Harbour Motors', 'Asia/Ho_Chi_Minh')",
    "INSERT INTO opening_hours (dealership_id, weekday, opens_at, closes_at) VALUES "
    + _hours(1, MONDAY_TO_SATURDAY, "08:00", "18:00")
    + ", "
    + _hours(2, MONDAY_TO_FRIDAY, "08:00", "17:00"),
    "INSERT INTO skill (id, name) VALUES (1, 'general'), (2, 'bodywork')",
    "INSERT INTO service_type (id, name, duration_minutes) VALUES"
    " (1, 'Oil change', 60), (2, 'Major service', 180), (3, 'Bodywork', 4320)",
    "INSERT INTO service_type_required_skill (service_type_id, skill_id) VALUES"
    " (1, 1), (2, 1), (3, 2)",
    "INSERT INTO service_bay (id, dealership_id, name) VALUES"
    " (1, 1, 'Bay 1'), (2, 1, 'Bay 2'), (3, 2, 'Bay 3')",
    "INSERT INTO technician (id, dealership_id, name) VALUES"
    " (1, 1, 'Ada'), (2, 1, 'Grace'), (3, 2, 'Minh')",
    # Ada: general, bodywork; Grace: general; Minh: general.
    "INSERT INTO technician_skill (technician_id, skill_id) VALUES (1, 1), (1, 2), (2, 1), (3, 1)",
    *(f"SELECT setval(pg_get_serial_sequence('{t}', 'id'), 99)" for t in SEEDED_TABLES),
)

# Reverse order of insertion; sequences back to their fresh state (next id 1).
DOWNGRADE: tuple[str, ...] = (
    "DELETE FROM technician_skill WHERE technician_id IN (1, 2, 3)",
    "DELETE FROM technician WHERE id IN (1, 2, 3)",
    "DELETE FROM service_bay WHERE id IN (1, 2, 3)",
    "DELETE FROM service_type_required_skill WHERE service_type_id IN (1, 2, 3)",
    "DELETE FROM service_type WHERE id IN (1, 2, 3)",
    "DELETE FROM skill WHERE id IN (1, 2)",
    "DELETE FROM opening_hours WHERE dealership_id IN (1, 2)",
    "DELETE FROM dealership WHERE id IN (1, 2)",
    *(f"SELECT setval(pg_get_serial_sequence('{t}', 'id'), 1, false)" for t in SEEDED_TABLES),
)


def upgrade() -> None:
    for statement in UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWNGRADE:
        op.execute(statement)
