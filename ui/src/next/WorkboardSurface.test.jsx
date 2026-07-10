import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import NextApp from './NextApp';

vi.mock('../api/v4Client', () => ({
  v4API: {
    reports: {
      list: vi.fn().mockResolvedValue({ data: [], meta: { total: 0 } }),
    },
    agentActivity: vi.fn().mockResolvedValue({ data: [], meta: { total: 0, counts: {} } }),
    workboard: vi.fn(),
    capture: vi.fn(),
    search: vi.fn(),
    entities: {
      list: vi.fn(),
      update: vi.fn(),
      create: vi.fn(),
      createLink: vi.fn(),
    },
    activityUpdates: {
      create: vi.fn(),
    },
    commitments: {
      nudgeDraft: vi.fn(),
    },
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

import { v4API } from '../api/v4Client';

const SPACE_PAYLOAD = {
  data: {
    groups: [
      {
        key: 'space-apollo',
        label: 'Apollo',
        kind: 'space',
        entity_id: 'space-apollo',
        counts: {
          total: 2,
          mine: 1,
          waiting_on: 1,
          overdue: 1,
          stale: 1,
          blocked: 1,
          at_risk: 1,
        },
        at_risk: {
          flag: true,
          reason: 'finish line in 4d; 1 of 2 open tasks stale',
          receipts: [],
        },
        items: [
          {
            id: 'task-close-contract',
            title: 'Close contract',
            status: 'open',
            due_at: '2026-07-07T12:00:00Z',
            owner: { id: 'person-operator', title: 'Operator' },
            space: { id: 'space-apollo', title: 'Apollo', due_at: '2026-07-12T12:00:00Z' },
            blocked_by: [{ id: 'task-legal', title: 'Legal review' }],
            states: {
              mine: true,
              waiting_on: false,
              overdue: true,
              stale: false,
              blocked: true,
              at_risk: true,
            },
            at_risk: {
              flag: true,
              reason: 'overdue 1d; blocked by 1 open item',
              receipts: [],
            },
          },
          {
            id: 'task-security-questionnaire',
            title: 'Security questionnaire',
            status: 'waiting',
            due_at: '2026-07-11T12:00:00Z',
            owner: { id: 'person-sam', title: 'Sam' },
            space: { id: 'space-apollo', title: 'Apollo', due_at: '2026-07-12T12:00:00Z' },
            blocked_by: [],
            states: {
              mine: false,
              waiting_on: true,
              overdue: false,
              stale: true,
              blocked: false,
              at_risk: false,
            },
            at_risk: { flag: false, reason: '', receipts: [] },
          },
        ],
      },
    ],
  },
  meta: {
    group: 'space',
    total: 2,
    counts: {
      total: 2,
      mine: 1,
      waiting_on: 1,
      overdue: 1,
      stale: 1,
      blocked: 1,
      at_risk: 1,
    },
  },
};

const PERSON_PAYLOAD = {
  data: {
    groups: [
      {
        key: 'person-operator',
        label: 'Operator',
        kind: 'person',
        entity_id: 'person-operator',
        counts: {
          total: 1,
          mine: 1,
          waiting_on: 0,
          overdue: 1,
          stale: 0,
          blocked: 1,
          at_risk: 1,
        },
        at_risk: { flag: false, reason: '', receipts: [] },
        items: [SPACE_PAYLOAD.data.groups[0].items[0]],
      },
      {
        key: 'person-sam',
        label: 'Sam',
        kind: 'person',
        entity_id: 'person-sam',
        counts: {
          total: 1,
          mine: 0,
          waiting_on: 1,
          overdue: 0,
          stale: 1,
          blocked: 0,
          at_risk: 0,
        },
        at_risk: { flag: false, reason: '', receipts: [] },
        items: [SPACE_PAYLOAD.data.groups[0].items[1]],
      },
    ],
  },
  meta: {
    group: 'person',
    total: 2,
    counts: SPACE_PAYLOAD.meta.counts,
  },
};

const PROJECTS = { data: [{ id: 'space-apollo', title: 'Apollo' }, { id: 'space-orbit', title: 'Orbit' }] };
const AREAS = { data: [] };
const PEOPLE = { data: [{ id: 'person-operator', title: 'Operator' }, { id: 'person-sam', title: 'Sam' }] };

function renderWorkboard() {
  return render(
    <MemoryRouter initialEntries={['/workboard']}>
      <Routes>
        <Route path="/*" element={<NextApp />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('WorkboardSurface', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.reports.list.mockResolvedValue({ data: [], meta: { total: 0 } });
    v4API.capture.mockResolvedValue({});
    v4API.search.mockResolvedValue({ data: [] });
    v4API.workboard.mockResolvedValue(SPACE_PAYLOAD);
    v4API.entities.list
      .mockResolvedValueOnce(PROJECTS)
      .mockResolvedValueOnce(AREAS)
      .mockResolvedValueOnce(PEOPLE);
    v4API.entities.update.mockResolvedValue({ data: {} });
    v4API.entities.create.mockResolvedValue({ data: { id: 'task-new' } });
    v4API.entities.createLink.mockResolvedValue({ data: {} });
    v4API.activityUpdates.create.mockResolvedValue({ data: {} });
  });

  it('loads the workboard route and shows filter chip counts from the API', async () => {
    renderWorkboard();

    expect(await screen.findByRole('heading', { name: 'Workboard' })).toBeInTheDocument();
    expect(v4API.workboard).toHaveBeenCalledWith({ group: 'space' });
    expect(screen.getByRole('button', { name: 'Mine 1' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Waiting on 1' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Blocked 1' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Apollo' })).toBeInTheDocument();
    expect(screen.getByText('Close contract')).toBeInTheDocument();
  });

  it('refetches when the group toggle and filter chips change', async () => {
    v4API.workboard
      .mockResolvedValueOnce(SPACE_PAYLOAD)
      .mockResolvedValueOnce(PERSON_PAYLOAD)
      .mockResolvedValueOnce(PERSON_PAYLOAD)
      .mockResolvedValue(SPACE_PAYLOAD);

    renderWorkboard();

    await screen.findByText('Close contract');
    fireEvent.click(screen.getByRole('button', { name: 'Person' }));

    await waitFor(() => expect(v4API.workboard).toHaveBeenNthCalledWith(2, { group: 'person' }));
    expect(await screen.findByRole('heading', { name: 'Operator' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Sam' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Overdue 1' }));
    await waitFor(() =>
      expect(v4API.workboard).toHaveBeenNthCalledWith(3, { group: 'person', state: ['overdue'] }),
    );

    const overdueChip = screen.getByRole('button', { name: 'Overdue 1' });
    expect(overdueChip.getAttribute('aria-pressed')).toBe('true');

    fireEvent.click(screen.getByRole('button', { name: 'Space' }));
    await waitFor(() =>
      expect(v4API.workboard).toHaveBeenNthCalledWith(4, { group: 'space', state: ['overdue'] }),
    );
    expect(within(screen.getByRole('main')).getByRole('heading', { name: 'Apollo' })).toBeInTheDocument();
  });

  it('updates status and due date inline without separate submit buttons', async () => {
    renderWorkboard();

    expect(await screen.findByText('Close contract')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Close contract status'), { target: { value: 'waiting' } });
    await waitFor(() =>
      expect(v4API.entities.update).toHaveBeenCalledWith('task-close-contract', { status: 'waiting' }),
    );

    fireEvent.change(screen.getByLabelText('Close contract due date'), { target: { value: '2026-08-01' } });
    await waitFor(() =>
      expect(v4API.entities.update).toHaveBeenCalledWith('task-close-contract', {
        due_at: '2026-08-01T12:00:00Z',
      }),
    );
  });

  it('executes compact affordance actions through the API client', async () => {
    renderWorkboard();

    expect(await screen.findByText('Close contract')).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: 'Mark Close contract done' })[0]);
    await waitFor(() => expect(v4API.entities.update).toHaveBeenCalledWith('task-close-contract', { status: 'done' }));

    fireEvent.change(screen.getByLabelText('Close contract owner'), { target: { value: 'person-sam' } });
    fireEvent.click(screen.getByRole('button', { name: 'Hand Close contract to owner' }));
    await waitFor(() =>
      expect(v4API.entities.createLink).toHaveBeenCalledWith(
        'task-close-contract',
        expect.objectContaining({
          target_id: 'person-sam',
          relationship_type: 'assigned_to',
        }),
      ),
    );

    fireEvent.click(screen.getByRole('button', { name: 'Move Close contract to another space' }));
    fireEvent.change(screen.getByLabelText('Close contract move to space'), { target: { value: 'space-orbit' } });
    fireEvent.click(screen.getByRole('button', { name: 'Move' }));
    await waitFor(() =>
      expect(v4API.entities.createLink).toHaveBeenCalledWith(
        'task-close-contract',
        expect.objectContaining({
          target_id: 'space-orbit',
          relationship_type: 'parent',
        }),
      ),
    );

    fireEvent.change(screen.getAllByLabelText('Close contract log update')[0], {
      target: { value: 'Sent revised draft.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Log update for Close contract' }));
    await waitFor(() =>
      expect(v4API.activityUpdates.create).toHaveBeenCalledWith('task-close-contract', 'Sent revised draft.'),
    );
  });

  it('shows nudge draft affordance on waiting-on commitments', async () => {
    v4API.commitments.nudgeDraft.mockResolvedValue({
      data: {
        draft: 'Hi Sam, following up on the security questionnaire from 28 Jun.',
        original_ask: 'Security questionnaire',
        committed_at: '2026-06-28',
        receipts: [],
        auto_sent: false,
      },
    });

    renderWorkboard();

    expect(await screen.findByText('Security questionnaire')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Draft nudge' })).toBeInTheDocument();
    expect(screen.queryAllByRole('button', { name: 'Draft nudge' })).toHaveLength(1);
  });
});
