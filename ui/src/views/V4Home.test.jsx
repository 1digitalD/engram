import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import V4Home from './V4Home';
import { v4API } from '../api/v4Client';

vi.mock('../components/MarkdownContent', () => ({
  default: ({ content }) => content || null,
}));

vi.mock('../api/v4Client', () => ({
  v4API: {
    inbox: vi.fn(),
    today: vi.fn(),
    entities: {
      list: vi.fn(),
    },
  },
}));

describe('V4Home', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the control-plane sections from existing v4 payloads', async () => {
    v4API.inbox.mockResolvedValue({
      needs_review: [
        { id: 'n1', type: 'note', title: 'Needs review note', status: 'active', content: 'body' },
      ],
      recent: [
        { id: 'n2', type: 'note', title: 'Recent note', status: 'active', content: 'body' },
      ],
    });
    v4API.today.mockResolvedValue({
      overdue: [{ id: 't1', type: 'task', title: 'Overdue task', status: 'open' }],
      due_today: [{ id: 't2', type: 'task', title: 'Due today task', status: 'open' }],
      overdue_follow_ups: [{ id: 't1', type: 'task', title: 'Overdue task', status: 'open' }],
      follow_ups: [],
      blocked_tasks: [{ id: 't3', type: 'task', title: 'Blocked task', status: 'blocked' }],
      waiting_tasks: [{ id: 't4', type: 'task', title: 'Waiting task', status: 'waiting' }],
      projects_without_open_tasks: [{ id: 'p9', type: 'project', title: 'Needs next task', status: 'active' }],
      pending_suggestions: [{ id: 's1' }],
    });
    v4API.entities.list.mockResolvedValue({
      data: [
        { id: 'p1', type: 'project', title: 'Memory Lookup', status: 'active' },
      ],
    });

    render(
      <MemoryRouter>
        <V4Home />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Run the system, then capture into it.')).toBeInTheDocument();
    await waitFor(() => expect(v4API.inbox).toHaveBeenCalledWith({ limit: 8 }));
    expect(v4API.today).toHaveBeenCalled();
    expect(v4API.entities.list).toHaveBeenCalledWith({
      type: 'project',
      status: 'active',
      lifecycle: 'active',
      limit: 8,
    });

    expect(screen.getByText('Review queue')).toBeInTheDocument();
    expect(screen.getByText('Today')).toBeInTheDocument();
    expect(screen.getByText('Stuck')).toBeInTheDocument();
    expect(screen.getByText('Active projects')).toBeInTheDocument();
    expect(screen.getByText('Inbox flow')).toBeInTheDocument();
    expect(screen.getByText('Needs review note')).toBeInTheDocument();
    expect(screen.getByText('Overdue task')).toBeInTheDocument();
    expect(screen.getByText('Blocked task')).toBeInTheDocument();
    expect(screen.getByText('Needs next task')).toBeInTheDocument();
    expect(screen.getByText('Memory Lookup')).toBeInTheDocument();
    expect(screen.getByText(/1 note in review/i)).toBeInTheDocument();
    expect(screen.getByText(/4 items need attention/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /^4 need attention$/i })).toHaveTextContent('4');
    const heroStats = screen.getByText('in review').closest('div');
    expect(within(heroStats).getByRole('link', { name: /^1 in review$/i })).toHaveAttribute('href', '/suggestions');
  });
});
