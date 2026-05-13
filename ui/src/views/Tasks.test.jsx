import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Tasks from './Tasks';
import useStore from '../stores/useStore';

vi.mock('../stores/useStore');

const mockTasks = [
  {
    id: 't1',
    title: 'Draft kickoff notes',
    status: 'PENDING',
    priority: 'HIGH',
    due_date: '2026-05-15',
    project_id: 'p1',
  },
  {
    id: 't2',
    title: 'Ship drag UI',
    status: 'IN_PROGRESS',
    priority: 'MEDIUM',
    due_date: '2026-05-10',
    project_id: 'p2',
  },
  {
    id: 't3',
    title: 'Close sprint',
    status: 'DONE',
    priority: 'LOW',
    due_date: null,
    project_id: 'p1',
  },
];

const mockProjects = [
  { id: 'p1', name: 'Atlas' },
  { id: 'p2', name: 'Beacon' },
];

function renderTasks(overrides = {}) {
  const store = {
    tasks: mockTasks,
    projects: mockProjects,
    createTask: vi.fn().mockResolvedValue({ id: 'new-task' }),
    updateTask: vi.fn().mockResolvedValue({ id: 't1', status: 'IN_PROGRESS' }),
    deleteTask: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };

  vi.mocked(useStore).mockReturnValue(store);
  return { store, ...render(<Tasks />) };
}

describe('Tasks view', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('creates a task inline in the target column', async () => {
    const user = userEvent.setup();
    const { store } = renderTasks();

    await user.click(screen.getByRole('button', { name: /add task to pending/i }));
    const input = screen.getByPlaceholderText(/add a task/i);
    await user.type(input, 'Write release notes{Enter}');

    await waitFor(() => {
      expect(store.createTask).toHaveBeenCalledWith({
        title: 'Write release notes',
        status: 'PENDING',
      });
    });
  });

  it('updates task status when dropped into another column', async () => {
    const { store } = renderTasks();
    const card = screen.getByTestId('task-card-t1');
    const dropZone = screen.getByTestId('task-column-IN_PROGRESS');
    const dataTransfer = {
      effectAllowed: 'move',
      dropEffect: 'move',
      setData: vi.fn(),
      getData: vi.fn(() => 't1'),
    };

    fireEvent.dragStart(card, { dataTransfer });
    fireEvent.dragOver(dropZone, { dataTransfer });
    fireEvent.drop(dropZone, { dataTransfer });

    await waitFor(() => {
      expect(store.updateTask).toHaveBeenCalledWith('t1', { status: 'IN_PROGRESS' });
    });
  });

  it('filters by project and overdue chips', async () => {
    const user = userEvent.setup();
    renderTasks();

    await user.click(screen.getByRole('button', { name: /by project/i }));
    expect(screen.getByText('Draft kickoff notes')).toBeInTheDocument();
    expect(screen.getByText('Close sprint')).toBeInTheDocument();
    expect(screen.queryByText('Ship drag UI')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /^overdue$/i }));
    expect(screen.getByText('Ship drag UI')).toBeInTheDocument();
    expect(screen.queryByText('Draft kickoff notes')).not.toBeInTheDocument();
    expect(screen.queryByText('Close sprint')).not.toBeInTheDocument();
  });
});
