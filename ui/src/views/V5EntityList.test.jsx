import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { v4API } from '../api/v4Client';
import V5EntityList from './V5EntityList';

vi.mock('../api/v4Client', () => ({
  v4API: {
    entities: {
      list: vi.fn(),
    },
  },
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
        <V5EntityList type="task" />
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
        <V5EntityList type="project" />
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
        <V5EntityList type="task" />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/\(no title\)/)).toBeInTheDocument();
  });

  it('shows an error message when loading fails', async () => {
    v4API.entities.list.mockRejectedValue(new Error('Network down'));

    render(
      <MemoryRouter>
        <V5EntityList type="note" />
      </MemoryRouter>,
    );

    expect(await screen.findByRole('alert')).toHaveTextContent('Network down');
  });
});
