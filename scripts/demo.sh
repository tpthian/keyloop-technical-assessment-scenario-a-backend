#!/usr/bin/env bash
# Demonstration of the booking service against seeded dealership 1 (ADR-012, D-035).
#
# Run with `make demo`, which starts db and api with docker compose first. The script expects
# a fresh database: `make down && make demo` is the clean rerun. Eight sections; every
# response lands in its own file under a temporary directory, printed at the start. The last
# printed line is the overlap count of design section 5, which must be 0.
#
# Requires: curl, jq, python3 (date and UUID generation), docker compose.
set -euo pipefail

cd "$(dirname "$0")/.."

API="${API_URL:-http://localhost:8000}"
D=1          # dealership 1, Riverside Motors, Europe/London, Mon-Sat 08:00-18:00 (0002_seed.py)
OIL_CHANGE=1 # service type 1, Oil change, 60 min, needs `general` (both technicians hold it)
RACE_CLIENTS=8

for tool in curl jq python3 docker; do
  if ! command -v "$tool" >/dev/null; then
    echo "demo.sh: $tool is required" >&2
    exit 1
  fi
done

# The overlap SQL of design section 5 (same text as OVERLAP_SQL in tests/conftest.py).
OVERLAP_SQL="SELECT count(*) FROM appointment a JOIN appointment b ON a.id < b.id
 AND (a.bay_id = b.bay_id
      OR a.technician_id = b.technician_id
      OR (a.dealership_id = b.dealership_id AND a.vehicle_key = b.vehicle_key))
 AND tstzrange(a.start_at, a.end_at) && tstzrange(b.start_at, b.end_at)"

psql_value() {
  docker compose exec -T db psql -U scheduler -d scheduler -tAX -c "$1"
}

uuid() {
  python3 -c 'import uuid; print(uuid.uuid4())'
}

# Next Monday strictly after today, the day after it, and the Monday after that (YYYY-MM-DD).
# python3 keeps the date arithmetic identical on macOS and Linux.
read -r MONDAY TUESDAY RACE_MONDAY <<<"$(python3 -c '
import datetime as dt
today = dt.date.today()
monday = today + dt.timedelta(days=7 - today.weekday())
print(monday, monday + dt.timedelta(days=1), monday + dt.timedelta(days=7))
')"

OUT="$(mktemp -d "${TMPDIR:-/tmp}/scheduler-demo.XXXXXX")"
echo "Responses are written to $OUT"

section() {
  printf '\n== %s ==\n' "$1"
}

# call NAME METHOD PATH [KEY] [BODY]: writes $OUT/NAME.json and $OUT/NAME.status.
call() {
  local name="$1" method="$2" path="$3" key="${4:-}" body="${5:-}"
  local args=(-sS -X "$method" -o "$OUT/$name.json" -w '%{http_code}')
  if [[ -n "$key" ]]; then
    args+=(-H "Idempotency-Key: $key")
  fi
  if [[ -n "$body" ]]; then
    args+=(-H 'Content-Type: application/json' --data "$body")
  fi
  curl "${args[@]}" "$API$path" >"$OUT/$name.status"
  echo "$method $path -> $(cat "$OUT/$name.status")"
}

# expect NAME STATUS [CODE]: stops the demo when the response is not the expected one.
expect() {
  local name="$1" status="$2" code="${3:-}" got got_code
  got="$(cat "$OUT/$name.status")"
  got_code="$(jq -r '.code // empty' "$OUT/$name.json" 2>/dev/null || true)"
  if [[ "$got" != "$status" ]] || [[ -n "$code" && "$got_code" != "$code" ]]; then
    echo "demo.sh: $name expected $status $code, got $got $got_code:" >&2
    cat "$OUT/$name.json" >&2
    exit 1
  fi
}

# booking START_LOCAL VEHICLE_ID VIN CUSTOMER_ID: an Oil change request in the wire format.
# An empty VEHICLE_ID or VIN is sent as null.
booking() {
  jq -cn --arg start "$1" --arg vid "$2" --arg vin "$3" --arg cid "$4" \
    --argjson st "$OIL_CHANGE" '{
      service_type_id: $st,
      start_at: $start,
      customer: {id: $cid, email: null, name: "Demo customer"},
      vehicle: {
        id: (if $vid == "" then null else $vid end),
        vin: (if $vin == "" then null else $vin end),
        make: "VW",
        model: "Golf"
      }
    }'
}

# `docker compose up --wait` returns once the api container runs; the container migrates
# before uvicorn listens, so wait for readiness (up to 60 s) before the first section.
for _ in $(seq 1 60); do
  if curl -fsS -o /dev/null "$API/health/ready" 2>/dev/null; then
    break
  fi
  sleep 1
done

existing="$(psql_value 'SELECT count(*) FROM appointment')"
if [[ "$existing" != "0" ]]; then
  echo "demo.sh: the database already holds $existing appointments;" \
    "run 'make down && make demo' for a clean run" >&2
  exit 1
fi

section "1. Health"
call live GET /health/live
expect live 200
call ready GET /health/ready
expect ready 200
jq -c . "$OUT/live.json" "$OUT/ready.json"

section "2. Book an Oil change, Monday $MONDAY 09:00 Europe/London"
KEY="$(uuid)"
BODY="$(booking "${MONDAY}T09:00:00" "" "WVWZZZ1JZXW000001" "C-42")"
echo "Idempotency-Key: $KEY"
call book POST "/dealerships/$D/appointments" "$KEY" "$BODY"
expect book 201
jq . "$OUT/book.json"

section "3. Replay: same key, same body"
call replay POST "/dealerships/$D/appointments" "$KEY" "$BODY"
expect replay 201
first_id="$(jq -r '.appointment_id' "$OUT/book.json")"
replay_id="$(jq -r '.appointment_id' "$OUT/replay.json")"
if [[ "$first_id" != "$replay_id" ]]; then
  echo "demo.sh: the replay returned appointment $replay_id, not $first_id" >&2
  exit 1
fi
echo "appointment_id $replay_id both times; the stored response is replayed, no second booking"

section "4. Same key, different body (10:00): replay_conflict"
OTHER="$(booking "${MONDAY}T10:00:00" "" "WVWZZZ1JZXW000001" "C-42")"
call conflict POST "/dealerships/$D/appointments" "$KEY" "$OTHER"
expect conflict 422 replay_conflict
jq -c . "$OUT/conflict.json"

section "5. Same car, new key, overlapping 09:30: vehicle_already_booked"
echo "VIN sent as \"wvw zzz1jzxw000001\"; normalised to the same vehicle"
OVERLAP="$(booking "${MONDAY}T09:30:00" "" "wvw zzz1jzxw000001" "C-42")"
call vehicle POST "/dealerships/$D/appointments" "$(uuid)" "$OVERLAP"
expect vehicle 409 vehicle_already_booked
jq -c . "$OUT/vehicle.json"

section "6. Availability, Oil change, Monday $MONDAY (advisory)"
call availability GET \
  "/dealerships/$D/availability?service_type_id=$OIL_CHANGE&from=$MONDAY&to=$TUESDAY"
expect availability 200
jq -r '"as_of \(.as_of)",
  (.windows[] | "bay \(.bay_id) technician \(.technician_id):"
    + " \(.earliest_start) .. \(.latest_start)")' "$OUT/availability.json"

section "7. Race: $RACE_CLIENTS clients, one slot, Monday $RACE_MONDAY 09:00"
echo "2 bays x 2 technicians allow 2 concurrent winners;" \
  "expected 2 x 201 and 6 x 409 capacity_exhausted"
pids=()
for i in $(seq 1 "$RACE_CLIENTS"); do
  body="$(booking "${RACE_MONDAY}T09:00:00" "RACE-$i" "" "RACE-C-$i")"
  key="$(uuid)"
  curl -sS -X POST -o "$OUT/race-$i.json" -w '%{http_code}' \
    -H "Idempotency-Key: $key" -H 'Content-Type: application/json' --data "$body" \
    "$API/dealerships/$D/appointments" >"$OUT/race-$i.status" &
  pids+=("$!")
done
for pid in "${pids[@]}"; do
  wait "$pid"
done
won=0
exhausted=0
for i in $(seq 1 "$RACE_CLIENTS"); do
  status="$(cat "$OUT/race-$i.status")"
  jq -r --arg i "$i" --arg s "$status" \
    '"client \($i): \($s) \(.code // .status)"
      + (if .bay_id then " bay \(.bay_id) technician \(.technician_id)" else "" end)' \
    "$OUT/race-$i.json"
  if [[ "$status" == "201" ]]; then
    won=$((won + 1))
  elif [[ "$status" == "409" && "$(jq -r '.code' "$OUT/race-$i.json")" == "capacity_exhausted" ]]; then
    exhausted=$((exhausted + 1))
  fi
done
echo "observed: $won x 201, $exhausted x 409 capacity_exhausted"
if [[ "$won" != "2" || "$exhausted" != "6" ]]; then
  echo "demo.sh: the race split differs from the expected 2 x 201, 6 x capacity_exhausted" >&2
  exit 1
fi
echo "last $RACE_CLIENTS book_appointment events (docker compose logs api):"
docker compose logs --no-color --no-log-prefix api \
  | jq -cR 'fromjson? | select(type == "object" and .route == "book_appointment")' \
  | tail -n "$RACE_CLIENTS"

section "8. Overlap count (design section 5), must be 0"
overlaps="$(psql_value "$OVERLAP_SQL")"
echo "$overlaps"
[[ "$overlaps" == "0" ]]
