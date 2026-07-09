import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import NextApp from './NextApp';

vi.mock('../api/v4Client', () => ({
  v4API: {
    reports: {
      list: vi.fn(),
    },
    today: vi.fn(),
    capture: vi.fn(),
    search: vi.fn(),
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

import { v4API } from '../api/v4Client';

const TODAY_PAYLOAD = {
  new_since_yesterday_count: 1,
  counts: {
    needs_you: 4,
    in_motion: 2,
    fired_markers: 1,
    ripened_follow_ups: 1,
    newly_at_risk: 1,
  },
  needs_you: [
    {
      id: 'marker-1',
      kind: 'fired_marker',
      title: 'Nudge Sam about load tests',
      summary: 'nudge marker fired',
      receipts: [{ kind: 'marker', entity_id: 'marker-1', field: 'due_at', value: '2026-07-08T09:00:00Z' }],
      marker: { id: 'marker-1', kind: 'nudge' },
      entity: { id: 'task-load-test', type: 'task', title: 'Load test results' },
    },
    {
      id: 'task-deck',
      kind: 'due_today',
      title: 'Send deck to Maria',
      summary: 'due today',
      receipts: [{ kind: 'task', entity_id: 'task-deck', field: 'due_at', value: '2026-07-08T12:00:00Z' }],
      entity: {
        id: 'task-deck',
        type: 'task',
        title: 'Send deck to Maria',
        projects: [{ id: 'space-apollo', title: 'Apollo renewal' }],
      },
    },
    {
      id: 'task-load-test',
      kind: 'ripened_follow_up',
      title: 'Load test results',
      summary: 'Sam — quiet 4d',
      receipts: [{ kind: 'task', entity_id: 'task-load-test', field: 'follow_up_at', value: '2026-07-04T12:00:00Z' }],
      entity: { id: 'task-load-test', type: 'task', title: 'Load test results' },
      person: { id: 'person-sam', title: 'Sam' },
      days_silent: 4,
    },
    {
      id: 'task-contract',
      kind: 'newly_at_risk',
      title: 'Close contract',
      summary: 'stale 12d; due in 3d',
      receipts: [{ kind: 'task', entity_id: 'task-contract', field: 'due_at', value: '2026-07-11T12:00:00Z' }],
      entity: { id: 'task-contract', type: 'task', title: 'Close contract' },
      entity_type: 'task',
    },
  ],
  in_motion: [
    {
      id: 'task-roadmap',
      kind: 'upcoming_due',
      title: 'Roadmap review',
      summary: 'due later this week',
      receipts: [],
      entity: { id: 'task-roadmap', type: 'task', title: 'Roadmap review' },
    },
    {
      id: 'note-standup',
      kind: 'recent_note',
      title: 'Morning standup',
      summary: 'recent note',
      receipts: [],
      entity: { id: 'note-standup', type: 'note', title: 'Morning standup' },
    },
  ],
  fired_markers: [
    {
      id: 'marker-1',
      kind: 'nudge',
      note: 'Nudge Sam about load tests',
    },
  ],
  ripened_follow_ups: [
    {
      id: 'task-load-test',
      kind: 'ripened_follow_up',
      title: 'Load test results',
      summary: 'Sam — quiet 4d',
    },
  ],
  newly_at_risk: [
    {
      id: 'task-contract',
      kind: 'newly_at_risk',
      title: 'Close contract',
      summary: 'stale 12d; due in 3d',
    },
  ],
};

function renderToday() {
  return render(
    <MemoryRouter initialEntries={['/today']}>
      <Routes>
        <Route path="/*" element={<NextApp />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('TodaySurface', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.reports.list.mockResolvedValue({ data: [], meta: { total: 0 } });
    v4API.today.mockResolvedValue(TODAY_PAYLOAD);
    v4API.capture.mockResolvedValue({});
    v4API.search.mockResolvedValue({ data: [] });
  });

  it('loads the extended Today feed and renders both sections with counts', async () => {
    renderToday();

    expect(await screen.findByRole('heading', { name: 'Today' })).toBeInTheDocument();
    expect(v4API.today).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('link', { name: 'Today' })).toBeInTheDocument();

    const needsYou = screen.getByRole('region', { name: 'Needs you' });
    const inMotion = screen.getByRole('region', { name: 'In motion' });

    expect(within(needsYou).getByLabelText('4 items')).toBeInTheDocument();
    expect(within(inMotion).getByLabelText('2 items')).toBeInTheDocument();
    expect(screen.getByText(/4 items need you/i)).toBeInTheDocument();
    expect(screen.getByText(/2 in motion/i)).toBeInTheDocument();
  });

  it('shows fired markers and ripened follow-ups in Needs you', async () => {
    renderToday();

    const needsYou = await screen.findByRole('region', { name: 'Needs you' });

    expect(within(needsYou).getByText('Nudge Sam about load tests')).toBeInTheDocument();
    expect(within(needsYou).getByText(/nudge marker fired/i)).toBeInTheDocument();
    expect(within(needsYou).getByText('Load test results')).toBeInTheDocument();
    expect(within(needsYou).getByText(/Sam — quiet 4d/i)).toBeInTheDocument();
    expect(within(needsYou).getByText('Close contract')).toBeInTheDocument();
    expect(within(needsYou).getByText(/stale 12d; due in 3d/i)).toBeInTheDocument();
  });

  it('shows in-motion items in the second column', async () => {
    renderToday();

    const inMotion = await screen.findByRole('region', { name: 'In motion' });

    expect(within(inMotion).getByText('Roadmap review')).toBeInTheDocument();
    expect(within(inMotion).getByText('Morning standup')).toBeInTheDocument();
  });
});
