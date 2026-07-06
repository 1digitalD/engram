import { MemoryRouter, Route, Routes } from 'react-router-dom';
import {
  beforeEach, describe, expect, it, vi,
} from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { v4API } from '../api/v4Client';
import LabEntityDetail from './LabEntityDetail';

vi.mock('../api/v4Client', () => ({
  v4API: {
    entities: {
      detail: vi.fn(),
      update: vi.fn(),
      createLink: vi.fn(),
    },
    search: vi.fn(),
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

const TASK_FIXTURE = {
  entity: {
    id: 'task-1',
    type: 'task',
    title: 'Write docs',
    status: 'open',
    due_at: null,
    follow_up_at: null,
    properties: {},
  },
  sections: [
    {
      key: 'project',
      title: 'Project',
      items: [],
    },
    {
      key: 'people',
      title: 'People',
      items: [
        {
          entity: { id: 'person-1', type: 'person', title: 'Henry' },
          relationship: { id: 'rel-1', relationship_type: 'assigned_to' },
          direction: 'outgoing',
        },
      ],
    },
    {
      key: 'blocking',
      title: 'Blocking / Blocked By',
      items: [],
    },
  ],
};

function renderDetail(path = '/lab/tasks/task-1') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/lab/:type/:id" element={<LabEntityDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('LabEntityDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.entities.detail.mockResolvedValue(TASK_FIXTURE);
    v4API.entities.update.mockResolvedValue({ data: TASK_FIXTURE.entity });
    v4API.entities.createLink.mockResolvedValue({ data: { id: 'rel-2' } });
    v4API.search.mockResolvedValue({ results: [] });
  });

  it('renders entity title and type', async () => {
    renderDetail();

    expect(await screen.findByRole('heading', { level: 1, name: 'Write docs' })).toBeInTheDocument();
    expect(screen.getByText('task')).toBeInTheDocument();
  });

  it('renders relationship sections and existing chips', async () => {
    renderDetail();

    expect(await screen.findByText('People')).toBeInTheDocument();
    expect(screen.getByText('Henry')).toBeInTheDocument();
  });

  it('persists status change via update entity API', async () => {
    renderDetail();
    await screen.findByRole('heading', { level: 1, name: 'Write docs' });

    const statusSelect = screen.getByLabelText('Status');
    await userEvent.selectOptions(statusSelect, 'in_progress');

    const saveButton = screen.getByRole('button', { name: 'Save changes' });
    await userEvent.click(saveButton);

    await waitFor(() => {
      expect(v4API.entities.update).toHaveBeenCalledWith('task-1', { status: 'in_progress' });
    });
    expect(v4API.entities.detail).toHaveBeenCalledTimes(2);
  });

  it('persists priority change as properties patch', async () => {
    renderDetail();
    await screen.findByRole('heading', { level: 1, name: 'Write docs' });

    const prioritySelect = screen.getByLabelText('Priority');
    await userEvent.selectOptions(prioritySelect, 'high');

    const saveButton = screen.getByRole('button', { name: 'Save changes' });
    await userEvent.click(saveButton);

    await waitFor(() => {
      expect(v4API.entities.update).toHaveBeenCalledWith('task-1', { properties: { priority: 'high' } });
    });
  });

  it('adds a relationship via the + add picker', async () => {
    v4API.search.mockResolvedValue({
      results: [
        {
          entity: { id: 'project-1', type: 'project', title: 'Docs project' },
          score: 1,
          match: { snippet: 'Docs project' },
        },
      ],
    });

    renderDetail();
    await screen.findByRole('heading', { level: 1, name: 'Write docs' });

    const addButtons = screen.getAllByRole('button', { name: 'Add relationship' });
    // The first section is "Project", whose default relationship type is parent.
    await userEvent.click(addButtons[0]);

    const searchInput = screen.getByLabelText('Search for an entity to link');
    await userEvent.type(searchInput, 'Docs');

    const resultItem = await screen.findByText('Docs project');
    await userEvent.click(resultItem);

    await waitFor(() => {
      expect(v4API.entities.createLink).toHaveBeenCalledWith('task-1', {
        target_id: 'project-1',
        relationship_type: 'parent',
      });
    });
  });

  it('renders activity updates without relationship chips', async () => {
    v4API.entities.detail.mockResolvedValue({
      ...TASK_FIXTURE,
      sections: [
        ...TASK_FIXTURE.sections,
        {
          key: 'activity_updates',
          title: 'Activity',
          items: [
            {
              id: 'update-1',
              title: 'Update: Pilot',
              content: 'Mary will review by Friday.',
              updated_at: '2026-06-22T14:00:00+00:00',
            },
          ],
        },
      ],
    });

    renderDetail();

    expect(await screen.findByText('Activity')).toBeInTheDocument();
    expect(screen.getByText('Update: Pilot')).toBeInTheDocument();
    expect(screen.getByText('Mary will review by Friday.')).toBeInTheDocument();
  });

  it('shows an error when detail load fails', async () => {
    v4API.entities.detail.mockRejectedValue(new Error('Server error'));
    renderDetail();

    expect(await screen.findByText('Server error')).toBeInTheDocument();
  });
});
