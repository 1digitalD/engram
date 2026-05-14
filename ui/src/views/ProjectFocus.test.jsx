import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import ProjectFocus from './ProjectFocus';
import useStore from '../stores/useStore';

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams: () => ({ id: 'p1' }),
  };
});

vi.mock('../stores/useStore');

function renderFocus(storeProps) {
  const updateProject = storeProps.updateProject ?? vi.fn().mockResolvedValue({
    project: { id: 'p1', is_archived: true },
    rollup: null,
  });
  const loadAll = storeProps.loadAll ?? vi.fn().mockResolvedValue(undefined);

  vi.mocked(useStore).mockReturnValue({
    projects: storeProps.projects,
    notes: storeProps.notes ?? [],
    tasks: storeProps.tasks ?? [],
    people: storeProps.people ?? [],
    areas: storeProps.areas ?? [],
    updateProject,
    loadAll,
  });

  return {
    updateProject,
    loadAll,
    ...render(
      <MemoryRouter initialEntries={['/projects/p1']}>
        <Routes>
          <Route path="/projects/:id" element={<ProjectFocus />} />
        </Routes>
      </MemoryRouter>
    ),
  };
}

describe('ProjectFocus complete project', () => {
  beforeEach(() => {
    mockNavigate.mockClear();
  });

  it('renders the redesigned header, progress section, and notes tab rows', () => {
    renderFocus({
      projects: [{
        id: 'p1',
        title: 'Apollo',
        description: 'Ship the redesign',
        status: 'in_progress',
        due_date: '2026-05-20',
        area_id: 'a1',
        color: '#abc',
      }],
      areas: [{ id: 'a1', title: 'Work', is_archived: false }],
      notes: [{
        id: 'n1',
        project_id: 'p1',
        raw_text: '# Launch plan',
        updated_at: '2026-05-11T10:00:00Z',
        tag_names: ['launch', 'design'],
      }],
      tasks: [
        { id: 't1', project_id: 'p1', title: 'Write brief', status: 'done' },
        { id: 't2', project_id: 'p1', title: 'Build UI', status: 'in_progress' },
        { id: 't3', project_id: 'p1', title: 'QA pass', status: 'pending' },
      ],
    });

    expect(screen.getByText('Work')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Apollo' })).toBeInTheDocument();
    expect(screen.getByText('Ship the redesign')).toBeInTheDocument();
    expect(screen.getByText(/Due May/)).toBeInTheDocument();
    expect(screen.getByText('Done')).toBeInTheDocument();
    expect(screen.getAllByText('In Progress').length).toBeGreaterThan(0);
    expect(screen.getByText('Pending')).toBeInTheDocument();
    expect(screen.getByText('33%')).toBeInTheDocument();
    expect(screen.getByText('Launch plan')).toBeInTheDocument();
    expect(screen.getByText('launch')).toBeInTheDocument();
    expect(screen.getByText('design')).toBeInTheDocument();
  });

  it('switches between tabs and shows compact task and people content', async () => {
    const user = userEvent.setup();
    renderFocus({
      projects: [{ id: 'p1', title: 'Alpha', is_archived: false, area_id: 'a1', color: '#abc' }],
      areas: [{ id: 'a1', title: 'Work', is_archived: false }],
      notes: [{ id: 'n1', project_id: 'p1', raw_text: 'Meeting notes', person_id: 'person-1' }],
      tasks: [
        { id: 't1', project_id: 'p1', title: 'Done task', status: 'done' },
        { id: 't2', project_id: 'p1', title: 'Active task', status: 'in_progress' },
        { id: 't3', project_id: 'p1', title: 'Planned task', status: 'pending' },
      ],
      people: [{ id: 'person-1', title: 'Ada Lovelace', role: 'Designer' }],
    });

    await user.click(screen.getByRole('button', { name: 'Tasks' }));
    expect(screen.getByText('Done task')).toBeInTheDocument();
    expect(screen.getByText('Active task')).toBeInTheDocument();
    expect(screen.getByText('Planned task')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'People' }));
    expect(screen.getByText('Ada Lovelace')).toBeInTheDocument();
    expect(screen.getByText('Designer')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Connections' }));
    expect(screen.getByPlaceholderText('Filter entities...')).toBeInTheDocument();
  });

  it('marks the project done and shows the rolling up to completed transition', async () => {
    const user = userEvent.setup();
    let resolveUpdate;
    const updateProjectMock = vi.fn().mockImplementation(() => new Promise((resolve) => {
      resolveUpdate = resolve;
    }));

    const { updateProject } = renderFocus({
      projects: [{ id: 'p1', title: 'Solo', is_archived: false, area_id: null, color: null, status: 'ACTIVE' }],
      updateProject: updateProjectMock,
    });

    await user.click(screen.getByTestId('complete-project-btn'));
    expect(screen.getByRole('button', { name: 'Rolling up...' })).toBeDisabled();

    resolveUpdate({ project: { id: 'p1', status: 'completed' }, rollup: null });

    await waitFor(() => {
      expect(updateProject).toHaveBeenCalledWith('p1', { status: 'completed' });
    });
    await waitFor(() => {
      expect(screen.queryByTestId('complete-project-btn')).not.toBeInTheDocument();
      expect(screen.getAllByText('Completed').length).toBeGreaterThanOrEqual(1);
    });
  });
});
