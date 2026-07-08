import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import NextApp from './NextApp';

vi.mock('../api/v4Client', () => ({
  v4API: {
    reports: {
      list: vi.fn(),
    },
    capture: vi.fn(),
    search: vi.fn(),
    brief: vi.fn(),
    timeline: vi.fn(),
    decisions: {
      list: vi.fn(),
    },
    suggestions: {
      list: vi.fn(),
    },
    entities: {
      list: vi.fn(),
      detail: vi.fn(),
      events: vi.fn(),
      update: vi.fn(),
      create: vi.fn(),
      createLink: vi.fn(),
      pin: vi.fn(),
      unpin: vi.fn(),
    },
    activityUpdates: {
      create: vi.fn(),
    },
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

import { v4API } from '../api/v4Client';

const SPACE_ID = 'space-apollo';

const DETAIL = {
  entity: {
    id: SPACE_ID,
    type: 'project',
    title: 'Apollo renewal',
    status: 'active',
    due_at: '2026-08-15T12:00:00Z',
    pinned_fields: ['status'],
    ai: {
      entity_summary: 'Maria confirmed intent to renew; deck due Friday.',
    },
  },
  sections: [
    {
      key: 'open_tasks',
      title: 'Open Tasks',
      items: [
        {
          entity: {
            id: 'task-deck',
            title: 'Send deck to Maria',
            status: 'open',
            due_at: '2026-07-11T12:00:00Z',
            owner: { id: 'person-operator', title: 'Operator' },
          },
        },
        {
          entity: {
            id: 'task-legal',
            title: 'Legal read on clause 7',
            status: 'waiting',
            due_at: null,
            owner: { id: 'person-dana', title: 'Dana' },
            updated_at: '2026-07-02T12:00:00Z',
          },
        },
      ],
    },
  ],
  decisions_count: 1,
};

const BRIEF = {
  brief: {
    narrative: 'Portfolio-wide brief.',
    generated_at: '2026-07-08T10:00:00Z',
    model: 'heuristic',
    items: [
      {
        entity_id: 'task-deck',
        title: 'Send deck to Maria',
        why_now: 'Due Friday and unstarted.',
        urgency: 5,
      },
    ],
  },
  from_cache: true,
};

const TIMELINE = {
  events: [
    {
      id: 'evt-1',
      actor: 'user',
      entity_type: 'note',
      occurred_at: '2026-07-08T14:02:00Z',
      narration: 'Captured call notes with Maria.',
    },
    {
      id: 'evt-2',
      actor: 'agent:v4-capture',
      entity_type: 'task',
      occurred_at: '2026-07-08T13:40:00Z',
      narration: 'Proposed status change to at risk.',
    },
  ],
};

const DECISIONS = {
  data: [
    {
      id: 'decision-1',
      statement: 'Renewal anchored on 2-yr term',
      decided_at: '2026-07-03T12:00:00Z',
      decided_by: 'user',
      context: 'Call with Maria',
    },
  ],
};

const QUESTIONS = {
  data: [
    {
      id: 'suggestion-q1',
      reason: 'Who committed to this?',
      payload: {
        thread_id: SPACE_ID,
        kind: 'attribution',
        question: 'Who owns the legal review?',
      },
      source_note_title: 'Team sync notes',
    },
  ],
};

const LEDGER = {
  data: [
    {
      id: 'ledger-1',
      actor: 'user',
      event_type: 'updated',
      created_at: '2026-07-07T12:00:00Z',
      reason: 'amended',
      narration: 'Amended activity update.',
      old_value: { content: 'Draft v1' },
      new_value: { content: 'Draft v2' },
    },
    {
      id: 'ledger-2',
      actor: 'user',
      event_type: 'updated',
      created_at: '2026-07-06T12:00:00Z',
      reason: 'pinned status',
      narration: 'Pinned status field.',
      old_value: { pinned_fields: [] },
      new_value: { pinned_fields: ['status'], field: 'status' },
    },
  ],
};

const PROJECTS = { data: [{ id: SPACE_ID, title: 'Apollo renewal', type: 'project', status: 'active' }] };
const AREAS = { data: [] };
const PEOPLE = {
  data: [
    { id: 'person-operator', title: 'Operator', is_owner: true },
    { id: 'person-dana', title: 'Dana' },
  ],
};

function renderDossier() {
  return render(
    <MemoryRouter initialEntries={[`/next/spaces/${SPACE_ID}`]}>
      <Routes>
        <Route path="/next/*" element={<NextApp />} />
      </Routes>
    </MemoryRouter>,
  );
}

function mockDossierLoads() {
  v4API.reports.list.mockResolvedValue({ data: [], meta: { total: 0 } });
  v4API.capture.mockResolvedValue({});
  v4API.search.mockResolvedValue({ data: [] });
  v4API.entities.detail.mockResolvedValue(DETAIL);
  v4API.brief.mockResolvedValue(BRIEF);
  v4API.timeline.mockResolvedValue(TIMELINE);
  v4API.decisions.list.mockResolvedValue(DECISIONS);
  v4API.suggestions.list.mockResolvedValue(QUESTIONS);
  v4API.entities.events.mockResolvedValue(LEDGER);
  v4API.entities.list
    .mockResolvedValueOnce(PROJECTS)
    .mockResolvedValueOnce(AREAS)
    .mockResolvedValueOnce(PEOPLE);
  v4API.entities.pin.mockResolvedValue({ data: {} });
  v4API.entities.unpin.mockResolvedValue({ data: {} });
}

describe('DossierSurface', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockDossierLoads();
  });

  it('loads brief and spine for a space entity', async () => {
    renderDossier();

    expect(await screen.findByRole('heading', { name: 'Apollo renewal' })).toBeInTheDocument();
    expect(v4API.entities.detail).toHaveBeenCalledWith(SPACE_ID);
    expect(v4API.brief).toHaveBeenCalled();
    expect(v4API.timeline).toHaveBeenCalledWith({ thread_id: SPACE_ID, limit: 40 });

    expect(screen.getByText(/Send deck to Maria: Due Friday and unstarted/)).toBeInTheDocument();
    expect(screen.getByText('Captured call notes with Maria.')).toBeInTheDocument();
    expect(screen.getByText('Proposed status change to at risk.')).toBeInTheDocument();
  });

  it('renders open commitments, decisions, and questions sections', async () => {
    renderDossier();

    expect(await screen.findByRole('heading', { name: 'Apollo renewal' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Decisions' })).toBeInTheDocument();
    expect(screen.getByText('Renewal anchored on 2-yr term')).toBeInTheDocument();
    expect(screen.getByText('Send deck to Maria')).toBeInTheDocument();
    expect(screen.getByText(/Dana — Legal read on clause 7/)).toBeInTheDocument();
    expect(screen.getByText('Who owns the legal review?')).toBeInTheDocument();
  });

  it('shows ledger tab with attributed timeline and amend history', async () => {
    renderDossier();

    expect(await screen.findByRole('heading', { name: 'Apollo renewal' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('tab', { name: 'Ledger' }));

    expect(await screen.findByText('Amended activity update.')).toBeInTheDocument();
    expect(screen.getByText(/content: Draft v1 → Draft v2/)).toBeInTheDocument();
    expect(screen.getByText('Pinned status field.')).toBeInTheDocument();
    expect(v4API.entities.events).toHaveBeenCalledWith(SPACE_ID);
  });

  it('toggles pin state from the dossier header', async () => {
    renderDossier();

    expect(await screen.findByRole('heading', { name: 'Apollo renewal' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Unpin status' }));

    await waitFor(() =>
      expect(v4API.entities.unpin).toHaveBeenCalledWith(SPACE_ID, 'status'),
    );
  });
});

describe('SpacesSurface navigation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.reports.list.mockResolvedValue({ data: [], meta: { total: 0 } });
    v4API.capture.mockResolvedValue({});
    v4API.search.mockResolvedValue({ data: [] });
    v4API.entities.list.mockResolvedValueOnce(PROJECTS).mockResolvedValueOnce(AREAS);
  });

  it('lists spaces and links into the dossier route', async () => {
    render(
      <MemoryRouter initialEntries={['/next/spaces']}>
        <Routes>
          <Route path="/next/*" element={<NextApp />} />
        </Routes>
      </MemoryRouter>,
    );

    const link = await screen.findByRole('link', { name: 'Apollo renewal' });
    expect(link).toHaveAttribute('href', `/next/spaces/${SPACE_ID}`);
    expect(screen.getByRole('navigation', { name: 'Primary' })).toBeInTheDocument();
  });
});
