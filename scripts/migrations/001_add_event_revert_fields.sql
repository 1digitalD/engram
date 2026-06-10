-- Slice B3: capture changelog + one-click undo.
-- Additive only: new nullable columns + new event_type enum value + index.
-- Idempotent.

ALTER TABLE entity_events
    ADD COLUMN IF NOT EXISTS source_note_id TEXT REFERENCES entities (id) ON DELETE SET NULL;

ALTER TABLE entity_events
    ADD COLUMN IF NOT EXISTS reverted_at TIMESTAMPTZ;

ALTER TABLE entity_events DROP CONSTRAINT IF EXISTS entity_events_event_type_check;
ALTER TABLE entity_events ADD CONSTRAINT entity_events_event_type_check
  CHECK (event_type IN (
    'created', 'updated', 'status_changed', 'archived', 'deleted',
    'relationship_added', 'relationship_updated', 'relationship_removed',
    'tag_added', 'tag_removed', 'ai_processed', 'ai_updated', 'ai_summarized',
    'suggestion_accepted', 'suggestion_dismissed', 'suggestion_expired',
    'review_marked_resolved', 'activity_update_added', 'reverted'
  ));

CREATE INDEX IF NOT EXISTS entity_events_source_note_idx
    ON entity_events (source_note_id, created_at ASC)
    WHERE source_note_id IS NOT NULL;
