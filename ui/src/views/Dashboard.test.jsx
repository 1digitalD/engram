import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Dashboard from './Dashboard';
import useStore from '../stores/useStore';
import { metricsAPI } from '../api/engram';

vi.mock('../components/notes/NoteCard', () => ({
  default: ({ note }) => <div data-testid="note-card">{note?.id}</div>,
}));

vi.mock('../stores/useStore');
vi.mock('../api/engram', () => ({
  metricsAPI: { health: vi.fn() },
}));

const baseHealth = {
  total_notes: 10,
  orphan_rate: 0.1,
  avg_links_per_note: 1.25,
  inbox_count: 3,
  archive_ratio: 0,
  tag_coverage: 0.5,
  active_projects: 1,
  stale_projects: 0,
  weekly_capture_rate: 4,
  weekly_capture_counts: [1, 2, 3, 4],
  link_proposals_pending: 0,
};

function renderDashboard() {
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>
  );
}

describe('Dashboard Knowledge Health', () => {
  beforeEach(() => {
    vi.mocked(metricsAPI.health).mockResolvedValue(baseHealth);
    vi.mocked(useStore).mockReturnValue({
      notes: [],
      projects: [],
      tasks: [],
      loading: false,
    });
  });

  it('renders Knowledge Health card with API metrics', async () => {
    renderDashboard();
    expect(screen.getByTestId('dashboard-health-card')).toBeInTheDocument();
    expect(screen.getByText('Knowledge Health')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId('health-orphan-rate')).toHaveTextContent('10%');
    });
    expect(screen.getByTestId('health-avg-links')).toHaveTextContent('1.25');
    expect(screen.getByTestId('health-capture-rate')).toHaveTextContent('4');
    expect(screen.getByTestId('health-inbox-count')).toHaveTextContent('3');

    const chart = screen.getByTestId('health-capture-chart');
    expect(chart.querySelectorAll('[data-count]')).toHaveLength(4);
  });

  it('colors inbox warn when count above 20', async () => {
    vi.mocked(metricsAPI.health).mockResolvedValue({
      ...baseHealth,
      inbox_count: 25,
    });
    renderDashboard();
    const inbox = await screen.findByTestId('health-inbox-count');
    expect(inbox).toHaveAttribute('data-tier', 'warn');
  });

  it('colors inbox bad when count above 50', async () => {
    vi.mocked(metricsAPI.health).mockResolvedValue({
      ...baseHealth,
      inbox_count: 51,
    });
    renderDashboard();
    const inbox = await screen.findByTestId('health-inbox-count');
    expect(inbox).toHaveAttribute('data-tier', 'bad');
  });

  it('colors orphan rate bad when very high', async () => {
    vi.mocked(metricsAPI.health).mockResolvedValue({
      ...baseHealth,
      orphan_rate: 0.5,
    });
    renderDashboard();
    const el = await screen.findByTestId('health-orphan-rate');
    expect(el).toHaveAttribute('data-tier', 'bad');
  });
});
