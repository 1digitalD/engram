import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ResourceDetail from './ResourceDetail';
import useStore from '../stores/useStore';
import { connectionsAPI, resourcesAPI } from '../api/engram';

const mockNavigate = vi.fn();

vi.mock('../components/ConnectionsPanel/ConnectionsPanel', async () => {
  const actual = await vi.importActual('../components/ConnectionsPanel/ConnectionsPanel');
  return {
    ...actual,
    default: () => <div data-testid="connections-panel">Connections panel</div>,
  };
});

vi.mock('../stores/useStore');
vi.mock('../api/engram', async () => {
  const actual = await vi.importActual('../api/engram');
  return {
    ...actual,
    resourcesAPI: {
      ...actual.resourcesAPI,
      get: vi.fn(),
    },
    connectionsAPI: {
      ...actual.connectionsAPI,
      forEntity: vi.fn(),
    },
  };
});

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

function renderDetail({
  route = '/resources/r1',
  resources = [],
  notes = [],
  tasks = [],
  people = [],
  areas = [],
} = {}) {
  const updateResource = vi.fn().mockResolvedValue({});
  const deleteResource = vi.fn().mockResolvedValue(undefined);
  const upsertResource = vi.fn();

  vi.mocked(useStore).mockReturnValue({
    resources,
    notes,
    tasks,
    people,
    areas,
    updateResource,
    deleteResource,
    upsertResource,
  });

  return {
    updateResource,
    deleteResource,
    upsertResource,
    ...render(
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/resources/:id" element={<ResourceDetail />} />
        </Routes>
      </MemoryRouter>,
    ),
  };
}

describe('ResourceDetail', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    vi.mocked(resourcesAPI.get).mockReset();
    vi.mocked(connectionsAPI.forEntity).mockReset();
  });

  it('loads the resource by URL param from the API when it is missing from the store', async () => {
    vi.mocked(resourcesAPI.get).mockResolvedValue({
      data: {
        id: 'r1',
        title: 'Designing Data-Intensive Applications',
        resource_type: 'BOOK',
        author: 'Martin Kleppmann',
        description: 'Reference book',
        tag_names: ['systems'],
      },
    });
    vi.mocked(connectionsAPI.forEntity).mockResolvedValue({ outgoing: [], incoming: [] });

    const { upsertResource } = renderDetail();

    await waitFor(() => {
      expect(resourcesAPI.get).toHaveBeenCalledWith('r1');
    });
    expect(await screen.findByRole('heading', { name: 'Designing Data-Intensive Applications' })).toBeInTheDocument();
    expect(upsertResource).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'r1', title: 'Designing Data-Intensive Applications' }),
    );
  });

  it('renders linked notes, tasks, and people tabs plus the AI sidebar', async () => {
    vi.mocked(connectionsAPI.forEntity).mockResolvedValue({
      outgoing: [
        { id: 'l1', src_id: 'r1', dst_id: 'n1', dst_entity: { id: 'n1', type: 'note', raw_text: '# Reading note' } },
        { id: 'l2', src_id: 'r1', dst_id: 't1', dst_entity: { id: 't1', type: 'task', title: 'Draft summary', status: 'IN_PROGRESS' } },
        { id: 'l3', src_id: 'r1', dst_id: 'person-1', dst_entity: { id: 'person-1', type: 'person', name: 'Ada Lovelace', role: 'Researcher' } },
      ],
      incoming: [],
    });

    renderDetail({
      resources: [{
        id: 'r1',
        title: 'Thinking in Systems',
        resource_type: 'BOOK',
        author: 'Donella Meadows',
        description: 'Systems primer',
        tag_names: ['systems', 'thinking'],
      }],
      notes: [{ id: 'n1', raw_text: '# Reading note', type: 'note' }],
      tasks: [{ id: 't1', title: 'Draft summary', status: 'IN_PROGRESS', type: 'task' }],
      people: [{ id: 'person-1', name: 'Ada Lovelace', role: 'Researcher', type: 'person' }],
    });

    expect(await screen.findByRole('heading', { name: 'Thinking in Systems' })).toBeInTheDocument();
    expect(screen.getByText('systems')).toBeInTheDocument();
    expect(screen.getByText('thinking')).toBeInTheDocument();
    expect(screen.getByText('Suggested links')).toBeInTheDocument();
    expect(screen.getByText('Quick actions')).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: /Tasks \(1\)/ }));
    expect(screen.getAllByText('Draft summary').length).toBeGreaterThan(0);

    await user.click(await screen.findByRole('button', { name: /People \(1\)/ }));
    expect(screen.getAllByText('Ada Lovelace').length).toBeGreaterThan(0);

    await user.click(await screen.findByRole('button', { name: /Notes \(1\)/ }));
    expect(screen.getAllByText('Reading note').length).toBeGreaterThan(0);
  });
});
