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
      overdue: [
        { id: 'od1', type: 'task', title: 'Overdue task', status: 'open', due_at: '2026-05-25T17:00:00Z' },
        { id: 'od2', type: 'task', title: 'Overdue inherited priority task', status: 'open', due_at: '2026-05-25T17:00:00Z', inherited_priority: 'urgent' },
      ],
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
      dependency_interventions: [
        {
          kind: 'blocked_by',
          label: 'Blocked by Security approval',
          entity: { id: 'b1', type: 'task', title: 'Blocked work', status: 'blocked' },
          blocker: { id: 'tdep1', type: 'task', title: 'Security approval', status: 'open' },
        },
        {
          kind: 'blocking',
          label: 'Blocking 1 open task',
          entity: { id: 'b2', type: 'task', title: 'Blocking workstream', status: 'open' },
          blocked_count: 1,
          blocked_preview: 'Launch checklist',
        },
      ],
      waiting_tasks: [{ id: 'w1', type: 'task', title: 'Waiting work', status: 'waiting' }],
      unscheduled_attention_tasks: [{
        id: 'ua1',
        type: 'task',
        title: 'Stale undated task',
        status: 'open',
        attention: { score: 43, level: 'medium', reasons: [{ key: 'staleness', label: 'no update in 14 days' }] },
      }],
      upcoming_due_tasks: [{ id: 'ud1', type: 'task', title: 'Due later this week', status: 'open', due_at: '2026-06-02T17:00:00Z' }],
      last_reviewed_at: null,
      reviewed_today: false,
      projects_without_open_tasks: [{ id: 'p1', type: 'project', title: 'Needs next task', status: 'active' }],
      recent_notes: [
        { id: 'n1', type: 'note', title: 'Recent note', status: 'active' },
        { id: 'n2', type: 'note', title: 'Captured blocker note', status: 'active', ai: { intent: 'blocker' } },
      ],
      pending_suggestions: [
        { id: 's1', source_entity_id: 'n2', suggestion_type: 'create_task', payload: { title: 'Suggested task' } },
        { id: 's2', source_entity_id: 'n2', suggestion_type: 'link_existing', payload: { title: 'Suggested project' } },
      ],
      delegations_quiet: [
        { id: 'dq1', type: 'task', title: 'Design GTM trigger doc', status: 'open', days_silent: 10, last_update: null },
      ],
      stale_projects: [
        { id: 'sp1', type: 'project', title: 'Quietly stalled project', status: 'active', stale_days: 16 },
      ],
      suggested_archival: [
        { id: 'sa1', type: 'project', title: 'Long-forgotten project', status: 'active', stale_days: 42 },
      ],
      new_since_yesterday_count: 3,
    });

    render(
      <MemoryRouter>
        <V4Today />
      </MemoryRouter>,
    );

    expect((await screen.findAllByText('Overdue task')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Overdue inherited priority task').length).toBeGreaterThan(0);
    expect(screen.getAllByText('~urgent').length).toBeGreaterThan(0);
    expect(screen.getByText('10 items need your attention today.')).toBeInTheDocument();
    expect(screen.getByText('Focus now')).toBeInTheDocument();
    expect(screen.getAllByText('overdue').length).toBeGreaterThan(0);
    expect(screen.getAllByText('due today').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Due today task').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Overdue follow-up').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Follow up today task').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Captured blocker note').length).toBeGreaterThan(0);
    expect(screen.getAllByText('captured blocker').length).toBeGreaterThan(0);
    expect(screen.getByText('Upcoming followup')).toBeInTheDocument();
    expect(screen.getAllByText('Blocked work').length).toBeGreaterThan(0);
    expect(screen.getByText('high · blocked')).toBeInTheDocument();
    expect(screen.getByText('Dependency interventions')).toBeInTheDocument();
    expect(screen.getByText('Blocked by Security approval')).toBeInTheDocument();
    expect(screen.getByText('Blocking workstream')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Security approval/i })).toHaveAttribute('href', '/tasks/tdep1');
    expect(screen.getByText('Waiting work')).toBeInTheDocument();
    expect(screen.getAllByText('Stale undated task').length).toBeGreaterThan(0);
    expect(screen.getByText('Your actions')).toBeInTheDocument();
    expect(screen.getByText(/Deadlines ahead/)).toBeInTheDocument();
    expect(screen.getByText('Due later this week')).toBeInTheDocument();
    expect(screen.getByText('Mark day reviewed')).toBeInTheDocument();
    expect(screen.getByText('Needs next task')).toBeInTheDocument();
    expect(screen.getByText(/Stale projects/)).toBeInTheDocument();
    expect(screen.getByText('Quietly stalled project')).toBeInTheDocument();
    expect(screen.getByText('no activity in 16 days')).toBeInTheDocument();
    expect(screen.getByText('Long-forgotten project')).toBeInTheDocument();
    expect(screen.getByText('no activity in 42 days')).toBeInTheDocument();
    expect(screen.getByText('consider archiving')).toBeInTheDocument();
    expect(screen.getByText('3 new since yesterday')).toBeInTheDocument();
    expect(screen.getByText('Recent note')).toBeInTheDocument();
    expect(screen.getByText('Delegations needing a nudge')).toBeInTheDocument();
    expect(screen.getByText('Design GTM trigger doc')).toBeInTheDocument();
    expect(screen.getByText('10 days silent')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /Overdue task/i })[0]).toHaveAttribute('href', '/tasks/od1');
    // Entity type is a glyph (aria-labelled icon), not a full-name pill.
    expect(screen.getAllByRole('img', { name: 'task' }).length).toBeGreaterThan(0);
    expect(v4API.today).toHaveBeenCalled();
  });
});
