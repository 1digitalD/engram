import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import NextApp from './NextApp';

vi.mock('../api/v4Client', () => ({
  v4API: {
    reports: { list: vi.fn().mockResolvedValue({ data: [], meta: { total: 0 } }) },
    agentActivity: vi.fn().mockResolvedValue({ data: [], meta: { total: 0, counts: {} } }),
    capture: vi.fn(),
    search: vi.fn(),
    today: vi.fn().mockResolvedValue({
      needs_you: [],
      in_motion: [],
      counts: { needs_you: 0, in_motion: 0 },
    }),
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

import { v4API } from '../api/v4Client';

describe('NextShell recall', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.search.mockResolvedValue({
      data: [
        {
          id: 'space-apollo',
          type: 'project',
          title: 'Apollo renewal',
          status: 'active',
          searchSnippet: 'Finish line in August',
        },
      ],
    });
  });

  it('shows live recall results while typing in the omni-bar', async () => {
    render(
      <MemoryRouter initialEntries={['/today']}>
        <Routes>
          <Route path="/*" element={<NextApp />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText('Recall search'), { target: { value: 'apollo' } });

    await waitFor(() => expect(v4API.search).toHaveBeenCalledWith({ q: 'apollo', limit: 12 }));
    expect(await screen.findByText('Apollo renewal')).toBeInTheDocument();
    expect(screen.getByText('Finish line in August')).toBeInTheDocument();
  });
});
