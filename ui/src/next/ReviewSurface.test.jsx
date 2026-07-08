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
const SUGGESTION_ID = 'suggestion-1';
const LIST_PAYLOAD = {
  data: [{ id: REPORT_ID, status: 'pending', source_note_id: 'note-1' }],
  meta: { total: 1 },
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

function renderReview(initialEntry = '/next/review') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/next" element={<NextShell />}>
          <Route path="review" element={<ReviewSurface />} />
        </Route>
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

  it('loads pending reports from GET /reports', async () => {
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

  it('dismisses with reason', async () => {
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

  it('marks a suggestion for later', async () => {
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
    vi.spyOn(Date, 'now').mockReturnValueOnce(1_000).mockReturnValueOnce(46_000);

    renderReview();

    await screen.findByText('Write docs');
    fireEvent.click(screen.getByRole('button', { name: 'Verify' }));

    await waitFor(() =>
      expect(v4API.metrics.recordReview).toHaveBeenCalledWith({
        report_id: REPORT_ID,
        duration_ms: 45_000,
        suggestion_count: 1,
      }),
    );
  });

  it('accepts the rest of the report in one batch', async () => {
    renderReview();

    await screen.findByText('Write docs');
    fireEvent.click(screen.getByRole('button', { name: /Accept rest \(1\)/ }));

    await waitFor(() =>
      expect(v4API.reports.resolve).toHaveBeenCalledWith(REPORT_ID, {
        decisions: [],
        accept_rest: true,
      }),
    );
  });

  it('does not show per-item actions for applied annotations', async () => {
    renderReview();

    await screen.findByText('Tag added: meeting');
    expect(screen.getByText(/Already applied/)).toBeInTheDocument();
    expect(screen.queryByText('Tag added: meeting', { selector: 'button' })).not.toBeInTheDocument();
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

  it('shows review pulse count for pending reports', async () => {
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
