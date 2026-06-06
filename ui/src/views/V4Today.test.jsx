/* eslint-disable no-unused-vars */
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { v4API } from '../api/v4Client';
import V4Today from './V4Today';

vi.mock('../api/v4Client', () => ({
  v4API: {
    today: vi.fn(),
    entities: { update: vi.fn() },
  },
}));

describe('V4Today', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders today cockpit sections with detail links', async () => {
    v4API.today.mockResolvedValue({
      overdue: [{ id: 'od1', type: 'task', title: 'Overdue task', status: 'open', due_at: '2026-05-25T17:00:00Z' }],
      due_today: [{ id: 'dt1', type: 'task', title: 'Due today task', status: 'open', due_at: '2026-05-27T17:00:00Z' }],
      overdue_follow_ups: [{ id: 'of1', type: 'task', title: 'Overdue follow-up', status: 'open' }],
      follow_ups: [{ id: 't1', type: 'task', title: 'Follow up today task', status: 'open' }],
      upcoming_follow_ups: [{ id: 'uf1', type: 'task', title: 'Upcoming followup', status: 'open' }],
      blocked_tasks: [{ id: 'b1', type: 'task', title: 'Blocked work', status: 'blocked' }],
      waiting_tasks: [{ id: 'w1', type: 'task', title: 'Waiting work', status: 'waiting' }],
      projects_without_open_tasks: [{ id: 'p1', type: 'project', title: 'Needs next task', status: 'active' }],
      recent_notes: [{ id: 'n1', type: 'note', title: 'Recent note', status: 'active' }],
      pending_suggestions: [{ id: 's1', suggestion_type: 'create_task', payload: { title: 'Suggested task' } }],
    });

    render(
      <MemoryRouter>
        <V4Today />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Overdue task')).toBeInTheDocument();
    expect(screen.getByText('Due today task')).toBeInTheDocument();
    expect(screen.getByText('Overdue follow-up')).toBeInTheDocument();
    expect(screen.getByText('Follow up today task')).toBeInTheDocument();
    expect(screen.getByText('Upcoming followup')).toBeInTheDocument();
    expect(screen.getByText('Blocked work')).toBeInTheDocument();
    expect(screen.getByText('Waiting work')).toBeInTheDocument();
    expect(screen.getByText('Needs next task')).toBeInTheDocument();
    expect(screen.getByText('Recent note')).toBeInTheDocument();
    expect(screen.getByText('Suggested task')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Overdue task/i })).toHaveAttribute('href', '/tasks/od1');
    expect(v4API.today).toHaveBeenCalled();
  });
});
