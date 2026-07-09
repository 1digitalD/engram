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
    },
    metrics: {
      recordReview: vi.fn(),
    },
    summary: vi.fn(),
    brief: vi.fn(),
    capture: vi.fn(),
    search: vi.fn(),
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

import { v4API } from '../api/v4Client';

const REPORT_ID = 'report-1';
const REPORT_ID_2 = 'report-2';
const SUGGESTION_ID = 'suggestion-1';
const SUGGESTION_ID_2 = 'suggestion-2';

const LIST_PAYLOAD = {
  data: [{ id: REPORT_ID, status: 'pending', source_note_id: 'note-1' }],
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

function renderReview(initialEntry = '/next/review') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/next/review" element={<ReviewSurface />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ReviewSurface', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(Date, 'now').mockReturnValue(1_000);

    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });

    v4API.reports.list.mockResolvedValue(LIST_PAYLOAD);
    v4API.reports.get.mockResolvedValue(DETAIL_PAYLOAD);
    v4API.reports.resolve.mockResolvedValue({ data: { status: 'reviewed' } });
    v4API.metrics.recordReview.mockResolvedValue({ data: {} });
    v4API.summary.mockResolvedValue(SUMMARY_PAYLOAD);
    v4API.brief.mockResolvedValue(BRIEF_PAYLOAD);
    v4API.capture.mockResolvedValue({});
    v4API.search.mockResolvedValue({ data: [] });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('loads pending reports via GET /reports', async () => {
    renderReview();

    expect(await screen.findByRole('heading', { name: 'Review' })).toBeInTheDocument();
    expect(v4API.reports.list).toHaveBeenCalledWith({ status: 'pending' });
    expect(v4API.summary).toHaveBeenCalled();
    expect(v4API.brief).toHaveBeenCalled();

    await waitFor(() => expect(v4API.reports.get).toHaveBeenCalledWith(REPORT_ID));
    expect(await screen.findByText('Write docs')).toBeInTheDocument();
    expect(screen.getByText('Proposed commitments')).toBeInTheDocument();
  });

  it('renders a weekly digest with citations', async () => {
    renderReview();

    expect(await screen.findByRole('region', { name: 'Weekly digest' })).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByLabelText('Weekly digest draft').value).toContain('Moved'),
    );
    expect(screen.getByLabelText('Weekly digest draft').value).toContain(
      'Apollo: Pricing decision is still open.',
    );
    expect(screen.getByText('Watch 1:1 drift and 1 blocked task.')).toBeInTheDocument();
    expect(screen.getAllByText('Send deck: Due Friday and still unstarted.').length).toBeGreaterThan(0);
  });

  it('allows editing and copying the weekly digest draft', async () => {
    renderReview();

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
    fireEvent.change(screen.getByLabelText('Edit title'), {
      target: { value: 'Write documentation' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save edit' }));

    await waitFor(() =>
      expect(v4API.reports.resolve).toHaveBeenCalledWith(REPORT_ID, {
        decisions: [
          {
            suggestion_id: SUGGESTION_ID,
            action: 'edit',
            edits: { title: 'Write documentation' },
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
    v4API.reports.list
      .mockResolvedValueOnce(LIST_PAYLOAD)
      .mockResolvedValueOnce({ data: [], meta: { total: 0 } });

    renderReview();

    await screen.findByText('Write docs');
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

    v4API.reports.list.mockImplementation(async () => ({
      data: pendingReports,
      meta: { total: pendingReports.length },
    }));
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

  it('keeps applied annotations read-only and leaves the proposal editable', async () => {
    renderReview();

    expect(await screen.findByText('Tag added: meeting')).toBeInTheDocument();
    expect(screen.getByText(/Already applied/)).toBeInTheDocument();
    expect(screen.queryByText('Tag added: meeting', { selector: 'button' })).not.toBeInTheDocument();
    expect(screen.getByText('Write docs')).toBeInTheDocument();
  });
});

describe('NextShell', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.reports.list.mockResolvedValue({ data: [{ id: REPORT_ID }, { id: REPORT_ID_2 }], meta: { total: 2 } });
    v4API.capture.mockResolvedValue({});
    v4API.search.mockResolvedValue({ data: [] });
  });

  it('shows the pending review count in the pulse link', async () => {
    render(
      <MemoryRouter initialEntries={['/next/review']}>
        <Routes>
          <Route path="/next" element={<NextShell />}>
            <Route path="review" element={<div>Review page</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByLabelText(/Review, 2 pending reports/i)).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });
});
