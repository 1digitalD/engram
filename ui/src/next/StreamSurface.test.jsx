import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import NextApp from './NextApp';

vi.mock('../api/v4Client', () => ({
  v4API: {
    reports: {
      list: vi.fn().mockResolvedValue({ data: [], meta: { total: 0 } }),
    },
    agentActivity: vi.fn().mockResolvedValue({ data: [], meta: { total: 0, counts: {} } }),
    entities: {
      list: vi.fn(),
      get: vi.fn(),
      createLink: vi.fn(),
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
      content: '**Blocked** on infra review',
      created_at: '2026-07-07T16:05:00Z',
      updated_at: '2026-07-07T16:05:00Z',
    },
  ],
};

const TARGETS = { data: [{ id: 'space-apollo', title: 'Apollo' }] };

function renderStream(initialEntry = '/stream') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/*" element={<NextApp />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('StreamSurface', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.reports.list.mockResolvedValue({ data: [], meta: { total: 0 } });
    v4API.entities.list
      .mockResolvedValueOnce(STREAM_PAYLOAD)
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce(TARGETS)
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: [] });
    v4API.entities.createLink.mockResolvedValue({ data: {} });
    v4API.capture.mockResolvedValue({});
    v4API.search.mockResolvedValue({ data: [] });
  });

  it('loads stream entries and groups them by local day', async () => {
    renderStream();

    expect(await screen.findByRole('heading', { name: 'Stream' })).toBeInTheDocument();
    expect(v4API.entities.list).toHaveBeenCalledWith({
      type: 'note',
      lifecycle: 'active',
      limit: 100,
    });
    expect(screen.getByRole('link', { name: 'Stream' })).toBeInTheDocument();

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
    expect(within(july7Section).getByText('Blocked')).toBeInTheDocument();
    expect(within(july7Section).queryByRole('time')).not.toBeInTheDocument();
  });

  it('renders markdown in stream entry bodies', async () => {
    renderStream();

    const july7 = await screen.findByRole('heading', { name: 'Jul 7, 2026' });
    const july7Section = july7.closest('section');
    expect(within(july7Section).getByText('Blocked').tagName).toBe('STRONG');
  });

  it('attaches a stream entry to a selected target', async () => {
    renderStream();

    expect(await screen.findByText('Morning standup')).toBeInTheDocument();

    const row = screen.getByText('Morning standup').closest('li');
    expect(row).not.toBeNull();

    fireEvent.change(within(row).getByLabelText('Attach Morning standup'), {
      target: { value: 'space-apollo' },
    });
    fireEvent.click(within(row).getByRole('button', { name: 'Attach entry' }));

    await waitFor(() =>
      expect(v4API.entities.createLink).toHaveBeenCalledWith('note-1', {
        target_id: 'space-apollo',
        relationship_type: 'related',
      }),
    );
  });

  it('fetches a highlighted note when it is outside the first page of stream results', async () => {
    v4API.entities.list
      .mockResolvedValueOnce(STREAM_PAYLOAD)
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce(TARGETS)
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: [] });
    v4API.entities.get.mockResolvedValue({
      data: {
        id: 'note-old',
        type: 'note',
        title: 'Older capture',
        content: 'Older capture',
        created_at: '2026-01-01T12:00:00Z',
        updated_at: '2026-01-01T12:00:00Z',
      },
    });

    renderStream('/stream?note=note-old');

    expect(await screen.findByText('Older capture')).toBeInTheDocument();
    expect(v4API.entities.get).toHaveBeenCalledWith('note-old');
  });
});
