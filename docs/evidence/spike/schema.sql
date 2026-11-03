-- Spike: prove that two concurrent bookings for the same bay cannot both commit.
CREATE EXTENSION IF NOT EXISTS btree_gist;

DROP TABLE IF EXISTS appointment;
CREATE TABLE appointment (
    id            serial PRIMARY KEY,
    dealership_id int  NOT NULL,
    bay_id        int  NOT NULL,
    technician_id int  NOT NULL,
    start_at      timestamptz NOT NULL,
    end_at        timestamptz NOT NULL,
    label         text NOT NULL,
    CHECK (end_at > start_at),
    -- One bay cannot be booked twice for overlapping time ranges.
    CONSTRAINT no_bay_overlap
        EXCLUDE USING gist (bay_id WITH =, tstzrange(start_at, end_at) WITH &&),
    -- One technician cannot be booked twice for overlapping time ranges.
    CONSTRAINT no_technician_overlap
        EXCLUDE USING gist (technician_id WITH =, tstzrange(start_at, end_at) WITH &&)
);
