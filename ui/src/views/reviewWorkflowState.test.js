import { describe, it, expect } from 'vitest';
import { mergeReviewWorkflowPersisted } from './reviewWorkflowState';

describe('mergeReviewWorkflowPersisted', () => {
  it('applies known expanded and completed flags', () => {
    const m = mergeReviewWorkflowPersisted({
      expanded: { projects: true },
      completed: { inbox: true },
      lastActiveStepId: 'areas',
    });
    expect(m.expanded.projects).toBe(true);
    expect(m.completed.inbox).toBe(true);
    expect(m.lastActiveStepId).toBe('areas');
  });
});
