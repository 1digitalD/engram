import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import NextShell from './NextShell';
import ReviewSurface from './ReviewSurface';

vi.mock('../api/v4Client', () => ({
  v4API: {
    reports: {
      list: vi.fn(),
      get: vi.fn(),
      resolve: vi.fn(),
      undo: vi.fn(),
      markDone: vi.fn(),
    },
    events: {
      revert: vi.fn(),
    },
    entities: {
      create: vi.fn(),
      createLink: vi.fn(),
    },
    metrics: {
      recordReview: vi.fn(),
    },
    summary: vi.fn(),
    brief: vi.fn(),
    capture: vi.fn(),
    search: vi.fn(),
    agentActivity: vi.fn().mockResolvedValue({ data: [], meta: { total: 0, counts: {} } }),
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

import { v4API } from '../api/v4Client';

const REPORT_ID = 'report-1';
const REPORT_ID_2 = 'report-2';
const SUGGESTION_ID = 'suggestion-1';
const SUGGESTION_ID_2 = 'suggestion-2';

const LIST_PAYLOAD = {
  data: [{
    id: REPORT_ID,
    status: 'pending',
    source_note_id: 'note-1',
    source_note_title: 'Standup note',
    pending_suggestion_count: 1,
  }],
  meta: { total: 1 },
};

const LIST_PAYLOAD_TWO_REPORTS = {
  data: [
    { id: REPORT_ID, status: 'pending', source_note_id: 'note-1' },
    { id: REPORT_ID_2, status: 'pending', source_note_id: 'note-2' },
  ],
  meta: { total: 2 },
};

const DETAIL_PAYLOAD = {
  data: {
    id: REPORT_ID,
    status: 'pending',
    narrative: {
      sections: [
        {
          name: 'proposed_commitments',
          title: 'Proposed commitments',
          items: [
            {
              id: SUGGESTION_ID,
              kind: 'create_entity',
              title: 'Write docs',
              reason: 'Write docs tomorrow',
              payload: { title: 'Write docs', evidence: 'Write docs tomorrow' },
            },
          ],
        },
        {
          name: 'applied_annotations',
          title: 'Applied annotations',
          items: [
            {
              id: 'event-1',
              event_id: 'event-1',
              kind: 'tag_added',
              title: 'Tag added: meeting',
            },
          ],
        },
      ],
    },
  },
  source_note: { id: 'note-1', title: 'Standup note' },
  suggestions: [
    {
      id: SUGGESTION_ID,
      status: 'pending',
      suggestion_type: 'create_task',
      operation_type: 'create_entity',
      payload: { type: 'task', title: 'Write docs', evidence: 'Write docs tomorrow' },
    },
  ],
};

const DETAIL_PAYLOAD_2 = {
  data: {
    id: REPORT_ID_2,
    status: 'pending',
    narrative: {
      sections: [
        {
          name: 'proposed_commitments',
          title: 'Proposed commitments',
          items: [
            {
              id: SUGGESTION_ID_2,
              kind: 'create_entity',
              title: 'Send recap',
              reason: 'Send recap today',
              payload: { title: 'Send recap', evidence: 'Send recap today' },
            },
          ],
        },
      ],
    },
  },
  source_note: { id: 'note-2', title: 'Recap note' },
  suggestions: [
    {
      id: SUGGESTION_ID_2,
      status: 'pending',
      suggestion_type: 'create_task',
      operation_type: 'create_entity',
      payload: { type: 'task', title: 'Send recap', evidence: 'Send recap today' },
    },
  ],
};

const SUMMARY_PAYLOAD = {
  inbox_count: 2,
  today_count: 5,
  suggestions_count: 1,
  last_reviewed_at: '2026-07-08T10:00:00Z',
  reviewed_today: true,
  stale_projects_count: 1,
  new_since_yesterday_count: 3,
  coordination_radar: {
    people: [
      {
        entity_id: 'person-1',
        title: 'Maria',
        headline: 'Watch 1:1 drift and 1 blocked task.',
        counts: { stuck_tasks: 1, overdue_follow_ups: 1 },
      },
    ],
    projects: [
      {
        entity_id: 'project-1',
        title: 'Apollo',
        headline: 'Apollo has 2 overdue commitments.',
        counts: { overdue_tasks: 2, quiet_tasks: 1, open_tasks: 5 },
      },
    ],
  },
};

const BRIEF_PAYLOAD = {
  brief: {
    narrative: 'Two threads need explicit decisions before Friday.',
    generated_at: '2026-07-08T10:00:00Z',
    items: [
      {
        entity_id: 'task-1',
        entity_type: 'task',
        title: 'Send deck',
        why_now: 'Due Friday and still unstarted.',
        urgency: 5,
      },
      {
        entity_id: 'project-1',
        entity_type: 'project',
        title: 'Apollo',
        why_now: 'Pricing decision is still open.',
        urgency: 4,
      },
    ],
  },
  from_cache: true,
};

function renderReview(initialEntry = '/review') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/review" element={<ReviewSurface />} />
      </Routes>
    </MemoryRouter>,
  );
}

function mockReviewQueueList(rows = LIST_PAYLOAD.data) {
  v4API.reports.list.mockImplementation(async (params = {}) => {
    const status = params.status || 'pending';
    const filtered = rows.filter((row) => row.status === status);
    return { data: filtered, meta: { total: filtered.length } };
  });
}

describe('ReviewSurface', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(Date, 'now').mockReturnValue(1_000);

    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });

    mockReviewQueueList();
    v4API.reports.get.mockResolvedValue(DETAIL_PAYLOAD);
    v4API.reports.resolve.mockResolvedValue({ data: { status: 'reviewed' } });
    v4API.reports.undo.mockResolvedValue({ data: { status: 'pending' } });
    v4API.reports.markDone.mockImplementation(async (id) =>
      v4API.reports.resolve(id, { decisions: [], accept_rest: false }),
    );
    v4API.events.revert.mockResolvedValue({ data: {} });
    v4API.metrics.recordReview.mockResolvedValue({ data: {} });
    v4API.summary.mockResolvedValue(SUMMARY_PAYLOAD);
    v4API.brief.mockResolvedValue(BRIEF_PAYLOAD);
    v4API.capture.mockResolvedValue({});
    v4API.search.mockResolvedValue({ data: [] });
  });

  afterEach(async () => {
    await waitFor(() => {
      const pending = [
        ...v4API.reports.list.mock.results,
        ...v4API.reports.get.mock.results,
        ...v4API.reports.resolve.mock.results,
      ].some((result) => result.type === 'pending');
      expect(pending).toBe(false);
    }).catch(() => {});
    vi.restoreAllMocks();
  });

  it('loads pending reports via GET /reports', async () => {
    renderReview();

    expect(await screen.findByRole('heading', { name: 'Review' })).toBeInTheDocument();
    expect(v4API.reports.list).toHaveBeenCalledWith({ status: 'pending', limit: 200 });
    expect(v4API.reports.list).toHaveBeenCalledWith({ status: 'partial', limit: 200 });
    expect(v4API.summary).not.toHaveBeenCalled();

    await waitFor(() => expect(v4API.reports.get).toHaveBeenCalledWith(REPORT_ID));
    expect(await screen.findByText('Write docs')).toBeInTheDocument();
    expect(screen.getByText('Proposed commitments')).toBeInTheDocument();
  });

  it('renders a weekly digest with citations on the digest tab', async () => {
    renderReview();

    fireEvent.click(await screen.findByRole('tab', { name: 'Weekly digest' }));
    expect(await screen.findByRole('region', { name: 'Weekly digest' })).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByLabelText('Weekly digest draft').value).toContain('Moved'),
    );
    expect(screen.getByText('Watch 1:1 drift and 1 blocked task.')).toBeInTheDocument();
  });

  it('allows editing and copying the weekly digest draft', async () => {
    renderReview();

    fireEvent.click(await screen.findByRole('tab', { name: 'Weekly digest' }));
    const draft = await screen.findByLabelText('Weekly digest draft');
    fireEvent.change(draft, { target: { value: 'Custom weekly update' } });
    fireEvent.click(screen.getByRole('button', { name: 'Copy digest' }));

    await waitFor(() =>
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('Custom weekly update'),
    );
    expect(screen.getByText('Digest copied.')).toBeInTheDocument();
  });

  it('verifies proposal via POST /reports/<id>/resolve', async () => {
    renderReview();

    await screen.findByText('Write docs');
    fireEvent.click(screen.getByRole('button', { name: 'Verify' }));

    await waitFor(() =>
      expect(v4API.reports.resolve).toHaveBeenCalledWith(REPORT_ID, {
        decisions: [{ suggestion_id: SUGGESTION_ID, action: 'accept' }],
      }),
    );
  });

  it('dismisses proposal with a reason', async () => {
    renderReview();

    await screen.findByText('Write docs');
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    fireEvent.click(await screen.findByRole('button', { name: 'not mine' }));

    await waitFor(() =>
      expect(v4API.reports.resolve).toHaveBeenCalledWith(REPORT_ID, {
        decisions: [
          {
            suggestion_id: SUGGESTION_ID,
            action: 'dismiss',
            dismissal_reason: 'not mine',
          },
        ],
      }),
    );
  });

  it('edits proposal title before verifying', async () => {
    renderReview();

    await screen.findByText('Write docs');
    fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
    fireEvent.change(screen.getByLabelText('Title'), {
      target: { value: 'Write documentation' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Verify with edits' }));

    await waitFor(() =>
      expect(v4API.reports.resolve).toHaveBeenCalledWith(REPORT_ID, {
        decisions: [
          {
            suggestion_id: SUGGESTION_ID,
            action: 'edit',
            edits: { title: 'Write documentation', type: 'task' },
          },
        ],
      }),
    );
  });

  it('marks suggestion later', async () => {
    renderReview();

    await screen.findByText('Write docs');
    fireEvent.click(screen.getByRole('button', { name: 'Later' }));

    await waitFor(() =>
      expect(v4API.reports.resolve).toHaveBeenCalledWith(REPORT_ID, {
        decisions: [{ suggestion_id: SUGGESTION_ID, action: 'later' }],
      }),
    );
  });

  it('sends review duration when a report leaves the queue', async () => {
    let reportStillPending = true;
    mockReviewQueueList(
      reportStillPending ? LIST_PAYLOAD.data : [],
    );
    v4API.reports.list.mockImplementation(async (params = {}) => {
      if (!reportStillPending) return { data: [], meta: { total: 0 } };
      const status = params.status || 'pending';
      const filtered = LIST_PAYLOAD.data.filter((row) => row.status === status);
      return { data: filtered, meta: { total: filtered.length } };
    });
    v4API.reports.resolve.mockImplementation(async () => {
      reportStillPending = false;
      return { data: { status: 'reviewed' } };
    });

    renderReview();

    await screen.findByText('Write docs');
    await waitFor(() => expect(v4API.reports.get).toHaveBeenCalledWith(REPORT_ID));
    vi.spyOn(Date, 'now').mockReturnValue(46_000);
    fireEvent.click(screen.getByRole('button', { name: 'Verify' }));

    await waitFor(() =>
      expect(v4API.metrics.recordReview).toHaveBeenCalledWith({
        report_id: REPORT_ID,
        duration_ms: 45_000,
        suggestion_count: 1,
      }),
    );
  });

  it('resets review timing when switching to another report', async () => {
    let pendingReports = [...LIST_PAYLOAD_TWO_REPORTS.data];

    mockReviewQueueList(pendingReports);
    v4API.reports.list.mockImplementation(async (params = {}) => {
      const status = params.status || 'pending';
      const filtered = pendingReports.filter((row) => row.status === status);
      return { data: filtered, meta: { total: filtered.length } };
    });
    v4API.reports.get.mockImplementation(async (reportId) =>
      reportId === REPORT_ID_2 ? DETAIL_PAYLOAD_2 : DETAIL_PAYLOAD,
    );
    v4API.reports.resolve.mockImplementation(async (reportId) => {
      pendingReports = pendingReports.filter((row) => row.id !== reportId);
      return { data: { status: 'reviewed' } };
    });

    let now = 1_000;
    vi.spyOn(Date, 'now').mockImplementation(() => now);

    renderReview();

    await screen.findByText('Write docs');
    now = 5_000;
    fireEvent.click(screen.getByRole('button', { name: /report-2/i }));
    expect(await screen.findByText('Send recap')).toBeInTheDocument();
    expect(v4API.reports.get).toHaveBeenCalledWith(REPORT_ID_2);
    await waitFor(() =>
      expect(screen.getByText('Recap note')).toBeInTheDocument(),
    );

    now = 9_000;
    fireEvent.click(screen.getByRole('button', { name: 'Verify' }));

    await waitFor(() => expect(v4API.metrics.recordReview).toHaveBeenCalled());
    expect(v4API.metrics.recordReview).toHaveBeenCalledWith({
      report_id: REPORT_ID_2,
      duration_ms: 4_000,
      suggestion_count: 1,
    });
  });

  it('keeps remaining items visible after verifying one proposal in a partial report', async () => {
    const detailWithTwo = {
      ...DETAIL_PAYLOAD,
      data: {
        ...DETAIL_PAYLOAD.data,
        narrative: {
          sections: [
            {
              name: 'proposed_commitments',
              title: 'Proposed commitments',
              items: [
                {
                  id: SUGGESTION_ID,
                  kind: 'create_entity',
                  title: 'Write docs',
                  reason: 'Write docs tomorrow',
                  payload: { title: 'Write docs', evidence: 'Write docs tomorrow' },
                },
                {
                  id: SUGGESTION_ID_2,
                  kind: 'create_entity',
                  title: 'Send recap',
                  reason: 'Send recap today',
                  payload: { title: 'Send recap', evidence: 'Send recap today' },
                },
              ],
            },
          ],
        },
      },
      suggestions: [
        ...DETAIL_PAYLOAD.suggestions,
        {
          id: SUGGESTION_ID_2,
          status: 'pending',
          suggestion_type: 'create_task',
          operation_type: 'create_entity',
          payload: { type: 'task', title: 'Send recap', evidence: 'Send recap today' },
        },
      ],
    };

    const detailAfterFirstVerify = {
      ...detailWithTwo,
      data: { ...detailWithTwo.data, status: 'partial' },
      suggestions: detailWithTwo.suggestions.map((row) =>
        row.id === SUGGESTION_ID ? { ...row, status: 'accepted' } : row,
      ),
    };

    let queueRows = [{ id: REPORT_ID, status: 'pending', source_note_id: 'note-1' }];
    mockReviewQueueList(queueRows);
    v4API.reports.list.mockImplementation(async (params = {}) => {
      const status = params.status || 'pending';
      const filtered = queueRows.filter((row) => row.status === status);
      return { data: filtered, meta: { total: filtered.length } };
    });
    v4API.reports.get.mockImplementation(async () => detailWithTwo);
    v4API.reports.resolve.mockImplementation(async () => {
      queueRows = [{ id: REPORT_ID, status: 'partial', source_note_id: 'note-1' }];
      v4API.reports.get.mockImplementation(async () => detailAfterFirstVerify);
      return { data: { status: 'partial' } };
    });

    renderReview();

    await screen.findByText('Write docs');
    expect(screen.getByText('Send recap')).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: 'Verify' })[0]);

    await waitFor(() => expect(v4API.reports.resolve).toHaveBeenCalled());
    expect(await screen.findByText('Send recap')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Verify' })).toHaveLength(1);
    expect(screen.getByRole('button', { name: /Accept remainder \(1\)/i })).toBeInTheDocument();
    expect(v4API.metrics.recordReview).not.toHaveBeenCalled();
  });

  it('accepts the remainder of a report in one batch', async () => {
    renderReview();

    await screen.findByText('Write docs');
    fireEvent.click(screen.getByRole('button', { name: 'Accept remainder (1)' }));

    await waitFor(() =>
      expect(v4API.reports.resolve).toHaveBeenCalledWith(REPORT_ID, {
        decisions: [],
        accept_rest: true,
      }),
    );
  });

  it('keeps applied annotations undoable and leaves proposals editable', async () => {
    renderReview();

    expect(await screen.findByText('Tag added: meeting')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Undo' })).toBeInTheDocument();
    expect(screen.getByText('Write docs')).toBeInTheDocument();
  });

  it('marks an applied-only report done when no proposals remain', async () => {
    const appliedOnlyDetail = {
      ...DETAIL_PAYLOAD,
      suggestions: DETAIL_PAYLOAD.suggestions.map((row) => ({ ...row, status: 'accepted' })),
    };
    v4API.reports.get.mockResolvedValue(appliedOnlyDetail);
    mockReviewQueueList([{
      id: REPORT_ID,
      status: 'pending',
      source_note_id: 'note-1',
      source_note_title: 'Standup note',
      pending_suggestion_count: 0,
    }]);

    renderReview();

    fireEvent.click(await screen.findByRole('button', { name: 'Done with capture' }));
    await waitFor(() => expect(v4API.reports.markDone).toHaveBeenCalledWith(REPORT_ID));
  });
});

describe('NextShell', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockReviewQueueList([
      { id: REPORT_ID, status: 'pending', source_note_title: 'Standup note', pending_suggestion_count: 1 },
      { id: REPORT_ID_2, status: 'pending', source_note_title: 'Recap note', pending_suggestion_count: 1 },
    ]);
    v4API.agentActivity.mockResolvedValue({ data: [], meta: { total: 0, counts: {} } });
    v4API.capture.mockResolvedValue({});
    v4API.search.mockResolvedValue({ data: [] });
  });

  it('shows the pending review count in the pulse control', async () => {
    render(
      <MemoryRouter initialEntries={['/review']}>
        <Routes>
          <Route path="/" element={<NextShell />}>
            <Route path="review" element={<div>Review page</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByLabelText(/Pulse: 0 running, 2 capture reports to review/i)).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText(/2 reports/)).toBeInTheDocument();
  });
});
