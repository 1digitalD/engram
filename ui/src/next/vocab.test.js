import { describe, expect, it } from 'vitest';
import {
  ACTION_LABELS,
  ENTITY_TYPE_GLYPHS,
  ENTITY_TYPE_LABELS,
  SECTION_LABELS,
  entityTypeLabel,
  itemTitle,
  proposalLabel,
  sectionLabel,
} from './vocab';

describe('vocab', () => {
  it('maps v4 entity types vision labels', () => {
    expect(entityTypeLabel('note')).toBe(ENTITY_TYPE_LABELS.note);
    expect(entityTypeLabel('project')).toBe(ENTITY_TYPE_LABELS.project);
    expect(entityTypeLabel('task')).toBe(ENTITY_TYPE_LABELS.task);
    expect(ENTITY_TYPE_GLYPHS.note).toBe('N');
    expect(ENTITY_TYPE_GLYPHS.task).toBe('C');
  });

  it('maps report section keys vision labels', () => {
    expect(sectionLabel('proposed_commitments')).toBe(SECTION_LABELS.proposed_commitments);
    expect(sectionLabel('questions')).toBe(SECTION_LABELS.questions);
  });

  it('labels proposals using vision vocabulary', () => {
    expect(proposalLabel({ suggestion_type: 'create_task', payload: { type: 'task' } }))
      .toBe('New commitment');
    expect(proposalLabel({ operation_type: 'create_decision' })).toBe('Decision proposal');
  });

  it('derives item titles from payload and question fields', () => {
    expect(itemTitle({ title: 'Direct title' })).toBe('Direct title');
    expect(itemTitle({ question: 'Who owns this?' })).toBe('Who owns this?');
    expect(itemTitle({ payload: { title: 'From payload' } })).toBe('From payload');
  });

  it('uses verify as the primary accept action label', () => {
    expect(ACTION_LABELS.verify).toBe('Verify');
    expect(ACTION_LABELS.acceptRest).toBe('Accept remainder');
  });
});
