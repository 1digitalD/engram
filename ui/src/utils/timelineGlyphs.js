const VALID_GLYPH_TYPES = new Set([
  'note', 'task', 'project', 'area', 'person', 'resource', 'decision', 'ai',
]);

export function timelineGlyphType(event, { defaultEntityType } = {}) {
  if (!event) return defaultEntityType || 'note';
  if (event.actor?.startsWith('agent:')) return 'ai';
  if (event.event_type === 'activity_update_added') return 'note';
  if (event.event_type?.includes('decision')) return 'decision';
  if (event.entity_type && VALID_GLYPH_TYPES.has(event.entity_type)) {
    return event.entity_type;
  }
  if (event.event_type === 'created' && defaultEntityType) return defaultEntityType;
  return defaultEntityType || 'note';
}
