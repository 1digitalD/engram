/* eslint-disable no-unused-vars */
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { v4API } from '../api/v4Client';
import V4Search from './V4Search';

vi.mock('../api/v4Client', () => ({
  v4API: {
    search: vi.fn(),
  },
}));

describe('V4Search', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('searches with filters and links results to detail pages', async () => {
    v4API.search.mockResolvedValue({
      query: 'memory',
      mode: 'hybrid',
      results: [{
        entity: {
          id: 'p1',
          type: 'project',
          title: 'Memory Lookup',
          status: 'active',
          tags: [{ id: 't1', name: 'ops' }],
        },
        score: 0.91,
        match: { source: 'keyword', snippet: 'rollout memory lookup' },
      }],
    });

    render(
      <MemoryRouter>
        <V4Search />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText('Search query'), { target: { value: 'memory' } });
    fireEvent.change(screen.getByLabelText('Entity type'), { target: { value: 'project' } });
    fireEvent.change(screen.getByLabelText('Search mode'), { target: { value: 'keyword' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    await waitFor(() => expect(v4API.search).toHaveBeenCalledWith({
      q: 'memory',
      tag: undefined,
      type: 'project',
      mode: 'keyword',
      limit: 25,
    }));
    expect(await screen.findByRole('link', { name: /Memory Lookup/i })).toHaveAttribute('href', '/projects/p1');
    expect(screen.getByText('keyword match')).toBeInTheDocument();
    expect(screen.getByText('active')).toBeInTheDocument();
    expect(screen.getByText('#ops')).toBeInTheDocument();
    expect(screen.getByText('rollout memory lookup')).toBeInTheDocument();
  });

  it('replays URL-backed searches and preserves tag filters when searching again', async () => {
    v4API.search
      .mockResolvedValueOnce({
        query: 'memory',
        tag: 'ops',
        mode: 'hybrid',
        results: [],
      })
      .mockResolvedValueOnce({
        query: 'memory recall',
        tag: 'ops',
        mode: 'keyword',
        results: [],
      });

    render(
      <MemoryRouter initialEntries={['/search?q=memory&tag=ops&type=task&mode=keyword']}>
        <V4Search />
      </MemoryRouter>,
    );

    await waitFor(() => expect(v4API.search).toHaveBeenCalledWith({
      q: 'memory',
      tag: 'ops',
      type: 'task',
      mode: 'keyword',
      limit: 25,
    }));

    fireEvent.change(screen.getByLabelText('Search query'), { target: { value: 'memory recall' } });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    await waitFor(() => expect(v4API.search).toHaveBeenLastCalledWith({
      q: 'memory recall',
      tag: 'ops',
      type: 'task',
      mode: 'keyword',
      limit: 25,
    }));
  });

  it('shows an initial guidance state before any search runs', () => {
    render(
      <MemoryRouter>
        <V4Search />
      </MemoryRouter>,
    );

    expect(screen.getByText('Search by text or jump in from a tag.')).toBeInTheDocument();
  });
});
