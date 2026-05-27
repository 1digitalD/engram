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
        entity: { id: 'p1', type: 'project', title: 'Memory Lookup' },
        score: 0.91,
        match: { snippet: 'rollout memory lookup' },
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
    expect(screen.getByText('rollout memory lookup')).toBeInTheDocument();
  });
});
