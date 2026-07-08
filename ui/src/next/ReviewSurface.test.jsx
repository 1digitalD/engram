import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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

describe('ReviewSurface', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.reports.list.mockResolvedValue(LIST_PAYLOAD);
    v4API.reports.get.mockResolvedValue(DETAIL_PAYLOAD);
    v4API.reports.resolve.mockResolvedValue({ data: { status: 'reviewed' } });
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

  it('verifies a proposal via POST /reports/<id>/resolve', async () => {
    renderReview();

    await screen.findByText('Write docs');
    fireEvent.click(screen.getByRole('button', { name: 'Verify' }));

    await waitFor(() => expect(v4API.reports.resolve).toHaveBeenCalledWith(REPORT_ID, {
      decisions: [{ suggestion_id: SUGGESTION_ID, action: 'accept' }],
    }));
  });

  it('dismisses with a reason', async () => {
    renderReview();

    await screen.findByText('Write docs');
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    fireEvent.click(await screen.findByRole('button', { name: 'not mine' }));

    await waitFor(() => expect(v4API.reports.resolve).toHaveBeenCalledWith(REPORT_ID, {
      decisions: [{ suggestion_id: SUGGESTION_ID, action: 'dismiss', dismissal_reason: 'not mine' }],
    }));
  });

  it('edits a proposal title before verifying', async () => {
    renderReview();

    await screen.findByText('Write docs');
    fireEvent.click(screen.getByRole('button', { name: 'Edit' }));
    const input = screen.getByLabelText('Edit title');
    fireEvent.change(input, { target: { value: 'Write documentation' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save edit' }));

    await waitFor(() => expect(v4API.reports.resolve).toHaveBeenCalledWith(REPORT_ID, {
      decisions: [{
        suggestion_id: SUGGESTION_ID,
        action: 'edit',
        edits: { title: 'Write documentation' },
      }],
    }));
  });

  it('defers a proposal with later', async () => {
    renderReview();

    await screen.findByText('Write docs');
    fireEvent.click(screen.getByRole('button', { name: 'Later' }));

    await waitFor(() => expect(v4API.reports.resolve).toHaveBeenCalledWith(REPORT_ID, {
      decisions: [{ suggestion_id: SUGGESTION_ID, action: 'later' }],
    }));
  });

  it('batch accept-rest calls POST /reports/<id>/resolve', async () => {
    renderReview();

    await screen.findByText('Write docs');
    fireEvent.click(screen.getByRole('button', { name: /Accept remainder \(1\)/ }));

    await waitFor(() => expect(v4API.reports.resolve).toHaveBeenCalledWith(REPORT_ID, {
      decisions: [],
      accept_rest: true,
    }));
  });

  it('renders applied annotations without per-item resolve actions', async () => {
    renderReview();

    await screen.findByText('Tag added: meeting');
    expect(screen.getByText(/Already applied/)).toBeInTheDocument();
    const appliedCard = screen.getByText('Tag added: meeting').closest('li');
    expect(within(appliedCard).queryByRole('button', { name: 'Verify' })).not.toBeInTheDocument();
    const proposalCard = screen.getByText('Write docs').closest('li');
    expect(within(proposalCard).getByRole('button', { name: 'Verify' })).toBeInTheDocument();
  });
});

describe('NextShell', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.reports.list.mockResolvedValue({ data: [], meta: { total: 2 } });
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
