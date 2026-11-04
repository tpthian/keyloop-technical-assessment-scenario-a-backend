"""AC-01 / TC-34: schema and seed (design §2 ERD, ADR-004, ADR-009).

T2 covers the schema clauses of TC-34: ``btree_gist`` installed; the nine named constraints
exist. The seed clauses are T3's.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

# name -> (table, contype, definition as pg_get_constraintdef prints it). The definition is
# asserted too: a constraint of the right name over the wrong columns breaks the guarantee.
NAMED_CONSTRAINTS: dict[str, tuple[str, str, str]] = {
    "no_bay_overlap": (
        "appointment",
        "x",
        "EXCLUDE USING gist (bay_id WITH =, tstzrange(start_at, end_at) WITH &&)",
    ),
    "no_technician_overlap": (
        "appointment",
        "x",
        "EXCLUDE USING gist (technician_id WITH =, tstzrange(start_at, end_at) WITH &&)",
    ),
    "no_vehicle_overlap": (
        "appointment",
        "x",
        "EXCLUDE USING gist (dealership_id WITH =, vehicle_key WITH =,"
        " tstzrange(start_at, end_at) WITH &&)",
    ),
    "bay_in_dealership": (
        "appointment",
        "f",
        "FOREIGN KEY (bay_id, dealership_id) REFERENCES service_bay(id, dealership_id)",
    ),
    "technician_in_dealership": (
        "appointment",
        "f",
        "FOREIGN KEY (technician_id, dealership_id) REFERENCES technician(id, dealership_id)",
    ),
    "valid_range": ("appointment", "c", "CHECK ((end_at > start_at))"),
    "positive_duration": ("service_type", "c", "CHECK ((duration_minutes > 0))"),
    "same_day_hours": ("opening_hours", "c", "CHECK ((opens_at < closes_at))"),
    "weekday_range": ("opening_hours", "c", "CHECK (((weekday >= 0) AND (weekday <= 6)))"),
}


async def test_btree_gist_installed(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        found = await conn.scalar(
            text("SELECT count(*) FROM pg_extension WHERE extname = 'btree_gist'")
        )
    assert found == 1


async def test_nine_named_constraints_exist(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT c.conname, t.relname, c.contype::text, pg_get_constraintdef(c.oid)"
                " FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid"
                " WHERE c.conname = ANY(:names)"
            ),
            {"names": list(NAMED_CONSTRAINTS)},
        )
        found = {r[0]: (r[1], r[2], r[3]) for r in rows}
    assert found == NAMED_CONSTRAINTS
