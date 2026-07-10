import { describe, expect, it } from 'vitest';

import { buildTaskBoardParams, datePresetParams, defaultOrderForSort, localDateString } from './tasksBoardUtils';

describe('tasksBoardUtils', () => {
  it('builds default open status params', () => {
    expect(
      buildTaskBoardParams({
        statuses: ['open', 'in_progress', 'waiting', 'blocked'],
        assignee: '',
        duePreset: 'any',
        followUpPreset: 'any',
        sort: 'created_at',
        order: 'desc',
      }),
    ).toEqual({
      status: 'open,in_progress,waiting,blocked',
      sort: 'created_at',
      order: 'desc',
    });
  });

  it('maps overdue due preset to yesterday in local time', () => {
    const params = datePresetParams('overdue', 'due');
    expect(params.due_before).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(params.due_after).toBeUndefined();
  });

  it('formats local calendar dates without UTC drift', () => {
    const date = new Date(2026, 6, 10, 23, 30, 0);
    expect(localDateString(date)).toBe('2026-07-10');
  });

  it('defaults follow-up sort to ascending', () => {
    expect(defaultOrderForSort('follow_up_at')).toBe('asc');
    expect(defaultOrderForSort('created_at')).toBe('desc');
  });
});
