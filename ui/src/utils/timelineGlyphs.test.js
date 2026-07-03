import { describe, expect, it } from 'vitest';
import { timelineGlyphType } from './timelineGlyphs';

describe('timelineGlyphType', () => {
  it('maps agent, update, and decision events to semantic glyph types', () => {
    expect(timelineGlyphType({
      actor: 'agent:v4-extraction',
      event_type: 'ai_updated',
    })).toBe('ai');

    expect(timelineGlyphType({
      event_type: 'activity_update_added',
      actor: 'user',
    })).toBe('note');

    expect(timelineGlyphType({
      event_type: 'decision_recorded',
      actor: 'user',
    })).toBe('decision');
  });

  it('prefers entity_type when present', () => {
    expect(timelineGlyphType({
      entity_type: 'task',
      event_type: 'status_changed',
      actor: 'user',
    })).toBe('task');
  });

  it('uses default entity type for created events without entity_type', () => {
    expect(timelineGlyphType({
      event_type: 'created',
      actor: 'user',
    }, { defaultEntityType: 'project' })).toBe('project');
  });
});
