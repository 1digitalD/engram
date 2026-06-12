import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import V4Home from './V4Home';
import { v4API } from '../api/v4Client';

vi.mock('../api/v4Client', () => ({
  v4API: {
    summary: vi.fn(),
    brief: vi.fn(),
    metrics: {
      trust: vi.fn(),
    },
  },
}));

const TRUST = {
  window_days: 30,
  suggestions: { accepted: 3, dismissed: 9, pending: 4, acceptance_rate: 0.25 },
  agent_actions: { total: 120, by_type: {} },
  corrections: { total: 14 },
  correction_rate: 0.117,
  weekly: [],
};

const BRIEF = {
  narrative: 'CS1 review is the hinge of the day.',
  generated_at: '2026-06-11T06:00:00+00:00',
  model: 'test',
  items: [
    {
      entity_id: 't1',
      entity_type: 'task',
      title: 'Ship CS1 contract review',
      status: 'open',
      why_now: 'Blocking two downstream tasks; due today.',
      urgency: 5,
    },
    {
      entity_id: 'p1',
      entity_type: 'project',
      title: 'Agent Platform',
      status: 'active',
      why_now: 'Roadmap decision pending since Monday.',
      urgency: 3,
    },
  ],
};

describe('V4Home', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.summary.mockResolvedValue({ inbox_count: 1, today_count: 4, reviewed_today: false, stale_projects_count: 2 });
    v4API.brief.mockResolvedValue({ brief: BRIEF, from_cache: true });
    v4API.metrics.trust.mockResolvedValue(TRUST);
  });

  it('renders the daily brief items with why-now reasons and entity links', async () => {
    render(
      <MemoryRouter>
        <V4Home />
      </MemoryRouter>,
    );

    expect(await screen.findByText('CS1 review is the hinge of the day.')).toBeInTheDocument();
    const item = screen.getByRole('link', { name: 'Ship CS1 contract review' });
    expect(item).toHaveAttribute('href', '/tasks/t1');
    expect(screen.getByText('Blocking two downstream tasks; due today.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Agent Platform' })).toHaveAttribute('href', '/projects/p1');
  });

  it('renders the trust strip from /metrics/trust', async () => {
    render(
      <MemoryRouter>
        <V4Home />
      </MemoryRouter>,
    );

    await waitFor(() => expect(v4API.metrics.trust).toHaveBeenCalled());
    expect(screen.getByText('pending review').previousSibling).toHaveTextContent('4');
    expect(screen.getByText(/suggestions accepted/)).toBeInTheDocument();
    expect(screen.getByText('25%')).toBeInTheDocument();
    expect(screen.getByText('12%')).toBeInTheDocument();
  });

  it('forces a brief regeneration from the refresh button', async () => {
    render(
      <MemoryRouter>
        <V4Home />
      </MemoryRouter>,
    );
    await screen.findByText('CS1 review is the hinge of the day.');

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Refresh brief' }));
    await waitFor(() => expect(v4API.brief).toHaveBeenCalledWith({ force: 1 }));
  });

  it('shows an empty state when no brief exists', async () => {
    v4API.brief.mockResolvedValue({ brief: null, from_cache: false });
    render(
      <MemoryRouter>
        <V4Home />
      </MemoryRouter>,
    );
    expect(await screen.findByText(/No brief yet/)).toBeInTheDocument();
  });
});
