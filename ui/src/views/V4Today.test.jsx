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
  },
}));

describe('V4Today', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders today cockpit sections with detail links', async () => {
    v4API.today.mockResolvedValue({
      follow_ups: [{ id: 't1', type: 'task', title: 'Follow up', status: 'open' }],
      blocked_or_waiting_tasks: [{ id: 't2', type: 'task', title: 'Waiting', status: 'waiting' }],
      projects_without_open_tasks: [{ id: 'p1', type: 'project', title: 'Needs next task', status: 'active' }],
      recent_notes: [{ id: 'n1', type: 'note', title: 'Recent note', status: 'active' }],
      pending_suggestions: [{ id: 's1', suggestion_type: 'create_task', payload: { title: 'Suggested task' } }],
    });

    render(
      <MemoryRouter>
        <V4Today />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Follow up')).toBeInTheDocument();
    expect(screen.getByText('Waiting')).toBeInTheDocument();
    expect(screen.getByText('Needs next task')).toBeInTheDocument();
    expect(screen.getByText('Recent note')).toBeInTheDocument();
    expect(screen.getByText('Suggested task')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Follow up/i })).toHaveAttribute('href', '/tasks/t1');
    expect(v4API.today).toHaveBeenCalled();
  });
});
