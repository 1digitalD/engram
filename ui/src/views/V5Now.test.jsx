import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ReviewProvider, useReview } from '../context/ReviewContext';
import { SummaryProvider } from '../context/SummaryContext';
import V5Now, { transformTodayResponse } from './V5Now';
import V5ReviewSheet from './V5ReviewSheet';
import { MOCKED_NOW_DATA } from './V5Now.fixtures';

vi.mock('../api/v4Client', () => ({
  v4API: {
    suggestions: {
      list: vi.fn(),
    },
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

import { v4API } from '../api/v4Client';

function NowWithReviewSheet({ previewData }) {
  const { open, closeReview } = useReview();
  return (
    <>
      <V5Now previewData={previewData} />
      <V5ReviewSheet open={open} onClose={closeReview} />
    </>
  );
}

function renderWithRouter(ui) {
  return render(
    <SummaryProvider value={{ refreshSummary: vi.fn() }}>
      <ReviewProvider>
        <MemoryRouter initialEntries={['/now']}>
          {ui}
        </MemoryRouter>
      </ReviewProvider>
    </SummaryProvider>,
  );
}

describe('transformTodayResponse', () => {
  it('maps blocked, waiting, and follow-up buckets into the three bands', () => {
    const today = {
      blocked_tasks: [{
        id: 'task-blocked',
        type: 'task',
        title: 'Blocked task',
        attention: { score: 80 },
      }],
      waiting_tasks: [{
        id: 'task-waiting',
        type: 'task',
        title: 'Waiting task',
        attention: { score: 40 },
      }],
      overdue_follow_ups: [{
        id: 'task-overdue-followup',
        type: 'task',
        title: 'Overdue follow-up',
        follow_up_at: '2026-07-01T12:00:00Z',
        attention: { score: 78 },
      }],
      follow_ups: [{
        id: 'task-followup',
        type: 'task',
        title: 'Today follow-up',
        follow_up_at: '2026-07-02T12:00:00Z',
        attention: { score: 35 },
      }],
    };

    const data = transformTodayResponse(today);

    expect(data.needs_you_now.map((item) => item.id)).toEqual(
      expect.arrayContaining(['task-blocked', 'task-overdue-followup']),
    );
    expect(data.waiting_on_you.map((item) => item.id)).toEqual(
      expect.arrayContaining(['task-waiting', 'task-followup']),
    );
    expect(data.needs_you_now.find((item) => item.id === 'task-blocked')?.why_now).toBe('blocked');
    expect(data.waiting_on_you.find((item) => item.id === 'task-waiting')?.why_now).toBe('waiting');
  });

  it('adds recent notes to ambient and a pending suggestions row', () => {
    const today = {
      recent_notes: [{
        id: 'note-1',
        type: 'note',
        title: 'Recent note',
        ai: { intent: 'follow_up' },
      }],
      pending_suggestions: [{ id: 's1' }, { id: 's2' }],
      new_since_yesterday_count: 3,
    };

    const data = transformTodayResponse(today);

    expect(data.ambient.map((item) => item.id)).toContain('note-1');
    expect(data.waiting_on_you.some((item) => item.id === 'pending-suggestions')).toBe(true);
    expect(data.new_since_yesterday_count).toBe(3);
  });
});

describe('V5Now', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.suggestions.list.mockResolvedValue({
      data: [{ id: 's1', payload: { title: 'Suggested task' } }],
      meta: { total: 1 },
    });
  });

  it('renders three sections from mocked data', () => {
    renderWithRouter(<V5Now previewData={MOCKED_NOW_DATA} />);
    expect(screen.getByRole('heading', { name: /Needs you now/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Waiting on you/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Ambient/i })).toBeInTheDocument();
    expect(screen.getByText(/Send yesterday’s standup update/i)).toBeInTheDocument();
    expect(screen.getByText(/GTM brief/i)).toBeInTheDocument();
    expect(screen.getByText(/Q3 strategy doc is still taking shape/i)).toBeInTheDocument();
  });

  it('renders sentence-shaped rows with metadata and action buttons', () => {
    renderWithRouter(<V5Now previewData={MOCKED_NOW_DATA} />);
    expect(screen.getByText('Due in 32 min')).toBeInTheDocument();
    expect(screen.getByText('Hard deadline this morning')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Open$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Mark done/i })).toBeInTheDocument();
  });

  it('links the sentence to the item and the chip to the parent thread', () => {
    renderWithRouter(<V5Now previewData={MOCKED_NOW_DATA} />);

    const sentence = screen.getByText(/Send yesterday’s standup update/i);
    const chip = screen.getByText('Product Launch');

    expect(sentence.closest('a')).toHaveAttribute('href', '/tasks/task-standup');
    expect(chip.closest('a')).toHaveAttribute('href', '/projects/project-launch');
  });

  it('keeps open navigation distinct from thread navigation', async () => {
    const user = userEvent.setup();

    render(
      <SummaryProvider value={{ refreshSummary: vi.fn() }}>
        <ReviewProvider>
          <MemoryRouter initialEntries={['/now']}>
            <Routes>
              <Route path="/now" element={<V5Now previewData={MOCKED_NOW_DATA} />} />
              <Route path="/tasks/:id" element={<div>Task detail</div>} />
              <Route path="/projects/:id" element={<div>Project detail</div>} />
            </Routes>
          </MemoryRouter>
        </ReviewProvider>
      </SummaryProvider>,
    );

    await user.click(screen.getByRole('button', { name: /^Open$/i }));
    expect(await screen.findByText('Task detail')).toBeInTheDocument();
  });

  it('shows an empty hint when no items are present', () => {
    renderWithRouter(<V5Now previewData={{ needs_you_now: [], waiting_on_you: [], ambient: [] }} />);
    expect(screen.getByText(/No items in your Now view yet/i)).toBeInTheDocument();
  });

  it('renders blocked and follow-up items from the today payload', () => {
    const previewData = transformTodayResponse({
      blocked_tasks: [{
        id: 'blocked-1',
        type: 'task',
        title: 'Security approval pending',
        attention: { score: 82 },
      }],
      overdue_follow_ups: [{
        id: 'followup-1',
        type: 'task',
        title: 'Ping vendor about contract',
        follow_up_at: '2026-07-01T12:00:00Z',
        attention: { score: 76 },
      }],
    });

    renderWithRouter(<V5Now previewData={previewData} />);
    expect(screen.getAllByText(/Security approval pending/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Ping vendor about contract/i).length).toBeGreaterThan(0);
    expect(screen.getByText('blocked')).toBeInTheDocument();
    expect(screen.getByText('overdue follow-up')).toBeInTheDocument();
  });

  it('opens the review sheet from the pending suggestions row', async () => {
    const user = userEvent.setup();

    renderWithRouter(
      <NowWithReviewSheet
        previewData={transformTodayResponse({
          pending_suggestions: [{ id: 's1' }],
        })}
      />,
    );

    expect(screen.getByText(/1 suggestion ready to review/i)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Review suggestions/i }));
    expect(await screen.findByRole('dialog', { name: 'Review suggestions' })).toBeInTheDocument();
    await waitFor(() => expect(v4API.suggestions.list).toHaveBeenCalledWith({ status: 'pending' }));
  });

  it('shows new since yesterday in the subtitle', () => {
    renderWithRouter(
      <V5Now
        previewData={{
          ...transformTodayResponse({
            blocked_tasks: [{
              id: 'blocked-1',
              type: 'task',
              title: 'Blocked task',
              attention: { score: 80 },
            }],
            new_since_yesterday_count: 2,
          }),
        }}
      />,
    );

    expect(screen.getByText(/2 new since yesterday/i)).toBeInTheDocument();
  });
});
