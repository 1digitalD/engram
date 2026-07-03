import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import V5Memory from './V5Memory';
import { v4API } from '../api/v4Client';

vi.mock('../api/v4Client', () => ({
  v4API: {
    timeline: vi.fn(),
    entities: {
      detail: vi.fn(),
      events: vi.fn(),
      canonical: vi.fn(),
    },
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

function renderWithRouter(ui) {
  return render(
    <MemoryRouter initialEntries={['/memory']}>
      {ui}
    </MemoryRouter>,
  );
}

const previewData = {
  events: [
    {
      id: 'e1',
      entity_id: 'task-1',
      entity_type: 'task',
      event_type: 'created',
      occurred_at: new Date().toISOString(),
      actor: 'user',
      narration: 'Created task "Ship timeline".',
      thread_id: 'project-1',
    },
    {
      id: 'e2',
      entity_id: 'note-1',
      entity_type: 'note',
      event_type: 'ai_processed',
      occurred_at: new Date(Date.now() - 86400000).toISOString(),
      actor: 'agent:v4-capture',
      narration: 'I processed this entity.',
      thread_id: 'note-1',
    },
    {
      id: 'e3',
      entity_id: 'task-1',
      entity_type: 'task',
      event_type: 'activity_update_added',
      occurred_at: new Date(Date.now() - 3600000).toISOString(),
      actor: 'user',
      narration: 'Updated task status.',
      thread_id: 'project-1',
    },
  ],
  next_offset: null,
};

describe('V5Memory', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders date headers and event cards', () => {
    renderWithRouter(<V5Memory previewData={previewData} />);
    expect(screen.getByRole('heading', { name: /Memory/i })).toBeInTheDocument();
    expect(screen.getByText('Today')).toBeInTheDocument();
    expect(screen.getByText('Yesterday')).toBeInTheDocument();
    expect(screen.getByText(/Created task "Ship timeline"/i)).toBeInTheDocument();
    expect(screen.getByText(/I processed this entity/i)).toBeInTheDocument();
  });

  it('renders filter chips for entity type and actor', () => {
    renderWithRouter(<V5Memory previewData={previewData} />);
    expect(screen.getByRole('group', { name: /Filter by entity type/i })).toBeInTheDocument();
    expect(screen.getByRole('group', { name: /Filter by actor/i })).toBeInTheDocument();
  });

  it('does not expose a thread ID filter by default', () => {
    renderWithRouter(<V5Memory previewData={previewData} />);
    expect(screen.queryByRole('textbox', { name: /Filter by thread ID/i })).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/Thread ID filter/i)).not.toBeInTheDocument();
  });

  it('renders a search input and client-side search filter', () => {
    renderWithRouter(<V5Memory previewData={previewData} />);
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'timeline' } });
    expect(screen.getByText(/Created task "Ship timeline"/i)).toBeInTheDocument();
    expect(screen.queryByText(/I processed this entity/i)).not.toBeInTheDocument();
  });

  it('toggles hiding routine bookkeeping narrations client-side', () => {
    renderWithRouter(<V5Memory previewData={previewData} />);
    expect(screen.getByText(/Updated task status/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Hide routine updates/i }));
    expect(screen.queryByText(/Updated task status/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Created task "Ship timeline"/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Hide routine updates/i }));
    expect(screen.getByText(/Updated task status/i)).toBeInTheDocument();
  });

  it('shows an empty hint when no events are provided', () => {
    renderWithRouter(<V5Memory previewData={{ events: [], next_offset: null }} />);
    expect(screen.getByText(/Capture something first/i)).toBeInTheDocument();
  });

  it('passes the agent prefix filter through to the API', async () => {
    v4API.timeline.mockResolvedValue({ events: [], next_offset: null });

    renderWithRouter(<V5Memory />);

    await waitFor(() => expect(v4API.timeline).toHaveBeenCalledWith({ limit: 50, offset: 0 }));
    fireEvent.click(screen.getByRole('button', { name: 'Agent' }));

    await waitFor(() => expect(v4API.timeline).toHaveBeenCalledWith({
      limit: 50,
      offset: 0,
      actor: 'agent:',
    }));
  });

  it('renders a clickable citation link when an event has a source note', async () => {
    const user = userEvent.setup();
    const dataWithSourceNote = {
      events: [
        {
          id: 'e3',
          entity_id: 'task-1',
          entity_type: 'task',
          event_type: 'ai_updated',
          occurred_at: new Date().toISOString(),
          actor: 'agent:v4-extraction',
          narration: 'Created task note.',
          thread_id: 'project-1',
          source_note_id: 'note-source',
        },
      ],
      next_offset: null,
    };

    v4API.entities.detail.mockResolvedValue({
      entity: { id: 'note-source', type: 'note', title: 'Source note', status: 'active' },
      sections: [],
    });
    v4API.entities.events.mockResolvedValue({ data: [] });
    v4API.entities.canonical.mockResolvedValue({ canonical: '' });

    renderWithRouter(<V5Memory previewData={dataWithSourceNote} />);

    const link = screen.getByRole('button', { name: /Open source note/i });
    await user.click(link);

    expect(v4API.entities.detail).toHaveBeenCalledWith('note-source');
    expect(screen.getByRole('dialog', { name: 'Citation' })).toBeInTheDocument();
  });
});
