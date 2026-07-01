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
