import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import V5Threads from './V5Threads';
import { v4API } from '../api/v4Client';

vi.mock('../api/v4Client', () => ({
  v4API: {
    threads: vi.fn(),
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

const sampleThreads = [
  {
    id: 'p1',
    type: 'project',
    name: 'HITL Pilot',
    attention_score: 88,
    attention_reasons: [{ key: 'status:blocked', label: 'blocked', weight: 35 }],
    last_activity_at: '2026-06-22T12:00:00Z',
    last_context: 'PR #847 review request',
    key_items: [{ id: 't1', type: 'task', name: 'Review PR', attention_score: 80 }],
  },
  {
    id: 'person1',
    type: 'person',
    name: 'Henry',
    attention_score: 42,
    attention_reasons: [{ key: 'staleness', label: 'no update in 6 days', weight: 10 }],
    last_activity_at: '2026-05-28T12:00:00Z',
    last_context: 'Loop in Finance',
    key_items: [],
  },
  {
    id: 'p2',
    type: 'project',
    name: 'Blog',
    attention_score: 8,
    attention_reasons: [],
    last_activity_at: '2026-06-01T12:00:00Z',
    last_context: 'last activity on Jun 01',
    key_items: [],
  },
];

describe('V5Threads', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders hot, warm, and ambient bands from the threads endpoint', async () => {
    v4API.threads.mockResolvedValue({ threads: sampleThreads, total_count: 3 });

    render(
      <MemoryRouter>
        <V5Threads />
      </MemoryRouter>,
    );

    await waitFor(() => expect(v4API.threads).toHaveBeenCalledWith({ rank: 'attention', limit: 200 }));
    expect(screen.getByText(/Threads · 3 active/i)).toBeInTheDocument();
    expect(screen.getByText('hot')).toBeInTheDocument();
    expect(screen.getByText('warm')).toBeInTheDocument();
    expect(screen.getByText('ambient')).toBeInTheDocument();
  });

  it('shows total count even when only a limited payload is loaded', async () => {
    v4API.threads.mockResolvedValue({ threads: sampleThreads.slice(0, 2), total_count: 25 });

    render(
      <MemoryRouter>
        <V5Threads />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Threads · 25 active/i)).toBeInTheDocument();
    expect(screen.getByText(/showing 2/i)).toBeInTheDocument();
  });
});
