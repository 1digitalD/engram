import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { v4API } from '../api/v4Client';
import { CaptureProvider } from '../context/CaptureContext';
import V5CaptureSheet from './V5CaptureSheet';
import V5EntityList from './V5EntityList';

vi.mock('../api/v4Client', () => ({
  v4API: {
    entities: {
      list: vi.fn(),
    },
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

describe('V5EntityList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders a list of entities and links to detail', async () => {
    v4API.entities.list.mockResolvedValue({
      data: [
        { id: 't1', type: 'task', title: 'Ship it', status: 'open' },
        { id: 't2', type: 'task', title: 'Tighten evals', status: 'in_progress' },
      ],
    });

    render(
      <MemoryRouter>
        <CaptureProvider>
                  <V5EntityList type="task" />
        </CaptureProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('link', { name: /Ship it/i })).toHaveAttribute('href', '/tasks/t1');
    expect(screen.getByRole('link', { name: /Tighten evals/i })).toHaveAttribute('href', '/tasks/t2');
  });

  it('shows project and area context on task cards', async () => {
    v4API.entities.list.mockResolvedValue({
      data: [
        {
          id: 't1',
          type: 'task',
          title: 'Ship rollout',
          status: 'open',
          projects: [{ id: 'p1', title: 'Memory Lookup' }],
          areas: [{ id: 'a1', title: 'Execution' }],
        },
      ],
    });

    render(
      <MemoryRouter>
        <CaptureProvider>
          <V5EntityList type="task" />
        </CaptureProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('link', { name: /Memory Lookup/i })).toHaveAttribute('href', '/projects/p1');
    expect(screen.getByRole('link', { name: /Execution/i })).toHaveAttribute('href', '/areas/a1');
  });

  it('shows open task badge on project rows', async () => {
    v4API.entities.list.mockResolvedValue({
      data: [
        {
          id: 'p1',
          type: 'project',
          title: 'Memory Lookup',
          status: 'active',
          task_counts: { open: 3, total: 5 },
        },
      ],
    });

    render(
      <MemoryRouter>
        <CaptureProvider>
          <V5EntityList type="project" />
        </CaptureProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText('3 open')).toBeInTheDocument();
  });

  it('shows linked count summary on area rows', async () => {
    v4API.entities.list.mockResolvedValue({
      data: [
        {
          id: 'a1',
          type: 'area',
          title: 'Execution',
          status: 'active',
          linked_counts: { tasks: 3, projects: 2, notes: 0 },
        },
      ],
    });

    render(
      <MemoryRouter>
        <CaptureProvider>
          <V5EntityList type="area" />
        </CaptureProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText('3 tasks · 2 projects')).toBeInTheDocument();
  });

  it('shows parent area chip on project rows', async () => {
    v4API.entities.list.mockResolvedValue({
      data: [
        {
          id: 'p1',
          type: 'project',
          title: 'Memory Lookup',
          status: 'active',
          areas: [{ id: 'a1', title: 'Execution' }],
        },
      ],
    });

    render(
      <MemoryRouter>
        <CaptureProvider>
          <V5EntityList type="project" />
        </CaptureProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('link', { name: /Execution/i })).toHaveAttribute('href', '/areas/a1');
  });

  it('filters entities by search query', async () => {
    v4API.entities.list.mockResolvedValue({
      data: [
        { id: 'p1', type: 'project', title: 'Agent Memory', status: 'active' },
        { id: 'p2', type: 'project', title: 'Billing Migration', status: 'active' },
      ],
    });

    render(
      <MemoryRouter>
        <CaptureProvider>
                  <V5EntityList type="project" />
        </CaptureProvider>
      </MemoryRouter>,
    );

    await screen.findByRole('link', { name: /Agent Memory/i });
    fireEvent.change(screen.getByLabelText('Search Projects'), { target: { value: 'billing' } });

    await waitFor(() => {
      expect(screen.queryByRole('link', { name: /Agent Memory/i })).not.toBeInTheDocument();
    });
    expect(screen.getByRole('link', { name: /Billing Migration/i })).toBeInTheDocument();
  });

  it('shows a placeholder for missing titles', async () => {
    v4API.entities.list.mockResolvedValue({
      data: [
        { id: 'task-null', type: 'task', title: null, status: 'open' },
      ],
    });

    render(
      <MemoryRouter>
        <CaptureProvider>
                  <V5EntityList type="task" />
        </CaptureProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText(/\(no title\)/)).toBeInTheDocument();
  });

  it('shows an error message when loading fails', async () => {
    v4API.entities.list.mockRejectedValue(new Error('Network down'));

    render(
      <MemoryRouter>
        <CaptureProvider>
                  <V5EntityList type="note" />
        </CaptureProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('alert')).toHaveTextContent('Network down');
  });

  it.each([
    ['note', 'No notes yet. Capture something from the quick capture sheet.'],
    ['task', 'No tasks yet. Capture a task to get started.'],
    ['project', 'No projects yet. Capture a project idea to get started.'],
    ['area', 'No areas yet. Capture an area to group projects and tasks.'],
    ['person', 'No people yet. Mention someone in a capture to add them.'],
    ['resource', 'No resources yet. Save a link, file, or reference in a capture.'],
  ])('opens the capture sheet from the %s list New button', async (type, hint) => {
    v4API.entities.list.mockResolvedValue({ data: [] });

    render(
      <MemoryRouter>
        <CaptureProvider>
          <V5EntityList type={type} />
          <V5CaptureSheet />
        </CaptureProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText(hint)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: new RegExp(`Capture ${type}`, 'i') }));
    expect(await screen.findByLabelText('Capture text')).toBeInTheDocument();
  });
});
