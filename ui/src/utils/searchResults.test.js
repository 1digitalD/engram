import { describe, expect, it } from 'vitest';
import { normalizeSearchResults } from './searchResults';

describe('normalizeSearchResults', () => {
  it('unwraps v4 search results into entity rows with snippet metadata', () => {
    const rows = normalizeSearchResults({
      query: 'memory',
      mode: 'keyword',
      results: [
        {
          entity: { id: 't1', type: 'task', title: 'Ship rollout', status: 'open' },
          score: 12,
          match: { source: 'keyword', snippet: 'Memory rollout checklist' },
        },
        {
          entity: { id: 'p1', type: 'project', title: 'Agent Memory' },
          score: 8,
          match: { source: 'hybrid', snippet: 'Platform memory work' },
        },
      ],
    });

    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({
      id: 't1',
      type: 'task',
      title: 'Ship rollout',
      searchSnippet: 'Memory rollout checklist',
      searchSource: 'keyword',
    });
    expect(rows[1].searchSnippet).toBe('Platform memory work');
  });

  it('returns legacy data arrays unchanged', () => {
    const legacy = [{ id: 'n1', type: 'note', title: 'Legacy row' }];
    expect(normalizeSearchResults({ data: legacy })).toEqual(legacy);
  });

  it('returns an empty array for missing or malformed payloads', () => {
    expect(normalizeSearchResults(null)).toEqual([]);
    expect(normalizeSearchResults({})).toEqual([]);
    expect(normalizeSearchResults({ results: [{ score: 1 }] })).toEqual([]);
  });
});
