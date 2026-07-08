-- Slice v6-40: follow-up markers for explicit nudge/discuss follow-ups.
-- Additive only. Idempotent.

CREATE TABLE IF NOT EXISTS followup_markers (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('nudge', 'discuss', 'custom')),
  due_at TIMESTAMP,
  person_entity_id TEXT REFERENCES entities(id) ON DELETE SET NULL,
  note TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  fired_at TIMESTAMP,
  resolved_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_followup_markers_entity_id
  ON followup_markers(entity_id);

CREATE INDEX IF NOT EXISTS idx_followup_markers_due_pending
  ON followup_markers(due_at)
  WHERE fired_at IS NULL AND resolved_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_followup_markers_person_discuss
  ON followup_markers(person_entity_id)
  WHERE kind = 'discuss' AND resolved_at IS NULL;
