import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { v4API } from '../api/v4Client';
import V5Recall from './V5Recall';

vi.mock('../api/v4Client', () => ({
  v4API: {
    search: vi.fn(),
  },
}));

describe('V5Recall', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.search.mockResolvedValue({ data: [] });
  });

  it('does not render when closed', () => {
    render(
      <MemoryRouter>
        <V5Recall open={false} onClose={vi.fn()} />
      </MemoryRouter>,
    );

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders the search palette when open', () => {
    render(
      <MemoryRouter>
        <V5Recall open onClose={vi.fn()} />
      </MemoryRouter>,
    );

    expect(screen.getByRole('dialog', { name: 'Recall search' })).toBeInTheDocument();
    expect(screen.getByLabelText('Search terms')).toBeInTheDocument();
  });

  it('searches and navigates to a result on enter', async () => {
    const onClose = vi.fn();
    v4API.search.mockResolvedValue({
      data: [
        { id: 'p1', type: 'project', title: 'Agent Memory', status: 'active' },
      ],
    });

    render(
      <MemoryRouter>
        <V5Recall open onClose={onClose} />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText('Search terms'), { target: { value: 'agent' } });

    await waitFor(() => expect(v4API.search).toHaveBeenCalledWith({ q: 'agent', limit: 24 }));
    expect(await screen.findByRole('option', { name: /Agent Memory/i })).toBeInTheDocument();

    fireEvent.keyDown(screen.getByLabelText('Search terms'), { key: 'Enter' });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('closes on escape', async () => {
    const onClose = vi.fn();
    render(
      <MemoryRouter>
        <V5Recall open onClose={onClose} />
      </MemoryRouter>,
    );

    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });
});
