
CREATE TABLE IF NOT EXISTS plants (
    id                    SERIAL PRIMARY KEY,
    name                  TEXT NOT NULL,
    plant_type            TEXT,
    threshold_dry         INTEGER NOT NULL DEFAULT 47000,
    threshold_getting_dry INTEGER NOT NULL DEFAULT 40000,
    threshold_too_wet     INTEGER NOT NULL DEFAULT 32000,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

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
