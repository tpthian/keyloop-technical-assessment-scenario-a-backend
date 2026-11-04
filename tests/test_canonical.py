"""TC-07: canonical request hash of ADR-008 (domain, pure). One test per TC clause."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from scheduler.domain.canonical import canonical_hash, normalise_vin
from scheduler.domain.model import BookingCommand, Customer, Vehicle

LONDON = ZoneInfo("Europe/London")


def command_from_json(raw: str) -> BookingCommand:
    """Stand-in for the interface mapping: parsed JSON -> command, VIN normalised."""
    body: dict[str, Any] = json.loads(raw)
    c, v = body["customer"], body["vehicle"]
    return BookingCommand(
        dealership_id=1,
        service_type_id=body["service_type_id"],
        start_local=datetime.fromisoformat(body["start_at"]),
        customer=Customer(id=c.get("id"), email=c.get("email"), name=c.get("name")),
        vehicle=Vehicle(
            id=v.get("id"),
            vin=normalise_vin(v.get("vin")),
            make=v.get("make"),
            model=v.get("model"),
        ),
        idempotency_key=UUID("00000000-0000-4000-8000-000000000001"),
    )


BASE_JSON = (
    '{"service_type_id": 1, "start_at": "2027-03-26T09:00:00",'
    ' "customer": {"id": "C-42", "email": null, "name": "Sam Lee"},'
    ' "vehicle": {"id": null, "vin": "WVWZZZ1JZXW000001", "make": "VW", "model": "Golf"}}'
)
BASE_HASH = canonical_hash(command_from_json(BASE_JSON), LONDON)


def test_tc07_key_order_does_not_change_the_hash() -> None:
    reordered = (
        '{"vehicle": {"model": "Golf", "make": "VW", "vin": "WVWZZZ1JZXW000001", "id": null},'
        ' "customer": {"name": "Sam Lee", "email": null, "id": "C-42"},'
        ' "start_at": "2027-03-26T09:00:00", "service_type_id": 1}'
    )
    assert canonical_hash(command_from_json(reordered), LONDON) == BASE_HASH


def test_tc07_whitespace_does_not_change_the_hash() -> None:
    spaced = BASE_JSON.replace(", ", ",\n   ").replace(": ", " :  ")
    assert canonical_hash(command_from_json(spaced), LONDON) == BASE_HASH


def test_tc07_null_fields_do_not_change_the_hash() -> None:
    absent = BASE_JSON.replace(' "email": null,', "").replace('"id": null, ', "")
    assert canonical_hash(command_from_json(absent), LONDON) == BASE_HASH


def test_tc07_vin_spacing_does_not_change_the_hash() -> None:
    spaced = BASE_JSON.replace('"WVWZZZ1JZXW000001"', '" wvw zzz 1jz xw0 00001 "')
    assert canonical_hash(command_from_json(spaced), LONDON) == BASE_HASH


def test_tc07_utc_instant_is_hashed() -> None:
    # summer wall time 09:00 BST is hashed as the instant 08:00Z, in the sorted compact form
    summer = command_from_json(BASE_JSON.replace("2027-03-26T09:00:00", "2027-06-01T09:00:00"))
    form = (
        '{"customer":{"id":"C-42","name":"Sam Lee"},"service_type_id":1,'
        '"start_at":"2027-06-01T08:00:00+00:00",'
        '"vehicle":{"make":"VW","model":"Golf","vin":"WVWZZZ1JZXW000001"}}'
    )
    assert canonical_hash(summer, LONDON) == hashlib.sha256(form.encode()).hexdigest()
