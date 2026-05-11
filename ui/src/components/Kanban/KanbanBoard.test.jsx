import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import KanbanBoard from './KanbanBoard';
import useStore from '../../stores/useStore';

vi.mock('../../stores/useStore');

const mockTasks = [
  { id: 't1', title: 'Task 1', status: 'PENDING', project_id: 'p1', area_id: null, tag_ids: ['tag1'] },
  { id: 't2', title: 'Task 2', status: 'PENDING', project_id: null, area_id: 'a1', tag_ids: [] },
  { id: 't3', title: 'Task 3', status: 'IN_PROGRESS', project_id: 'p1', area_id: 'a1', tag_ids: ['tag1', 'tag2'] },
  { id: 't4', title: 'Task 4', status: 'DONE', project_id: 'p2', area_id: null, tag_ids: [] },
  { id: 't5', title: 'Task 5', status: 'PENDING', project_id: 'p2', area_id: 'a2', tag_ids: ['tag2'] },
];

const mockProjects = [
  { id: 'p1', name: 'Project Alpha' },
  { id: 'p2', name: 'Project Beta' },
];

const mockAreas = [
  { id: 'a1', name: 'Area One' },
  { id: 'a2', name: 'Area Two' },
];

const mockTags = [
  { id: 'tag1', name: 'urgent' },
  { id: 'tag2', name: 'backend' },
];

const mockStore = {
  tasks: mockTasks,
  projects: mockProjects,
  areas: mockAreas,
  tags: mockTags,
  updateTask: vi.fn().mockResolvedValue({ data: { id: 't1', status: 'IN_PROGRESS' } }),
};

const renderKanban = () => {
  vi.mocked(useStore).mockReturnValue({ ...mockStore });
  return render(<KanbanBoard />);
};

describe('KanbanBoard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the Kanban board header', () => {
    renderKanban();
    expect(screen.getByText('Kanban Board')).toBeInTheDocument();
  });

  it('renders three columns for each status', () => {
    renderKanban();
    expect(screen.getByTestId('kanban-column-PENDING')).toBeInTheDocument();
    expect(screen.getByTestId('kanban-column-IN_PROGRESS')).toBeInTheDocument();
    expect(screen.getByTestId('kanban-column-DONE')).toBeInTheDocument();
  });

  it('shows column labels', () => {
    renderKanban();
    expect(screen.getByText('Pending')).toBeInTheDocument();
    expect(screen.getByText('In Progress')).toBeInTheDocument();
    expect(screen.getByText('Done')).toBeInTheDocument();
  });

  it('displays correct column counts', () => {
    renderKanban();
    expect(screen.getByTestId('column-count-PENDING')).toHaveTextContent('3');
    expect(screen.getByTestId('column-count-IN_PROGRESS')).toHaveTextContent('1');
    expect(screen.getByTestId('column-count-DONE')).toHaveTextContent('1');
  });

  it('renders task cards in the correct columns', () => {
    renderKanban();
    expect(screen.getByTestId('kanban-card-t1')).toBeInTheDocument();
    expect(screen.getByTestId('kanban-card-t2')).toBeInTheDocument();
    expect(screen.getByTestId('kanban-card-t3')).toBeInTheDocument();
    expect(screen.getByTestId('kanban-card-t4')).toBeInTheDocument();
    expect(screen.getByTestId('kanban-card-t5')).toBeInTheDocument();
  });

  it('shows task titles on cards', () => {
    renderKanban();
    expect(screen.getByText('Task 1')).toBeInTheDocument();
    expect(screen.getByText('Task 2')).toBeInTheDocument();
    expect(screen.getByText('Task 3')).toBeInTheDocument();
  });

  it('shows project names on cards when task has a project', () => {
    renderKanban();
    expect(screen.getByTestId('card-project-t1')).toHaveTextContent('Project Alpha');
    expect(screen.getByTestId('card-project-t4')).toHaveTextContent('Project Beta');
  });

  it('shows area names on cards when task has an area', () => {
    renderKanban();
    expect(screen.getByTestId('card-area-t2')).toHaveTextContent('Area One');
    expect(screen.getByTestId('card-area-t3')).toHaveTextContent('Area One');
  });

  it('shows tag badges on cards when task has tags', () => {
    renderKanban();
    const urgentBadges = screen.getAllByText('urgent');
    expect(urgentBadges.length).toBeGreaterThanOrEqual(1);
    const backendBadges = screen.getAllByText('backend');
    expect(backendBadges.length).toBeGreaterThanOrEqual(1);
  });

  it('shows total task count in subtitle', () => {
    renderKanban();
    expect(screen.getByText('5 tasks')).toBeInTheDocument();
  });

  it('opens filter bar when filter button is clicked', async () => {
    const user = userEvent.setup();
    renderKanban();

    await user.click(screen.getByTestId('toggle-filters'));
    expect(screen.getByTestId('filter-bar')).toBeInTheDocument();
  });

  it('shows filter dropdowns when filter bar is open', async () => {
    const user = userEvent.setup();
    renderKanban();

    await user.click(screen.getByTestId('toggle-filters'));
    expect(screen.getByTestId('filter-project')).toBeInTheDocument();
    expect(screen.getByTestId('filter-area')).toBeInTheDocument();
    expect(screen.getByTestId('filter-tag')).toBeInTheDocument();
  });

  it('filters tasks by project', async () => {
    const user = userEvent.setup();
    renderKanban();

    await user.click(screen.getByTestId('toggle-filters'));
    await user.selectOptions(screen.getByTestId('filter-project'), 'p1');

    expect(screen.getByTestId('column-count-PENDING')).toHaveTextContent('1');
    expect(screen.getByTestId('column-count-IN_PROGRESS')).toHaveTextContent('1');
    expect(screen.getByTestId('column-count-DONE')).toHaveTextContent('0');

    expect(screen.queryByTestId('kanban-card-t2')).not.toBeInTheDocument();
    expect(screen.queryByTestId('kanban-card-t4')).not.toBeInTheDocument();
    expect(screen.queryByTestId('kanban-card-t5')).not.toBeInTheDocument();
  });

  it('filters tasks by area', async () => {
    const user = userEvent.setup();
    renderKanban();

    await user.click(screen.getByTestId('toggle-filters'));
    await user.selectOptions(screen.getByTestId('filter-area'), 'a1');

    expect(screen.getByTestId('column-count-PENDING')).toHaveTextContent('1');
    expect(screen.getByTestId('column-count-IN_PROGRESS')).toHaveTextContent('1');

    expect(screen.queryByTestId('kanban-card-t1')).not.toBeInTheDocument();
    expect(screen.queryByTestId('kanban-card-t4')).not.toBeInTheDocument();
    expect(screen.queryByTestId('kanban-card-t5')).not.toBeInTheDocument();
  });

  it('filters tasks by tag', async () => {
    const user = userEvent.setup();
    renderKanban();

    await user.click(screen.getByTestId('toggle-filters'));
    await user.selectOptions(screen.getByTestId('filter-tag'), 'tag2');

    expect(screen.getByTestId('column-count-IN_PROGRESS')).toHaveTextContent('1');
    expect(screen.getByTestId('column-count-PENDING')).toHaveTextContent('1');

    expect(screen.queryByTestId('kanban-card-t1')).not.toBeInTheDocument();
    expect(screen.queryByTestId('kanban-card-t2')).not.toBeInTheDocument();
    expect(screen.queryByTestId('kanban-card-t4')).not.toBeInTheDocument();
  });

  it('clears filters when clear button is clicked', async () => {
    const user = userEvent.setup();
    renderKanban();

    await user.click(screen.getByTestId('toggle-filters'));
    await user.selectOptions(screen.getByTestId('filter-project'), 'p1');

    expect(screen.getByTestId('column-count-PENDING')).toHaveTextContent('1');

    await user.click(screen.getByTestId('clear-filters'));

    expect(screen.getByTestId('column-count-PENDING')).toHaveTextContent('3');
    expect(screen.getByTestId('column-count-IN_PROGRESS')).toHaveTextContent('1');
    expect(screen.getByTestId('column-count-DONE')).toHaveTextContent('1');
  });

  it('renders draggable cards with sortable attributes', () => {
    renderKanban();
    const draggableCards = document.querySelectorAll('[role="button"][aria-roledescription="sortable"]');
    expect(draggableCards.length).toBe(5);
  });

  it('renders droppable columns', () => {
    renderKanban();
    expect(screen.getByTestId('column-body-PENDING')).toBeInTheDocument();
    expect(screen.getByTestId('column-body-IN_PROGRESS')).toBeInTheDocument();
    expect(screen.getByTestId('column-body-DONE')).toBeInTheDocument();
  });

  it('updates subtitle count when filters are applied', async () => {
    const user = userEvent.setup();
    renderKanban();

    expect(screen.getByText('5 tasks')).toBeInTheDocument();

    await user.click(screen.getByTestId('toggle-filters'));
    await user.selectOptions(screen.getByTestId('filter-project'), 'p1');

    expect(screen.getByText('2 tasks')).toBeInTheDocument();
  });
});
