-- Slice prd-decisions: first-class decision records.
-- Additive only: new decisions table + new event_type enum value.
-- Idempotent.

CREATE TABLE IF NOT EXISTS decisions (
    id             TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    thread_id      TEXT NOT NULL REFERENCES entities (id) ON DELETE CASCADE,
    statement      TEXT NOT NULL,
    context        TEXT,
    decided_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_by     TEXT NOT NULL,
    source_note_id TEXT REFERENCES entities (id) ON DELETE SET NULL,
    superseded_by  TEXT REFERENCES decisions (id) ON DELETE SET NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS decisions_thread_idx      ON decisions (thread_id, decided_at DESC);
CREATE INDEX IF NOT EXISTS decisions_source_note_idx ON decisions (source_note_id);
CREATE INDEX IF NOT EXISTS decisions_superseded_idx  ON decisions (superseded_by);

ALTER TABLE entity_events DROP CONSTRAINT IF EXISTS entity_events_event_type_check;
ALTER TABLE entity_events ADD CONSTRAINT entity_events_event_type_check
  CHECK (event_type IN (
    'created', 'updated', 'status_changed', 'archived', 'deleted',
    'relationship_added', 'relationship_updated', 'relationship_removed',
    'tag_added', 'tag_removed', 'ai_processed', 'ai_updated', 'ai_summarized',
    'suggestion_accepted', 'suggestion_dismissed', 'suggestion_expired',
    'review_marked_resolved', 'activity_update_added', 'reverted',
    'merged', 'merged_into', 'type_converted', 'decision_recorded'
  ));

CREATE OR REPLACE TRIGGER decisions_updated_at
    BEFORE UPDATE ON decisions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
