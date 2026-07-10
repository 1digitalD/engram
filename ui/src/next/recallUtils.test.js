import { describe, expect, it } from 'vitest';

import { groupRecallResults, recallEntityPath } from './recallUtils';

describe('recallUtils', () => {
  it('maps entities to v6 routes', () => {
    expect(recallEntityPath({ id: 'p1', type: 'person' })).toBe('/people/p1');
    expect(recallEntityPath({ id: 's1', type: 'project' })).toBe('/spaces/s1');
    expect(
      recallEntityPath({ id: 't1', type: 'task', projects: [{ id: 's1' }] }),
    ).toBe('/commitments/t1');
    expect(recallEntityPath({ id: 'n1', type: 'note' })).toBe('/notes/n1');
  });

  it('groups project and area results under Spaces', () => {
    const groups = groupRecallResults([
      { id: '1', type: 'project', title: 'Apollo' },
      { id: '2', type: 'area', title: 'Ops' },
      { id: '3', type: 'person', title: 'Sam' },
    ]);
    expect(groups.map((group) => group.label)).toEqual(['Spaces', 'People']);
    expect(groups[0].items).toHaveLength(2);
  });
});
