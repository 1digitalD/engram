import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import V5Memory from './V5Memory';

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
  ],
  next_offset: null,
};

describe('V5Memory', () => {
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

    const entityTypeGroup = screen.getByRole('group', { name: /Filter by entity type/i });
    const actorGroup = screen.getByRole('group', { name: /Filter by actor/i });

    expect(entityTypeGroup).toBeInTheDocument();
    expect(actorGroup).toBeInTheDocument();

    expect(entityTypeGroup.querySelectorAll('button').length).toBeGreaterThanOrEqual(2);
    expect(actorGroup.querySelectorAll('button').length).toBeGreaterThanOrEqual(2);
  });

  it('renders a search input', () => {
    renderWithRouter(<V5Memory previewData={previewData} />);
    expect(screen.getByRole('searchbox')).toBeInTheDocument();
  });

  it('shows an empty hint when no events are provided', () => {
    renderWithRouter(<V5Memory previewData={{ events: [], next_offset: null }} />);
    expect(screen.getByText(/Nothing in your memory yet/i)).toBeInTheDocument();
  });

  it('filters events by search query', () => {
    renderWithRouter(<V5Memory previewData={previewData} />);

    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'timeline' } });

    expect(screen.getByText(/Created task "Ship timeline"/i)).toBeInTheDocument();
    expect(screen.queryByText(/I processed this entity/i)).not.toBeInTheDocument();
  });
});
