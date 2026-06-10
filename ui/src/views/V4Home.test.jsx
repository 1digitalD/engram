import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import V4Home from './V4Home';
import { v4API } from '../api/v4Client';

vi.mock('../api/v4Client', () => ({
  v4API: {
    summary: vi.fn(),
  },
}));

describe('V4Home', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders hero stats and workflow shortcuts from /summary', async () => {
    v4API.summary.mockResolvedValue({
      inbox_count: 1,
      today_count: 4,
      suggestions_count: 1,
      last_reviewed_at: null,
      reviewed_today: false,
      stale_projects_count: 2,
    });

    render(
      <MemoryRouter>
        <V4Home />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Run the system, then capture into it.')).toBeInTheDocument();
    await waitFor(() => expect(v4API.summary).toHaveBeenCalled());

    const heroStats = screen.getByText('in review').closest('div');
    expect(within(heroStats).getByRole('link', { name: /^1 in review$/i })).toHaveAttribute('href', '/suggestions');
    expect(within(heroStats).getByRole('link', { name: /^4 need attention$/i })).toHaveAttribute('href', '/today');
    expect(within(heroStats).getByText('No')).toBeInTheDocument();
    expect(within(heroStats).getByText('day reviewed')).toBeInTheDocument();
    expect(within(heroStats).getByRole('link', { name: /^2 stale projects$/i })).toHaveAttribute('href', '/today');

    expect(screen.getByRole('link', { name: /^Capture/ })).toHaveAttribute('href', '/inbox');
    expect(screen.getByText(/1 note in review/i)).toBeInTheDocument();
    expect(screen.getByText(/4 items need attention/i)).toBeInTheDocument();
  });

  it('shows day reviewed as Yes when reviewed_today is true', async () => {
    v4API.summary.mockResolvedValue({
      inbox_count: 0,
      today_count: 0,
      suggestions_count: 0,
      last_reviewed_at: '2026-06-10T12:00:00Z',
      reviewed_today: true,
    });

    render(
      <MemoryRouter>
        <V4Home />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Yes')).toBeInTheDocument();
  });
});
