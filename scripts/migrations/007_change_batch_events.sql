-- Slice v6-11: link entity_events to change_batches for batch undo.
-- Additive only: nullable FK + index.
-- Idempotent.

ALTER TABLE entity_events
    ADD COLUMN IF NOT EXISTS change_batch_id TEXT REFERENCES change_batches (id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS entity_events_change_batch_idx
    ON entity_events (change_batch_id)
    WHERE change_batch_id IS NOT NULL;
