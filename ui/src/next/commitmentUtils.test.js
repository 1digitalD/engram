import { describe, expect, it } from 'vitest';

import {
  commitmentDetailPath,
  isOrphanTaskEntity,
  normalizeTaskOwner,
  taskOwnerId,
  taskOwnerRef,
  taskSpaceId,
} from './commitmentUtils';
import { openCommitmentsFromDetail } from './dossierUtils';

describe('commitmentUtils', () => {
  it('resolves owner from people[] when owner is absent', () => {
    const item = {
      id: 'task-1',
      people: [{ id: 'person-dana', title: 'Dana' }],
    };
    expect(taskOwnerRef(item)).toEqual({ id: 'person-dana', title: 'Dana' });
    expect(taskOwnerId(item)).toBe('person-dana');
    expect(normalizeTaskOwner(item).owner).toEqual({ id: 'person-dana', title: 'Dana' });
  });

  it('prefers explicit owner over people[]', () => {
    const item = {
      id: 'task-1',
      owner: { id: 'person-operator', title: 'Operator' },
      people: [{ id: 'person-dana', title: 'Dana' }],
    };
    expect(taskOwnerId(item)).toBe('person-operator');
  });

  it('detects orphan tasks and builds detail paths', () => {
    const orphan = { id: 'task-orphan', type: 'task', title: 'Loose task' };
    const linked = {
      id: 'task-linked',
      type: 'task',
      projects: [{ id: 'space-apollo', title: 'Apollo' }],
    };
    expect(isOrphanTaskEntity(orphan)).toBe(true);
    expect(isOrphanTaskEntity(linked)).toBe(false);
    expect(taskSpaceId(linked)).toBe('space-apollo');
    expect(commitmentDetailPath('task-orphan')).toBe('/commitments/task-orphan');
  });
});

describe('openCommitmentsFromDetail', () => {
  it('normalizes assignees onto owner for dossier rows', () => {
    const tasks = openCommitmentsFromDetail({
      sections: [
        {
          key: 'open_tasks',
          items: [
            {
              entity: {
                id: 'task-1',
                title: 'Legal read',
                people: [{ id: 'person-dana', title: 'Dana' }],
              },
            },
          ],
        },
      ],
    });

    expect(tasks[0].owner).toEqual({ id: 'person-dana', title: 'Dana' });
  });
});
