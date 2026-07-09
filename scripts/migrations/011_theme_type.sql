-- Additive only: extend entity type and event type constraints for themes.

ALTER TABLE entities DROP CONSTRAINT IF EXISTS entities_type_check;
ALTER TABLE entities ADD CONSTRAINT entities_type_check
CHECK (
    type IN (
        'note',
        'task',
        'project',
        'theme',
        'area',
        'resource',
        'person'
    )
);

ALTER TABLE entity_events DROP CONSTRAINT IF EXISTS entity_events_event_type_check;
ALTER TABLE entity_events ADD CONSTRAINT entity_events_event_type_check
CHECK (
    event_type IN (
        'created',
        'updated',
        'status_changed',
        'archived',
        'deleted',
        'relationship_added',
        'relationship_updated',
        'relationship_removed',
        'tag_added',
        'tag_removed',
        'ai_processed',
        'ai_updated',
        'ai_summarized',
        'suggestion_accepted',
        'suggestion_dismissed',
        'suggestion_expired',
        'review_marked_resolved',
        'activity_update_added',
        'reverted',
        'merged',
        'merged_into',
        'type_converted',
        'promoted',
        'decision_recorded'
    )
);
