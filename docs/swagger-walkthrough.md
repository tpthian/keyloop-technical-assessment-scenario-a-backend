# Trying the API in Swagger UI

A click-through of every route with values ready to paste. It covers the same sequence as `scripts/demo.sh` sections 1 to 6, one request at a time. The eight-client race (demo section 7) needs simultaneous requests, so it stays in the script and in `tests/test_concurrency.py`.

## Start the service

```sh
docker compose up -d --build --wait db api
open http://localhost:8000/docs
```

The `api` container runs the migrations and the seed: dealership 1 (Riverside Motors, Europe/London, Monday to Saturday 08:00 to 18:00), two bays, two technicians, service type 1 (Oil change, 60 minutes). `make up` alone starts only the database.

For a clean run after earlier bookings: `docker compose down && docker compose up -d --build --wait db api`.

## Pick a date

`start_at` is local time at the dealership, with no zone suffix; the service stores UTC. It must fall on a Monday to Saturday, start on or after 08:00 and before 18:00, and lie within the next 90 days. The examples below use `2026-11-09` (a Monday); replace it with the next Monday from today:

```sh
python3 -c "from datetime import date,timedelta as t;d=date.today();print(d+t((7-d.weekday())%7 or 7))"
```

Every POST needs an `Idempotency-Key` header holding a UUID. Swagger UI shows it under Parameters. Generate one with `python3 -c "import uuid;print(uuid.uuid4())"` or `uuidgen`.

## The sequence

Expand each route, press "Try it out", fill the values, press Execute.

### 1. Book: `POST /dealerships/{dealership_id}/appointments` → 201

| Field | Value |
|---|---|
| dealership_id | `1` |
| Idempotency-Key | `16b0bff2-c0d6-4ca2-8185-a22a5e8fa8a7` |

```json
{
  "service_type_id": 1,
  "start_at": "2026-11-09T09:00:00",
  "customer": {"id": "C-42", "email": null, "name": "Demo customer"},
  "vehicle": {"id": null, "vin": "WVWZZZ1JZXW000001", "make": "VW", "model": "Golf"}
}
```

The response carries `appointment_id`, the assigned `bay_id` and `technician_id`, and `end_at` one hour later in UTC.

### 2. Replay: same request again → 201, same `appointment_id`

Press Execute again without changing anything. The stored response is replayed; no second appointment is created (ADR-008).

### 3. Same key, different body → 422 `replay_conflict`

Keep the key; change only `start_at` to `"2026-11-09T10:00:00"`.

### 4. Same vehicle, overlapping time, untidy VIN → 409 `vehicle_already_booked`

| Field | Value |
|---|---|
| Idempotency-Key | `78898938-91b0-4c1f-aed9-572a061d9a55` |

```json
{
  "service_type_id": 1,
  "start_at": "2026-11-09T09:30:00",
  "customer": {"id": "C-42", "email": null, "name": "Demo customer"},
  "vehicle": {"id": null, "vin": "wvw zzz1jzxw000001", "make": "VW", "model": "Golf"}
}
```

The VIN is normalised (upper case, whitespace removed) before the vehicle constraint is checked (ADR-007).

### 5. Availability: `GET /dealerships/{dealership_id}/availability` → 200

| Field | Value |
|---|---|
| dealership_id | `1` |
| service_type_id | `1` |
| from | `2026-11-09` |
| to | `2026-11-10` |

Returns start windows per bay and technician pair, stamped with `as_of`. It is advisory: it reserves nothing (ADR-010).

### 6. A second vehicle at the same time → 201

Two bays and two technicians are seeded, so a second booking at 09:00 takes the remaining pair.

| Field | Value |
|---|---|
| Idempotency-Key | `6b0afadb-e3fd-4770-bcec-75d8ff05e5e3` |

```json
{
  "service_type_id": 1,
  "start_at": "2026-11-09T09:00:00",
  "customer": {"id": "C-43", "email": null, "name": "Second customer"},
  "vehicle": {"id": null, "vin": "WVWZZZ1JZXW000002", "make": "VW", "model": "Polo"}
}
```

A third vehicle at 09:00 with a new key returns 409 `capacity_exhausted`: no free pair.

### 7. Read back: `GET /dealerships/{dealership_id}/appointments/{appointment_id}` → 200

| Field | Value |
|---|---|
| dealership_id | `1` |
| appointment_id | `1` |

An unknown id returns 404 `not_found`.

### 8. Refusals worth seeing

| Request | Response |
|---|---|
| POST without the `Idempotency-Key` header | 400 `validation` |
| `start_at` on a Sunday, outside 08:00 to 18:00, in the past, or beyond 90 days | 422 `validation` |
| Body over 16 KiB | 413 `validation` |
| `GET /health/live`, `GET /health/ready` | 200 |

Every response body for an error has the same shape: `{"code": ..., "message": ...}`. Every request also writes one JSON event line to the `api` container log: `docker compose logs --no-log-prefix api | tail -n 3`.
