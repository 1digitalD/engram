import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import NextApp from './NextApp';

vi.mock('../api/v4Client', () => ({
  v4API: {
    reports: {
      list: vi.fn().mockResolvedValue({ data: [], meta: { total: 0 } }),
    },
    agentActivity: vi.fn().mockResolvedValue({ data: [], meta: { total: 0, counts: {} } }),
    capture: vi.fn(),
    search: vi.fn(),
    entities: {
      list: vi.fn(),
      detail: vi.fn(),
    },
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

import { v4API } from '../api/v4Client';

const PERSON_ID = 'person-mary';

const PEOPLE = {
  data: [
    { id: PERSON_ID, type: 'person', title: 'Mary Patel', status: 'active' },
    { id: 'person-akash', type: 'person', title: 'Akash', status: 'active' },
  ],
};

const DETAIL = {
  entity: {
    id: PERSON_ID,
    type: 'person',
    title: 'Mary Patel',
    status: 'active',
    ai: {
      entity_summary: 'Final reviewer for the HITL pilot.',
    },
  },
  pulse: {
    headline: 'Follow up on 1 quiet task and 1 stuck task.',
    summary: {
      open_tasks: 2,
      stuck_tasks: 1,
      overdue_follow_ups: 0,
      quiet_tasks: 1,
    },
    focus_items: [
      {
        kind: 'quiet',
        label: 'Quiet 9d',
        entity: {
          id: 'task-rollout',
          type: 'task',
          title: 'Send rollout update',
          status: 'open',
          projects: [{ id: 'space-hitl', title: 'HITL Pilot' }],
        },
      },
    ],
  },
  current_load: [
    {
      task: {
        id: 'task-review',
        type: 'task',
        title: 'Review PR #847',
        status: 'blocked',
        projects: [{ id: 'space-hitl', title: 'HITL Pilot' }],
      },
      last_heard_at: '2026-06-22T14:00:00Z',
      last_heard_preview: 'Mary said she would review by end of week.',
    },
  ],
  meeting_prep: {
    headline: 'Go in with 3 agenda topics and 1 recent note.',
    mutual_commitments: {
      they_owe: [
        {
          id: 'task-review',
          title: 'Review PR #847',
          status: 'blocked',
          due_at: '2026-07-11T12:00:00Z',
          projects: [{ id: 'space-hitl', title: 'HITL Pilot' }],
        },
      ],
      you_owe: [
        {
          id: 'task-recap',
          title: 'Send Mary the recap',
          status: 'open',
          due_at: '2026-07-10T12:00:00Z',
          projects: [{ id: 'space-hitl', title: 'HITL Pilot' }],
        },
      ],
    },
    agenda_items: [
      {
        kind: 'quiet',
        title: 'Ask for status on rollout update',
        reason: 'No update in 9 days.',
        entity: {
          id: 'task-rollout',
          type: 'task',
          title: 'Send rollout update',
          status: 'open',
          projects: [{ id: 'space-hitl', title: 'HITL Pilot' }],
        },
      },
    ],
    recent_notes: [
      {
        id: 'note-mary-1on1',
        type: 'note',
        title: 'Mary 1:1 notes',
        updated_at: '2026-06-20T11:00:00Z',
        preview: 'Discuss rollout blockers and support path.',
      },
    ],
  },
};

function renderRoute(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/*" element={<NextApp />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('PeopleSurface', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.reports.list.mockResolvedValue({ data: [], meta: { total: 0 } });
    v4API.capture.mockResolvedValue({});
    v4API.search.mockResolvedValue({ data: [] });
    v4API.entities.list.mockResolvedValue(PEOPLE);
    v4API.entities.detail.mockResolvedValue(DETAIL);
  });

  it('loads the people index and links each person into the surface route', async () => {
    renderRoute('/people');

    expect(await screen.findByRole('heading', { name: 'People' })).toBeInTheDocument();
    expect(v4API.entities.list).toHaveBeenCalledWith({ type: 'person' });
    expect(screen.getByRole('link', { name: 'Mary Patel' })).toHaveAttribute(
      'href',
      `/people/${PERSON_ID}`,
    );
  });

  it('loads a person rollup with owes and prep sections', async () => {
    renderRoute(`/people/${PERSON_ID}`);

    expect(await screen.findByRole('heading', { name: 'Mary Patel' })).toBeInTheDocument();
    expect(v4API.entities.detail).toHaveBeenCalledWith(PERSON_ID);
    expect(screen.getByText('Final reviewer for the HITL pilot.')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'People' })).toHaveLength(2);
    expect(screen.getByRole('link', { name: 'Jump to prep' })).toHaveAttribute(
      'href',
      '#person-prep',
    );

    const owesSection = screen.getByRole('region', { name: 'They owe you' });
    expect(within(owesSection).getByText('Review PR #847')).toBeInTheDocument();

    const owedSection = screen.getByRole('region', { name: 'You owe them' });
    expect(within(owedSection).getByText('Send Mary the recap')).toBeInTheDocument();

    const quietSection = screen.getByRole('region', { name: 'Quiet watch' });
    expect(within(quietSection).getByText('Send rollout update')).toBeInTheDocument();
    expect(within(quietSection).getByText('Quiet 9d')).toBeInTheDocument();

    const prepSection = screen.getByRole('region', { name: 'Meeting prep' });
    expect(within(prepSection).getByText('Go in with 3 agenda topics and 1 recent note.')).toBeInTheDocument();
    expect(within(prepSection).getByText('Mary 1:1 notes')).toBeInTheDocument();
  });
});
