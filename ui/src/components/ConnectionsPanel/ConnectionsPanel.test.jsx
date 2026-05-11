import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import ConnectionsPanel from './ConnectionsPanel';
import { connectionsAPI } from '../../api/engram';

vi.mock('../../api/engram', () => ({
  connectionsAPI: { forEntity: vi.fn() },
}));

function renderPanel(entityId, refreshKey = 0) {
  return render(
    <MemoryRouter>
      <ConnectionsPanel entityId={entityId} refreshKey={refreshKey} />
    </MemoryRouter>
  );
}

describe('ConnectionsPanel', () => {
  beforeEach(() => {
    vi.mocked(connectionsAPI.forEntity).mockReset();
  });

  it('shows loading state initially', () => {
    vi.mocked(connectionsAPI.forEntity).mockReturnValue(new Promise(() => {}));
    renderPanel('entity-1');
    expect(screen.getByTestId('connections-panel')).toBeInTheDocument();
    expect(screen.getByText(/Loading connections/)).toBeInTheDocument();
  });

  it('shows empty state when no connections', async () => {
    vi.mocked(connectionsAPI.forEntity).mockResolvedValue({ outgoing: [], incoming: [] });
    renderPanel('entity-1');
    await waitFor(() => {
      expect(screen.getByText('No connections yet.')).toBeInTheDocument();
    });
  });

  it('shows panel with connections when data loads', async () => {
    vi.mocked(connectionsAPI.forEntity).mockResolvedValue({
      outgoing: [
        {
          id: 'link-1',
          dst_id: 'note-1',
          dst_entity: { id: 'note-1', type: 'note', title: 'Related Note' },
          link_type: 'related',
        },
      ],
      incoming: [],
    });
    renderPanel('entity-1');
    await waitFor(() => {
      expect(screen.getByTestId('connections-panel')).toBeInTheDocument();
      expect(screen.getByText('Connections')).toBeInTheDocument();
    });
    expect(screen.getByText('Related Note')).toBeInTheDocument();
  });

  it('lists related entities grouped by type', async () => {
    vi.mocked(connectionsAPI.forEntity).mockResolvedValue({
      outgoing: [
        {
          id: 'link-1',
          dst_id: 'note-1',
          dst_entity: { id: 'note-1', type: 'note', title: 'Note A' },
          link_type: 'related',
        },
        {
          id: 'link-2',
          dst_id: 'note-2',
          dst_entity: { id: 'note-2', type: 'note', title: 'Note B' },
          link_type: 'related',
        },
        {
          id: 'link-3',
          dst_id: 'proj-1',
          dst_entity: { id: 'proj-1', type: 'project', name: 'Project X' },
          link_type: 'related',
        },
      ],
      incoming: [
        {
          id: 'link-4',
          src_id: 'area-1',
          src_entity: { id: 'area-1', type: 'area', name: 'Area Y' },
          link_type: 'related',
        },
        {
          id: 'link-5',
          src_id: 'person-1',
          src_entity: { id: 'person-1', type: 'person', name: 'Jane Doe' },
          link_type: 'mentions',
        },
      ],
    });
    renderPanel('entity-1');

    await waitFor(() => {
      expect(screen.getByText('Note A')).toBeInTheDocument();
    });

    expect(screen.getByText('Note B')).toBeInTheDocument();
    expect(screen.getByText('Project X')).toBeInTheDocument();
    expect(screen.getByText('Area Y')).toBeInTheDocument();
    expect(screen.getByText('Jane Doe')).toBeInTheDocument();

    expect(screen.getByTestId('connections-group-note')).toBeInTheDocument();
    expect(screen.getByTestId('connections-group-project')).toBeInTheDocument();
    expect(screen.getByTestId('connections-group-area')).toBeInTheDocument();
    expect(screen.getByTestId('connections-group-person')).toBeInTheDocument();
  });

  it('clicking a related entity navigates to it', async () => {
    vi.mocked(connectionsAPI.forEntity).mockResolvedValue({
      outgoing: [
        {
          id: 'link-1',
          dst_id: 'note-1',
          dst_entity: { id: 'note-1', type: 'note', title: 'Click Me' },
          link_type: 'related',
        },
        {
          id: 'link-2',
          dst_id: 'proj-1',
          dst_entity: { id: 'proj-1', type: 'project', name: 'Click Project' },
          link_type: 'related',
        },
        {
          id: 'link-3',
          dst_id: 'area-1',
          dst_entity: { id: 'area-1', type: 'area', name: 'Click Area' },
          link_type: 'related',
        },
        {
          id: 'link-4',
          dst_id: 'person-1',
          dst_entity: { id: 'person-1', type: 'person', name: 'Click Person' },
          link_type: 'related',
        },
      ],
      incoming: [],
    });
    renderPanel('entity-1');

    await waitFor(() => {
      expect(screen.getByText('Click Me')).toBeInTheDocument();
    });

    const noteLink = screen.getByTestId('connection-link-note-1');
    expect(noteLink).toHaveAttribute('href', '/notes/note-1');

    const projLink = screen.getByTestId('connection-link-proj-1');
    expect(projLink).toHaveAttribute('href', '/projects/proj-1');

    const areaLink = screen.getByTestId('connection-link-area-1');
    expect(areaLink).toHaveAttribute('href', '/areas/area-1');

    const personLink = screen.getByTestId('connection-link-person-1');
    expect(personLink).toHaveAttribute('href', '/people/person-1');
  });

  it('updates when refreshKey changes', async () => {
    const mockResponse1 = {
      outgoing: [
        {
          id: 'link-1',
          dst_id: 'note-1',
          dst_entity: { id: 'note-1', type: 'note', title: 'Original' },
          link_type: 'related',
        },
      ],
      incoming: [],
    };
    const mockResponse2 = {
      outgoing: [
        {
          id: 'link-2',
          dst_id: 'note-2',
          dst_entity: { id: 'note-2', type: 'note', title: 'Updated' },
          link_type: 'related',
        },
      ],
      incoming: [],
    };

    vi.mocked(connectionsAPI.forEntity)
      .mockResolvedValueOnce(mockResponse1)
      .mockResolvedValueOnce(mockResponse2);

    const { rerender } = render(
      <MemoryRouter>
        <ConnectionsPanel entityId="entity-1" refreshKey={0} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Original')).toBeInTheDocument();
    });

    rerender(
      <MemoryRouter>
        <ConnectionsPanel entityId="entity-1" refreshKey={1} />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Updated')).toBeInTheDocument();
    });
    expect(screen.queryByText('Original')).not.toBeInTheDocument();
  });

  it('shows connection count badge', async () => {
    vi.mocked(connectionsAPI.forEntity).mockResolvedValue({
      outgoing: [
        {
          id: 'link-1',
          dst_id: 'note-1',
          dst_entity: { id: 'note-1', type: 'note', title: 'Note A' },
          link_type: 'related',
        },
        {
          id: 'link-2',
          dst_id: 'proj-1',
          dst_entity: { id: 'proj-1', type: 'project', name: 'Project X' },
          link_type: 'related',
        },
      ],
      incoming: [
        {
          id: 'link-3',
          src_id: 'area-1',
          src_entity: { id: 'area-1', type: 'area', name: 'Area Y' },
          link_type: 'related',
        },
      ],
    });
    renderPanel('entity-1');

    await waitFor(() => {
      expect(screen.getByText('3')).toBeInTheDocument();
    });
  });

  it('deduplicates entities appearing in both outgoing and incoming', async () => {
    vi.mocked(connectionsAPI.forEntity).mockResolvedValue({
      outgoing: [
        {
          id: 'link-1',
          dst_id: 'note-1',
          dst_entity: { id: 'note-1', type: 'note', title: 'Shared Note' },
          link_type: 'related',
        },
      ],
      incoming: [
        {
          id: 'link-2',
          src_id: 'note-1',
          src_entity: { id: 'note-1', type: 'note', title: 'Shared Note' },
          link_type: 'related',
        },
      ],
    });
    renderPanel('entity-1');

    await waitFor(() => {
      const items = screen.getAllByText('Shared Note');
      expect(items).toHaveLength(1);
    });
  });

  it('falls back to raw_text for note titles when title is missing', async () => {
    vi.mocked(connectionsAPI.forEntity).mockResolvedValue({
      outgoing: [
        {
          id: 'link-1',
          dst_id: 'note-1',
          dst_entity: { id: 'note-1', type: 'note', raw_text: '# Meeting Notes\n\nBody text' },
          link_type: 'related',
        },
      ],
      incoming: [],
    });
    renderPanel('entity-1');

    await waitFor(() => {
      expect(screen.getByText('Meeting Notes')).toBeInTheDocument();
    });
  });

  it('shows link type label', async () => {
    vi.mocked(connectionsAPI.forEntity).mockResolvedValue({
      outgoing: [
        {
          id: 'link-1',
          dst_id: 'note-1',
          dst_entity: { id: 'note-1', type: 'note', title: 'Linked Note' },
          link_type: 'references',
        },
      ],
      incoming: [],
    });
    renderPanel('entity-1');

    await waitFor(() => {
      expect(screen.getByText('references')).toBeInTheDocument();
    });
  });
});
