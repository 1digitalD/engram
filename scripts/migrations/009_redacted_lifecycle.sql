-- Slice v6-32: redacted lifecycle for note redaction + redacted event type.
-- Additive only: extend lifecycle check + entity_events event_type enum.
-- Idempotent.

ALTER TABLE entities DROP CONSTRAINT IF EXISTS chk_entities_lifecycle;
ALTER TABLE entities DROP CONSTRAINT IF EXISTS entities_lifecycle_check;
ALTER TABLE entities ADD CONSTRAINT chk_entities_lifecycle
  CHECK (lifecycle IN ('active', 'archived', 'deleted', 'redacted'));

ALTER TABLE entity_events DROP CONSTRAINT IF EXISTS entity_events_event_type_check;
ALTER TABLE entity_events ADD CONSTRAINT entity_events_event_type_check
  CHECK (event_type IN (
    'created', 'updated', 'status_changed', 'archived', 'deleted', 'redacted',
    'relationship_added', 'relationship_updated', 'relationship_removed',
    'tag_added', 'tag_removed', 'ai_processed', 'ai_updated', 'ai_summarized',
    'suggestion_accepted', 'suggestion_dismissed', 'suggestion_expired',
    'review_marked_resolved', 'activity_update_added', 'reverted',
    'merged', 'merged_into', 'type_converted', 'decision_recorded'
  ));
