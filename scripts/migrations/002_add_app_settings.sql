-- Slice C1: delegation detection + cadence.
-- Additive only: new app_settings key/value table.
-- Idempotent.

CREATE TABLE IF NOT EXISTS app_settings (
    key        TEXT PRIMARY KEY,
    value      JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
