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
    entities: { update: vi.fn(), get: vi.fn() },
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
      overdue_follow_ups: [
        { id: 'od1', type: 'task', title: 'Overdue task', status: 'open', due_at: '2026-05-25T17:00:00Z' },
        { id: 'of1', type: 'task', title: 'Overdue follow-up', status: 'open' },
      ],
      follow_ups: [{ id: 't1', type: 'task', title: 'Follow up today task', status: 'open' }],
      upcoming_follow_ups: [{ id: 'uf1', type: 'task', title: 'Upcoming followup', status: 'open' }],
      blocked_tasks: [{
        id: 'b1',
        type: 'task',
        title: 'Blocked work',
        status: 'blocked',
        attention: { score: 56, level: 'high', reasons: [{ key: 'status:blocked', label: 'blocked' }] },
      }],
      waiting_tasks: [{ id: 'w1', type: 'task', title: 'Waiting work', status: 'waiting' }],
      projects_without_open_tasks: [{ id: 'p1', type: 'project', title: 'Needs next task', status: 'active' }],
      recent_notes: [
        { id: 'n1', type: 'note', title: 'Recent note', status: 'active' },
        { id: 'n2', type: 'note', title: 'Captured blocker note', status: 'active', ai: { intent: 'blocker' } },
      ],
      pending_suggestions: [
        { id: 's1', source_entity_id: 'n2', suggestion_type: 'create_task', payload: { title: 'Suggested task' } },
        { id: 's2', source_entity_id: 'n2', suggestion_type: 'link_existing', payload: { title: 'Suggested project' } },
      ],
    });

    render(
      <MemoryRouter>
        <V4Today />
      </MemoryRouter>,
    );

    expect((await screen.findAllByText('Overdue task')).length).toBeGreaterThan(0);
    expect(screen.getByText('7 items need your attention today.')).toBeInTheDocument();
    expect(screen.getByText('Focus now')).toBeInTheDocument();
    expect(screen.getAllByText('overdue').length).toBeGreaterThan(0);
    expect(screen.getAllByText('due today').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Due today task').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Overdue follow-up').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Follow up today task').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Captured blocker note').length).toBeGreaterThan(0);
    expect(screen.getAllByText('captured blocker').length).toBeGreaterThan(0);
    expect(screen.getByText('Upcoming followup')).toBeInTheDocument();
    expect(screen.getByText('Blocked work')).toBeInTheDocument();
    expect(screen.getByText('high · blocked')).toBeInTheDocument();
    expect(screen.getByText('Waiting work')).toBeInTheDocument();
    expect(screen.getByText('Needs next task')).toBeInTheDocument();
    expect(screen.getByText('Recent note')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /Overdue task/i })[0]).toHaveAttribute('href', '/tasks/od1');
    expect(v4API.today).toHaveBeenCalled();
  });
});
