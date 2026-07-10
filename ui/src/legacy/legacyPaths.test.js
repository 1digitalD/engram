import { afterEach, describe, expect, it } from 'vitest';

import { appPath, legacyPath, setAppPathPrefix } from './legacyPaths';

describe('legacyPaths', () => {
  afterEach(() => {
    setAppPathPrefix('');
  });

  it('returns root paths by default for v6', () => {
    expect(legacyPath('/projects/p1')).toBe('/projects/p1');
    expect(appPath('/tasks/t1')).toBe('/tasks/t1');
  });

  it('prefixes paths inside the legacy shell', () => {
    setAppPathPrefix('/legacy');
    expect(legacyPath('/projects/p1')).toBe('/legacy/projects/p1');
    expect(legacyPath('/legacy/now')).toBe('/legacy/now');
  });
});
