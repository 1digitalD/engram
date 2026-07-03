import { describe, expect, it } from 'vitest';
import { dueUrgencyClass, statusPillVariant } from './entityRowChrome';

describe('entityRowChrome', () => {
  it('maps status to semantic pill variants', () => {
    expect(statusPillVariant('blocked')).toBe('blocked');
    expect(statusPillVariant('waiting')).toBe('waiting');
    expect(statusPillVariant('done')).toBe('done');
    expect(statusPillVariant('in_progress')).toBe('active');
    expect(statusPillVariant('open')).toBe('neutral');
  });

  it('detects due-date urgency bands', () => {
    const today = new Date();
    today.setHours(12, 0, 0, 0);
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    expect(dueUrgencyClass({
      type: 'task',
      due_at: yesterday.toISOString(),
    })).toBe('dueOverdue');

    expect(dueUrgencyClass({
      type: 'task',
      due_at: today.toISOString(),
    })).toBe('dueToday');

    expect(dueUrgencyClass({
      type: 'task',
      due_at: tomorrow.toISOString(),
    })).toBe('');
  });
});
