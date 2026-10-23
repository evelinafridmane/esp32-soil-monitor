-- Soil Monitor database schema.
-- Reconstructed from app.py queries + CLAUDE.md notes (the original schema was
-- built by hand in DBeaver and never checked in). Safe to re-run: all
-- statements use IF NOT EXISTS.
--
-- Rebuild a fresh database with:
--   createdb soil_monitor
--   psql soil_monitor -f schema.sql
--   psql soil_monitor -f seed.sql   # optional sample data

-- Per-pot plants. plant_type is free text (may be NULL, may reference a
-- plant_types row by name, or may be a brand-new type not yet in plant_types).
CREATE TABLE IF NOT EXISTS plants (
    id                    SERIAL PRIMARY KEY,
    name                  TEXT NOT NULL,
    plant_type            TEXT,
    threshold_dry         INTEGER NOT NULL DEFAULT 47000,
    threshold_getting_dry INTEGER NOT NULL DEFAULT 40000,
    threshold_too_wet     INTEGER NOT NULL DEFAULT 32000,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Per-type care info (shared across all pots of the same type). Name is the
-- key the plants table joins to. Rows are auto-created by the Groq background
-- task when a new plant_type first appears.
CREATE TABLE IF NOT EXISTS plant_types (
    name            TEXT PRIMARY KEY,
    description     TEXT NOT NULL DEFAULT '',
    watering_habits TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Raw moisture readings POSTed by the chip. Higher = drier (capacitive).
CREATE TABLE IF NOT EXISTS readings (
    id           SERIAL PRIMARY KEY,
    plant_id     INTEGER NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    moisture_raw INTEGER NOT NULL,
    recorded_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_readings_plant_recorded
    ON readings (plant_id, recorded_at DESC);

-- Manual "I just watered" log entries.
CREATE TABLE IF NOT EXISTS waterings (
    id         SERIAL PRIMARY KEY,
    plant_id   INTEGER NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
    watered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes      TEXT
);
CREATE INDEX IF NOT EXISTS idx_waterings_plant_watered
    ON waterings (plant_id, watered_at DESC);
