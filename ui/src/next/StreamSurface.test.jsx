import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import NextApp from './NextApp';

vi.mock('../api/v4Client', () => ({
  v4API: {
    reports: {
      list: vi.fn(),
    },
    entities: {
      list: vi.fn(),
    },
    capture: vi.fn(),
    search: vi.fn(),
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

import { v4API } from '../api/v4Client';

const STREAM_PAYLOAD = {
  data: [
    {
      id: 'note-3',
      type: 'note',
      title: 'Recap after partner call',
      content: 'Recap after partner call',
      created_at: '2026-07-08T17:45:00Z',
      updated_at: '2026-07-08T17:45:00Z',
    },
    {
      id: 'note-2',
      type: 'note',
      title: 'Inbox cleanup',
      content: 'Inbox cleanup',
      created_at: '2026-07-08T08:10:00Z',
      updated_at: '2026-07-08T08:10:00Z',
    },
    {
      id: 'note-1',
      type: 'note',
      title: 'Morning standup',
      content: 'Morning standup',
      created_at: '2026-07-07T16:05:00Z',
      updated_at: '2026-07-07T16:05:00Z',
    },
  ],
};

const JULY7_LOCAL_TIME = new Intl.DateTimeFormat('en-US', {
  hour: 'numeric',
  minute: '2-digit',
}).format(new Date('2026-07-07T16:05:00Z'));

function renderStream() {
  return render(
    <MemoryRouter initialEntries={['/next/stream']}>
      <Routes>
        <Route path="/next/*" element={<NextApp />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('StreamSurface', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.reports.list.mockResolvedValue({ data: [], meta: { total: 0 } });
    v4API.entities.list.mockResolvedValue(STREAM_PAYLOAD);
    v4API.capture.mockResolvedValue({});
    v4API.search.mockResolvedValue({ data: [] });
  });

  it('loads the stream route and requests recent notes', async () => {
    renderStream();

    expect(await screen.findByRole('heading', { name: 'Stream' })).toBeInTheDocument();
    expect(v4API.entities.list).toHaveBeenCalledWith({
      type: 'note',
      limit: 100,
      sort: 'created_at',
      order: 'desc',
      lifecycle: 'active',
    });
    expect(screen.getByRole('link', { name: 'Stream' })).toBeInTheDocument();
  });

  it('groups captures by day and shows note vocabulary badge', async () => {
    renderStream();

    const july8 = await screen.findByRole('heading', { name: 'Jul 8, 2026' });
    const july7 = screen.getByRole('heading', { name: 'Jul 7, 2026' });

    const july8Section = july8.closest('section');
    const july7Section = july7.closest('section');

    expect(july8Section).not.toBeNull();
    expect(july7Section).not.toBeNull();

    expect(within(july8Section).getByText('Recap after partner call')).toBeInTheDocument();
    expect(within(july8Section).getByText('Inbox cleanup')).toBeInTheDocument();
    expect(within(july8Section).getAllByText('N')).toHaveLength(2);
    expect(within(july8Section).getAllByText('Stream entry')).toHaveLength(2);

    expect(within(july7Section).getByText('Morning standup')).toBeInTheDocument();
    expect(within(july7Section).getByText(JULY7_LOCAL_TIME)).toBeInTheDocument();
  });
});
