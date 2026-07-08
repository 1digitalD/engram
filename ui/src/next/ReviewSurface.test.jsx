import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ReviewSurface from './ReviewSurface';
import NextShell from './NextShell';

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

function renderReview(initialEntry = '/next/review') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/next/review" element={<ReviewSurface />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('ReviewSurface', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(Date, 'now').mockReturnValue(1_000);
    v4API.reports.list.mockResolvedValue(LIST_PAYLOAD);
    v4API.reports.get.mockResolvedValue(DETAIL_PAYLOAD);
    v4API.reports.resolve.mockResolvedValue({ data: { status: 'reviewed' } });
    v4API.metrics.recordReview.mockResolvedValue({ data: {} });
    v4API.capture.mockResolvedValue({});
    v4API.search.mockResolvedValue({ data: [] });
  });

  it('loads pending reports via GET /reports', async () => {
    renderReview();

    expect(await screen.findByRole('heading', { name: 'Review' })).toBeInTheDocument();
    expect(v4API.reports.list).toHaveBeenCalledWith({ status: 'pending' });
    await waitFor(() => expect(v4API.reports.get).toHaveBeenCalledWith(REPORT_ID));
    expect(await screen.findByText('Write docs')).toBeInTheDocument();
    expect(screen.getByText('Proposed commitments')).toBeInTheDocument();
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

  it('dismisses proposal with reason', async () => {
    renderReview();

    await screen.findByText('Write docs');
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    fireEvent.click(await screen.findByRole('button', { name: 'not mine' }));

    await waitFor(() =>
      expect(v4API.reports.resolve).toHaveBeenCalledWith(REPORT_ID, {
        decisions: [
          { suggestion_id: SUGGESTION_ID, action: 'dismiss', dismissal_reason: 'not mine' },
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

  it('sends review duration report when report leaves queue', async () => {
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
    v4API.reports.get.mockImplementation(async (reportId) => (
      reportId === REPORT_ID_2 ? DETAIL_PAYLOAD_2 : DETAIL_PAYLOAD
    ));
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
    await screen.findByText('Send recap');
    // Detail effect seeds reviewStartedAt at now=5_000 before we advance the clock.
    await waitFor(() => expect(v4API.reports.get).toHaveBeenCalledWith(REPORT_ID_2));
    now = 25_000;
    fireEvent.click(screen.getByRole('button', { name: 'Verify' }));

    await waitFor(() =>
      expect(v4API.metrics.recordReview).toHaveBeenCalledWith({
        report_id: REPORT_ID_2,
        duration_ms: 20_000,
        suggestion_count: 1,
      }),
    );
  });

  it('accepts remainder of report in one batch', async () => {
    renderReview();

    await screen.findByText('Write docs');
    fireEvent.click(screen.getByRole('button', { name: /Accept remainder \(1\)/ }));

    await waitFor(() =>
      expect(v4API.reports.resolve).toHaveBeenCalledWith(REPORT_ID, {
        decisions: [],
        accept_rest: true,
      }),
    );
  });

  it('hides per-item actions for applied annotations', async () => {
    renderReview();

    await screen.findByText('Tag added: meeting');
    expect(screen.getByText(/Already applied/)).toBeInTheDocument();
    expect(
      screen.queryByText('Tag added: meeting', { selector: 'button' }),
    ).not.toBeInTheDocument();
    expect(screen.getByText('Write docs')).toBeInTheDocument();
  });
});

describe('NextShell', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.reports.list.mockResolvedValue({ data: [], meta: { total: 2 } });
    v4API.metrics.recordReview.mockResolvedValue({ data: {} });
    v4API.capture.mockResolvedValue({});
    v4API.search.mockResolvedValue({ data: [] });
  });

  it('shows review pulse count from pending reports', async () => {
    render(
      <MemoryRouter initialEntries={['/next/review']}>
        <Routes>
          <Route path="/next" element={<NextShell />}>
            <Route path="review" element={<div>Review page</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByLabelText(/Review, 2 pending reports/)).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });
});
