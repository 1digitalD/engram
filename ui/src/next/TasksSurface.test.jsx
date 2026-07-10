import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import NextApp from './NextApp';

vi.mock('../api/v4Client', () => ({
  v4API: {
    reports: {
      list: vi.fn().mockResolvedValue({ data: [], meta: { total: 0 } }),
    },
    agentActivity: vi.fn().mockResolvedValue({ data: [], meta: { total: 0, counts: {} } }),
    taskBoard: vi.fn(),
    capture: vi.fn(),
    search: vi.fn(),
    entities: {
      list: vi.fn(),
      update: vi.fn(),
      createLink: vi.fn(),
    },
    activityUpdates: {
      create: vi.fn(),
    },
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

import { v4API } from '../api/v4Client';

const BOARD_PAYLOAD = {
  data: {
    groups: [
      {
        key: 'project-apollo',
        label: 'Apollo',
        kind: 'project',
        entity_id: 'project-apollo',
        counts: { total: 1 },
        items: [
          {
            id: 'task-close-contract',
            title: 'Close contract',
            status: 'open',
            due_at: '2026-07-07T12:00:00Z',
            follow_up_at: '2026-07-12T12:00:00Z',
            created_at: '2026-07-01T12:00:00Z',
            owner: { id: 'person-sam', title: 'Sam' },
            space: { id: 'project-apollo', title: 'Apollo', type: 'project' },
          },
        ],
      },
    ],
  },
  meta: {
    total: 1,
    counts: {
      by_status: {
        open: 1,
        in_progress: 0,
        waiting: 0,
        blocked: 0,
        done: 0,
        cancelled: 0,
      },
    },
    sort: 'created_at',
    order: 'desc',
  },
};

const PROJECTS = { data: [{ id: 'project-apollo', title: 'Apollo' }] };
const AREAS = { data: [] };
const PEOPLE = { data: [{ id: 'person-sam', title: 'Sam' }] };

function renderTasks() {
  return render(
    <MemoryRouter initialEntries={['/tasks']}>
      <Routes>
        <Route path="/*" element={<NextApp />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('TasksSurface', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.reports.list.mockResolvedValue({ data: [], meta: { total: 0 } });
    v4API.capture.mockResolvedValue({});
    v4API.search.mockResolvedValue({ data: [] });
    v4API.taskBoard.mockResolvedValue(BOARD_PAYLOAD);
    v4API.entities.list
      .mockResolvedValueOnce(PROJECTS)
      .mockResolvedValueOnce(AREAS)
      .mockResolvedValueOnce(PEOPLE);
    v4API.entities.update.mockResolvedValue({ data: {} });
    v4API.entities.createLink.mockResolvedValue({ data: {} });
    v4API.activityUpdates.create.mockResolvedValue({ data: {} });
  });

  it('loads tasks grouped by project with default open status filters', async () => {
    renderTasks();

    expect(await screen.findByRole('heading', { name: 'Tasks' })).toBeInTheDocument();
    expect(v4API.taskBoard).toHaveBeenCalledWith({
      status: 'open,in_progress,waiting,blocked',
      sort: 'created_at',
      order: 'desc',
    });
    expect(screen.getByRole('heading', { name: 'Apollo' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Close contract' })).toHaveAttribute(
      'href',
      '/commitments/task-close-contract',
    );
    expect(screen.getByText('9d')).toBeInTheDocument();
  });

  it('refetches when status chips and sort controls change', async () => {
    v4API.taskBoard.mockResolvedValueOnce(BOARD_PAYLOAD).mockResolvedValue(BOARD_PAYLOAD);
    renderTasks();

    await screen.findByText('Close contract');
    fireEvent.click(screen.getByRole('button', { name: 'Done 0' }));

    await waitFor(() =>
      expect(v4API.taskBoard).toHaveBeenLastCalledWith({
        status: 'open,in_progress,waiting,blocked,done',
        sort: 'created_at',
        order: 'desc',
      }),
    );

    fireEvent.change(screen.getByLabelText('Sort tasks'), { target: { value: 'follow_up_at' } });
    await waitFor(() =>
      expect(v4API.taskBoard).toHaveBeenLastCalledWith({
        status: 'open,in_progress,waiting,blocked,done',
        sort: 'follow_up_at',
        order: 'asc',
      }),
    );
  });

  it('marks a task done from the checkbox', async () => {
    renderTasks();

    expect(await screen.findByText('Close contract')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Mark Close contract done' }));

    await waitFor(() =>
      expect(v4API.entities.update).toHaveBeenCalledWith('task-close-contract', { status: 'done' }),
    );
  });

  it('reopens a task to its prior status after unchecking done', async () => {
    renderTasks();

    expect(await screen.findByText('Close contract')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Close contract status'), { target: { value: 'waiting' } });
    await waitFor(() =>
      expect(v4API.entities.update).toHaveBeenCalledWith('task-close-contract', { status: 'waiting' }),
    );

    fireEvent.click(screen.getByRole('checkbox', { name: 'Mark Close contract done' }));
    await waitFor(() =>
      expect(v4API.entities.update).toHaveBeenCalledWith('task-close-contract', { status: 'done' }),
    );

    fireEvent.click(screen.getByRole('checkbox', { name: 'Mark Close contract done' }));
    await waitFor(() =>
      expect(v4API.entities.update).toHaveBeenCalledWith('task-close-contract', { status: 'waiting' }),
    );
  });

  it('logs an update from the expandable update field', async () => {
    renderTasks();

    const field = await screen.findByLabelText('Close contract log update');
    fireEvent.focus(field);
    fireEvent.change(field, { target: { value: 'Sent reminder' } });
    fireEvent.click(screen.getByRole('button', { name: 'Log update for Close contract' }));

    await waitFor(() =>
      expect(v4API.activityUpdates.create).toHaveBeenCalledWith('task-close-contract', 'Sent reminder'),
    );
  });
});
