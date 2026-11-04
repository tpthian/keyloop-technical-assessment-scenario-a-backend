"""Canonical request form and hash for the idempotency key (ADR-008, D-041 item 7).

The hash is stored on the key row and compared on every retry, so its byte form is part of the
persisted contract: changing it turns stored retries into ``replay_conflict``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from zoneinfo import ZoneInfo

from scheduler.domain.model import BookingCommand
from scheduler.domain.time_rules import canonical_utc


def normalise_vin(raw: str | None) -> str | None:
    """Upper case with all whitespace removed; empty after that is ``None`` (design §2)."""
    if raw is None:
        return None
    vin = "".join(raw.split()).upper()
    return vin or None


def _without_nulls(fields: dict[str, object]) -> dict[str, object]:
    return {k: v for k, v in fields.items() if v is not None}


def canonical_hash(command: BookingCommand, zone: ZoneInfo) -> str:
    """sha256 hex of the canonical request: sorted keys, no whitespace, nulls omitted.

    Covers ``service_type_id``, ``start_at`` as the UTC instant of the wall time in the
    dealership zone (first occurrence; a gap time still hashes deterministically),
    ``customer`` and ``vehicle`` with the VIN normalised. The dealership and the key itself are
    not hashed: the key is already scoped per dealership.
    """
    vehicle = asdict(command.vehicle)
    vehicle["vin"] = normalise_vin(command.vehicle.vin)
    canonical = {
        "service_type_id": command.service_type_id,
        "start_at": canonical_utc(command.start_local, zone).isoformat(),
        "customer": _without_nulls(asdict(command.customer)),
        "vehicle": _without_nulls(vehicle),
    }
    form = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(form.encode("utf-8")).hexdigest()
