import { describe, expect, it, vi } from 'vitest';
import { fetchReviewQueueReports, mergeReviewReports, REVIEW_QUEUE_LIMIT, reportQueueTitle, reportStatusLabel, citationEntityPath } from './reviewUtils';

describe('fetchReviewQueueReports', () => {
  it('merges pending and partial lists with the review queue limit', async () => {
    const reportsApi = {
      list: vi.fn(async (params) => {
        if (params.status === 'pending') {
          return {
            data: [{ id: 'r1', status: 'pending', created_at: '2026-07-09T10:00:00Z' }],
            meta: { total: 1 },
          };
        }
        return {
          data: [{ id: 'r2', status: 'partial', created_at: '2026-07-09T09:00:00Z' }],
          meta: { total: 1 },
        };
      }),
    };

    const { rows, total } = await fetchReviewQueueReports(reportsApi);

    expect(reportsApi.list).toHaveBeenCalledWith({ status: 'pending', limit: REVIEW_QUEUE_LIMIT });
    expect(reportsApi.list).toHaveBeenCalledWith({ status: 'partial', limit: REVIEW_QUEUE_LIMIT });
    expect(rows.map((row) => row.id)).toEqual(['r1', 'r2']);
    expect(total).toBe(2);
  });

  it('returns partial results when one list request fails', async () => {
    const reportsApi = {
      list: vi.fn(async (params) => {
        if (params.status === 'pending') {
          throw new Error('network down');
        }
        return { data: [{ id: 'r2', status: 'partial' }], meta: { total: 3 } };
      }),
    };

    const { rows, total } = await fetchReviewQueueReports(reportsApi);
    expect(rows).toEqual([{ id: 'r2', status: 'partial' }]);
    expect(total).toBe(3);
  });

  it('throws when both list requests fail', async () => {
    const reportsApi = {
      list: vi.fn(async () => {
        throw new Error('network down');
      }),
    };

    await expect(fetchReviewQueueReports(reportsApi)).rejects.toThrow('network down');
  });

  it('uses meta.total for pulse counts beyond the fetched page', async () => {
    const reportsApi = {
      list: vi.fn(async (params) => {
        if (params.status === 'pending') {
          return { data: [{ id: 'r1', status: 'pending' }], meta: { total: 250 } };
        }
        return { data: [{ id: 'r2', status: 'partial' }], meta: { total: 40 } };
      }),
    };

    const { rows, total } = await fetchReviewQueueReports(reportsApi);
    expect(rows).toHaveLength(2);
    expect(total).toBe(290);
  });
});

describe('report helpers', () => {
  it('labels queue rows with note titles and pending counts', () => {
    expect(reportQueueTitle({ source_note_title: 'My capture', id: 'abc' })).toBe('My capture');
    expect(reportStatusLabel({ pending_suggestion_count: 0, status: 'pending' })).toBe('Applied only');
    expect(reportStatusLabel({ pending_suggestion_count: 2, status: 'pending' })).toBe('2 proposals');
    expect(citationEntityPath({ entity_id: 'p1', entity_type: 'person', meta: 'Person' })).toBe('/people/p1');
    expect(citationEntityPath({ entity_id: 'project-1', meta: 'Space • 2 open tasks' })).toBe('/spaces/project-1');
  });
});

describe('mergeReviewReports', () => {
  it('dedupes the same report id across lists', () => {
    const rows = mergeReviewReports(
      [{ id: 'r1', status: 'pending' }],
      [{ id: 'r1', status: 'partial' }],
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].status).toBe('partial');
  });
});
