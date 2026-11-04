"""AC-01 / TC-34: schema and seed (design §2 ERD, ADR-004, ADR-009).

T2 covers the schema clauses of TC-34: ``btree_gist`` installed; the nine named constraints
exist. T3 covers the seed clauses: two dealerships; three service types, one of 4,320 minutes;
dealership 1 has 2 bays and 2 technicians; both hold ``general``, only technician 1 holds
``bodywork``. Seed rows sit below id 100, so the harness cleanup keeps them.
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


async def test_seed_two_dealerships(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        rows = await conn.execute(text("SELECT id, name, timezone FROM dealership"))
        found = {tuple(r) for r in rows}
    assert found == {
        (1, "Riverside Motors", "Europe/London"),
        (2, "Harbour Motors", "Asia/Ho_Chi_Minh"),
    }


async def test_seed_three_service_types_one_of_4320_minutes(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT st.id, st.name, st.duration_minutes, s.name FROM service_type st"
                " LEFT JOIN service_type_required_skill r ON r.service_type_id = st.id"
                " LEFT JOIN skill s ON s.id = r.skill_id"
            )
        )
        found = {tuple(r) for r in rows}
    assert found == {
        (1, "Oil change", 60, "general"),
        (2, "Major service", 180, "general"),
        (3, "Bodywork", 4320, "bodywork"),
    }


async def test_seed_dealership_1_has_two_bays_and_two_technicians(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        bays = set(await conn.scalars(text("SELECT id FROM service_bay WHERE dealership_id = 1")))
        technicians = set(
            await conn.scalars(text("SELECT id FROM technician WHERE dealership_id = 1"))
        )
    assert (bays, technicians) == ({1, 2}, {1, 2})


async def test_seed_both_hold_general_only_technician_1_holds_bodywork(
    engine: AsyncEngine,
) -> None:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT s.name, ts.technician_id FROM technician_skill ts"
                " JOIN skill s ON s.id = ts.skill_id"
                " JOIN technician t ON t.id = ts.technician_id"
                " WHERE t.dealership_id = 1 OR s.name = 'bodywork'"
            )
        )
        holders: dict[str, set[int]] = {}
        for skill, technician_id in rows:
            holders.setdefault(skill, set()).add(technician_id)
    assert holders == {"general": {1, 2}, "bodywork": {1}}
