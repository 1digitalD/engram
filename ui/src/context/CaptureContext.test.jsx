import { describe, expect, it } from 'vitest';
import { threadFromPathname } from './CaptureContext';

describe('threadFromPathname', () => {
  it('detects thread context from entity detail routes', () => {
    expect(threadFromPathname('/projects/p1')).toEqual({
      id: 'p1',
      type: 'project',
      routeType: 'projects',
    });
    expect(threadFromPathname('/people/mary')).toEqual({
      id: 'mary',
      type: 'person',
      routeType: 'people',
    });
  });

  it('returns null for non-thread routes', () => {
    expect(threadFromPathname('/')).toBeNull();
    expect(threadFromPathname('/inbox')).toBeNull();
    expect(threadFromPathname('/today')).toBeNull();
  });
});
