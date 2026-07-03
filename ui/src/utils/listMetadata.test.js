import { describe, expect, it } from 'vitest';
import {
  formatLinkedCountsSummary,
  formatProjectOpenBadge,
  listRowSecondaryMeta,
} from './listMetadata';

describe('listMetadata', () => {
  it('formats project open task badge', () => {
    expect(formatProjectOpenBadge({ open: 3, total: 5 })).toBe('3 open');
    expect(formatProjectOpenBadge({ open: 0, total: 2 })).toBeNull();
  });

  it('formats linked count summary for areas and people', () => {
    expect(formatLinkedCountsSummary({ tasks: 3, projects: 2, notes: 1 })).toBe(
      '3 tasks · 2 projects · 1 note',
    );
    expect(formatLinkedCountsSummary({ tasks: 1, projects: 0, notes: 0 })).toBe('1 task');
    expect(formatLinkedCountsSummary({})).toBeNull();
  });

  it('picks the right secondary meta by list type', () => {
    expect(listRowSecondaryMeta({ task_counts: { open: 2, total: 4 } }, 'project')).toBe('2 open');
    expect(listRowSecondaryMeta({
      linked_counts: { tasks: 2, projects: 1, notes: 0 },
    }, 'area')).toBe('2 tasks · 1 project');
    expect(listRowSecondaryMeta({ status: 'open' }, 'task')).toBeNull();
  });
});
