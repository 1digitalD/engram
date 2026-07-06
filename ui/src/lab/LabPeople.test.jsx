import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LabPeople from './LabPeople';

vi.mock('../api/v4Client', () => ({
  v4API: {
    entities: {
      list: vi.fn(),
      detail: vi.fn(),
    },
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

import { v4API } from '../api/v4Client';

function renderWithRouter() {
  return render(
    <MemoryRouter initialEntries={['/lab/people']}>
      <LabPeople />
    </MemoryRouter>,
  );
}

describe('LabPeople', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows a loading state while fetching people', () => {
    v4API.entities.list.mockReturnValue(new Promise(() => {}));

    renderWithRouter();

    expect(screen.getByText('Loading people…')).toBeInTheDocument();
  });

  it('renders each person with open-task count, last-heard, and quiet flag from detail', async () => {
    v4API.entities.list.mockResolvedValue({
      data: [
        { id: 'p1', type: 'person', title: 'Alice', updated_at: '2026-07-06T10:00:00Z' },
        { id: 'p2', type: 'person', title: 'Bob', updated_at: '2026-07-05T10:00:00Z' },
      ],
    });
    v4API.entities.detail.mockImplementation((id) => {
      if (id === 'p1') {
        return Promise.resolve({
          pulse: { summary: { open_tasks: 3, quiet_tasks: 0 } },
          current_load: [
            { task: { id: 't1' }, last_heard_at: '2026-07-05T10:00:00Z' },
          ],
        });
      }
      return Promise.resolve({
        pulse: { summary: { open_tasks: 1, quiet_tasks: 1 } },
        current_load: [
          { task: { id: 't2' }, last_heard_at: '2026-06-20T10:00:00Z' },
        ],
      });
    });

    renderWithRouter();

    const aliceLink = await screen.findByRole('link', { name: /Alice/ });
    expect(aliceLink).toHaveAttribute('href', '/people/p1');
    expect(within(aliceLink).getByText(/3 open tasks/)).toBeInTheDocument();
    expect(within(aliceLink).getByText(/Last heard/)).toBeInTheDocument();

    const bobLink = screen.getByRole('link', { name: /Bob/ });
    expect(bobLink).toHaveAttribute('href', '/people/p2');
    expect(within(bobLink).getByText(/1 open task/)).toBeInTheDocument();
    expect(within(bobLink).getByText('Gone quiet')).toBeInTheDocument();
  });

  it('does not render any multi-select UI', async () => {
    v4API.entities.list.mockResolvedValue({
      data: [{ id: 'p1', type: 'person', title: 'Alice', updated_at: '2026-07-06T10:00:00Z' }],
    });
    v4API.entities.detail.mockResolvedValue({
      pulse: { summary: { open_tasks: 0, quiet_tasks: 0 } },
      current_load: [],
    });

    renderWithRouter();

    await screen.findByRole('link', { name: /Alice/ });
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /select/i })).not.toBeInTheDocument();
  });

  it('shows an empty hint when there are no people', async () => {
    v4API.entities.list.mockResolvedValue({ data: [] });

    renderWithRouter();

    await waitFor(() => expect(v4API.entities.list).toHaveBeenCalledWith({
      type: 'person',
      lifecycle: 'active',
      limit: 200,
      sort: 'updated_at',
      order: 'desc',
    }));
    expect(screen.getByText('No people yet. Mention someone in a capture to add them.')).toBeInTheDocument();
  });

  it('shows an error message when the list endpoint fails', async () => {
    v4API.entities.list.mockRejectedValue(new Error('Network error'));

    renderWithRouter();

    expect(await screen.findByText('Network error')).toBeInTheDocument();
  });

  it('still renders a person row when their detail payload fails', async () => {
    v4API.entities.list.mockResolvedValue({
      data: [{ id: 'p1', type: 'person', title: 'Alice', updated_at: '2026-07-06T10:00:00Z' }],
    });
    v4API.entities.detail.mockRejectedValue(new Error('Detail failed'));

    renderWithRouter();

    expect(await screen.findByRole('link', { name: /Alice/ })).toBeInTheDocument();
    expect(screen.getByText('Could not load summary')).toBeInTheDocument();
  });
});
