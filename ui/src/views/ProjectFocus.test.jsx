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

  it('with parent area shows rollup confirmation, then archives with rollup and navigates to area', async () => {
    const user = userEvent.setup();
    const { updateProject, loadAll } = renderFocus({
      projects: [{ id: 'p1', name: 'Alpha', is_archived: false, area_id: 'a1', color: '#abc' }],
      areas: [{ id: 'a1', name: 'Work', is_archived: false }],
    });

    await user.click(screen.getByTestId('complete-project-btn'));
    expect(screen.getByTestId('rollup-confirm-copy')).toBeInTheDocument();
    expect(screen.getByTestId('rollup-confirm-copy')).toHaveTextContent('Work');

    await user.click(screen.getByTestId('rollup-confirm-submit'));

    await waitFor(() => {
      expect(updateProject).toHaveBeenCalledWith('p1', {
        is_archived: true,
        rollup_confirmed: true,
      });
    });
    expect(loadAll).toHaveBeenCalled();
    expect(mockNavigate).toHaveBeenCalledWith('/areas/a1');
  });

  it('without parent area archives directly and navigates to projects list', async () => {
    const user = userEvent.setup();
    const { updateProject, loadAll } = renderFocus({
      projects: [{ id: 'p1', name: 'Solo', is_archived: false, area_id: null, color: null }],
    });

    await user.click(screen.getByTestId('complete-project-btn'));
    await user.click(screen.getByTestId('archive-only-submit'));

    await waitFor(() => {
      expect(updateProject).toHaveBeenCalledWith('p1', { is_archived: true });
    });
    expect(loadAll).toHaveBeenCalled();
    expect(mockNavigate).toHaveBeenCalledWith('/projects');
  });
});
