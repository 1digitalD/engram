import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from '../App';
import { v4API } from '../api/v4Client';

vi.mock('../api/v4Client', () => ({
  v4API: {
    capture: vi.fn(),
    entities: {
      list: vi.fn(),
      create: vi.fn(),
      get: vi.fn(),
      pin: vi.fn(),
      unpin: vi.fn(),
    },
    today: vi.fn(),
    summary: vi.fn(),
    search: vi.fn(),
    threads: vi.fn(),
    workboard: vi.fn(),
    reports: {
      list: vi.fn().mockResolvedValue({ data: [], meta: { total: 0 } }),
    },
    metrics: {
      trust: vi.fn().mockResolvedValue({ correction_rate: null }),
    },
    suggestions: {
      list: vi.fn().mockResolvedValue({ data: [], meta: { total: 0 } }),
      accept: vi.fn(),
      dismiss: vi.fn(),
    },
  },
}));

vi.mock('../views/V5Now', () => ({ default: () => <main data-testid="legacy-now">Now view</main> }));
vi.mock('../next/TodaySurface', () => ({ default: () => <main data-testid="v6-today">Today surface</main> }));

describe('TC-60 shell routing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.today.mockResolvedValue({
      needs_you: [],
      in_motion: [],
      counts: { needs_you: 0, in_motion: 0 },
    });
    v4API.summary.mockResolvedValue({ today_count: 0, threads_count: 0 });
    v4API.reports.list.mockResolvedValue({ data: [], meta: { total: 0 } });
    v4API.metrics.trust.mockResolvedValue({ correction_rate: null });
  });

  it('serves v6 NextApp at / and redirects to /today', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('v6-today')).toBeInTheDocument();
  });

  it('serves the legacy V5 shell at /legacy/now', async () => {
    render(
      <MemoryRouter initialEntries={['/legacy/now']}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('legacy-now')).toBeInTheDocument();
  });

  it('redirects /next/today to /today', async () => {
    render(
      <MemoryRouter initialEntries={['/next/today']}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('v6-today')).toBeInTheDocument();
  });
});
