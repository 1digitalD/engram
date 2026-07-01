-- Timeline index: supports chronological event stream queries ordered by event time.
-- `occurred_at` in the API maps to entity_events.created_at.
CREATE INDEX IF NOT EXISTS entity_events_occurred_at_idx
    ON entity_events (created_at DESC);
