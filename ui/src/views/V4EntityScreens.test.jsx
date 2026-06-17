/* eslint-disable no-unused-vars */
import React from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { v4API } from '../api/v4Client';
import V4EntityList from './V4EntityList';
import V4EntityDetail from './V4EntityDetail';

vi.mock('../components/MarkdownContent', () => ({
  default: ({ content }) => content || null,
}));

vi.mock('../components/MarkdownEditor', () => ({
  default: ({ value = '', onChange, placeholder, ariaLabel }) => (
    <textarea
      aria-label={ariaLabel || placeholder || 'Markdown'}
      value={value}
      placeholder={placeholder}
      onChange={(event) => onChange?.(event.target.value)}
    />
  ),
}));

vi.mock('../api/v4Client', () => ({
  v4API: {
    entities: {
      list: vi.fn(),
      create: vi.fn(),
      detail: vi.fn(),
      events: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
      merge: vi.fn(),
      convert: vi.fn(),
      captureChanges: vi.fn(),
      setOwner: vi.fn(),
      clearOwner: vi.fn(),
    },
    events: {
      revert: vi.fn(),
    },
    capture: vi.fn(),
    relationships: {
      create: vi.fn(),
      delete: vi.fn(),
    },
    activityUpdates: {
      list: vi.fn(),
      create: vi.fn(),
    },
    suggestions: {
      list: vi.fn(),
    },
  },
}));

describe('v4 entity screens', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    v4API.entities.list.mockResolvedValue({ data: [] });
    v4API.entities.events.mockResolvedValue({ data: [] });
    v4API.entities.captureChanges.mockResolvedValue({ data: [] });
    v4API.entities.setOwner.mockResolvedValue({ data: { owner_person_id: 'person-me', is_owner: true } });
    v4API.entities.clearOwner.mockResolvedValue({ data: { owner_person_id: null, is_owner: false } });
    v4API.activityUpdates.list.mockResolvedValue({ data: [] });
    v4API.suggestions.list.mockResolvedValue({ data: [] });
  });

  it('creates a task manually from the task list', async () => {
    v4API.entities.list.mockResolvedValue({ data: [] });
    v4API.entities.create.mockResolvedValue({
      data: { id: 't1', type: 'task', title: 'Follow up', status: 'open' },
    });

    render(
      <MemoryRouter>
        <V4EntityList type="task" />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: /New task/i }));
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Follow up' } });
    fireEvent.click(screen.getByRole('button', { name: /create task/i }));

    await waitFor(() => {
      expect(v4API.entities.create).toHaveBeenCalledWith({
        type: 'task',
        title: 'Follow up',
        content: null,
      });
    });
    expect(await screen.findByRole('link', { name: /Follow up/i })).toHaveAttribute('href', '/tasks/t1');
  });

  it('creates a note from content-first input through capture', async () => {
    v4API.entities.list.mockResolvedValue({ data: [] });
    v4API.capture.mockResolvedValue({
      source_note: { id: 'n1', type: 'note', title: 'Captured note', content: 'Remember the rollout', status: 'active' },
      applied_changes: [],
      suggestions: [],
      warnings: [],
    });

    render(
      <MemoryRouter>
        <V4EntityList type="note" />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: /New note/i }));
    fireEvent.change(screen.getByLabelText('Content'), { target: { value: 'Remember the rollout' } });
    fireEvent.click(screen.getByRole('button', { name: /create note/i }));

    await waitFor(() => {
      expect(v4API.capture).toHaveBeenCalledWith({
        title: undefined,
        content: 'Remember the rollout',
        source: 'ui',
        mode: 'auto',
      });
    });
    expect(await screen.findByRole('link', { name: /Captured note/i })).toHaveAttribute('href', '/notes/n1');
  });

  it('renders area entities on the area list', async () => {
    let resolveList;
    v4API.entities.list.mockReturnValue(new Promise((resolve) => {
      resolveList = resolve;
    }));

    render(
      <MemoryRouter>
        <V4EntityList type="area" />
      </MemoryRouter>,
    );

    expect(screen.getByText('Loading areas...')).toBeInTheDocument();

    resolveList({
      data: [
        {
          id: 'a1',
          type: 'area',
          title: 'Agent Memory',
          status: 'active',
          created_at: '2026-05-20T09:00:00+00:00',
          updated_at: '2026-05-20T10:00:00+00:00',
          properties: {},
          tags: [],
        },
      ],
    });

    expect(await screen.findByRole('link', { name: /Agent Memory/i })).toHaveAttribute('href', '/areas/a1');
    expect(v4API.entities.list).toHaveBeenCalledWith({ type: 'area', limit: 100, lifecycle: 'active' });
  });

  it('filters entity lists through status chips', async () => {
    v4API.entities.list.mockResolvedValue({
      data: [
        {
          id: 't-open',
          type: 'task',
          title: 'Open item',
          status: 'open',
          created_at: '2026-05-20T09:00:00+00:00',
          updated_at: '2026-05-20T10:00:00+00:00',
          properties: {},
          tags: [],
        },
        {
          id: 't-done',
          type: 'task',
          title: 'Done item',
          status: 'done',
          created_at: '2026-05-20T09:00:00+00:00',
          updated_at: '2026-05-20T10:00:00+00:00',
          properties: {},
          tags: [],
        },
      ],
    });

    render(
      <MemoryRouter>
        <V4EntityList type="task" />
      </MemoryRouter>,
    );

    expect(await screen.findByRole('link', { name: /Open item/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Done item/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'done' }));

    expect(screen.getByRole('button', { name: 'done' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.queryByRole('link', { name: /Open item/i })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Done item/i })).toBeInTheDocument();
  });

  it('resets to the next entity type state when the shared list view changes type', async () => {
    v4API.entities.list.mockImplementation(({ type }) => {
      if (type === 'project') {
        return Promise.resolve({
          data: [
            {
              id: 'p-active',
              type: 'project',
              title: 'Active project',
              status: 'active',
              created_at: '2026-05-20T09:00:00+00:00',
              updated_at: '2026-05-20T10:00:00+00:00',
              properties: {},
              tags: [],
            },
          ],
        });
      }

      return Promise.resolve({
        data: [
          {
            id: 't-open',
            type: 'task',
            title: 'Open task',
            status: 'open',
            created_at: '2026-05-20T09:00:00+00:00',
            updated_at: '2026-05-20T10:00:00+00:00',
            properties: {},
            tags: [],
          },
        ],
      });
    });

    function Wrapper({ type }) {
      return (
        <MemoryRouter>
          <V4EntityList type={type} />
        </MemoryRouter>
      );
    }

    const { rerender } = render(<Wrapper type="project" />);

    expect(await screen.findByRole('link', { name: /Active project/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'completed' }));
    expect(screen.getByText(/No projects match the current filters/i)).toBeInTheDocument();

    rerender(<Wrapper type="task" />);

    expect(await screen.findByRole('link', { name: /Open task/i })).toBeInTheDocument();
    expect(screen.queryByText(/No tasks match the current filters/i)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'open' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('hides lifecycle control for simple archive types and still allows archived filtering', async () => {
    v4API.entities.list.mockResolvedValue({
      data: [
        {
          id: 'n-active',
          type: 'note',
          title: 'Active note',
          status: 'active',
          created_at: '2026-05-20T09:00:00+00:00',
          updated_at: '2026-05-20T10:00:00+00:00',
          properties: {},
          tags: [],
        },
        {
          id: 'n-archived',
          type: 'note',
          title: 'Archived note',
          status: 'archived',
          created_at: '2026-05-19T09:00:00+00:00',
          updated_at: '2026-05-19T10:00:00+00:00',
          properties: {},
          tags: [],
        },
      ],
    });

    render(
      <MemoryRouter>
        <V4EntityList type="note" />
      </MemoryRouter>,
    );

    expect(await screen.findByRole('link', { name: /Active note/i })).toBeInTheDocument();
    expect(screen.queryByText('Lifecycle')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'archived' }));

    expect(screen.getByRole('button', { name: 'archived' })).toHaveAttribute('aria-pressed', 'true');
    await waitFor(() => {
      expect(v4API.entities.list).toHaveBeenLastCalledWith({ type: 'note', limit: 100, lifecycle: 'archived' });
    });
    expect(screen.queryByRole('link', { name: /Active note/i })).not.toBeInTheDocument();
    expect(await screen.findByRole('link', { name: /Archived note/i })).toBeInTheDocument();
  });

  it('updates metadata and manages linked section actions from detail sections', async () => {
    const detail = {
      entity: {
        id: 't1',
        type: 'task',
        title: 'Follow up',
        content: 'Body',
        status: 'open',
        created_at: '2026-05-20T09:00:00+00:00',
        updated_at: '2026-05-20T10:00:00+00:00',
        due_at: null,
        follow_up_at: null,
        reference_url: null,
        properties: {},
        tags: [],
      },
      sections: [{
        key: 'project',
        title: 'Project',
        items: [{
          entity: { id: 'p1', type: 'project', title: 'Memory Lookup', status: 'active' },
          relationship: { id: 'r1', relationship_type: 'parent' },
        }],
      }],
    };
    v4API.entities.events.mockResolvedValue({
      data: [
        {
          id: 'e1',
          event_type: 'ai_updated',
          actor: 'agent:v4-capture',
          reason: 'Detected a follow-up action',
          confidence: 0.91,
          created_at: '2026-05-20T10:30:00+00:00',
        },
      ],
    });
    v4API.entities.detail.mockResolvedValue(detail);
    v4API.entities.update.mockResolvedValue({ data: { ...detail.entity, status: 'done' } });
    v4API.relationships.create.mockResolvedValue({ data: { id: 'r2' } });
    v4API.relationships.delete.mockResolvedValue({ data: { id: 'r1', deleted: true } });

    render(
      <MemoryRouter initialEntries={['/tasks/t1']}>
        <Routes>
          <Route path="/tasks/:id" element={<V4EntityDetail type="task" />} />
        </Routes>
      </MemoryRouter>,
    );

    expect((await screen.findAllByText('Memory Lookup')).length).toBeGreaterThan(0);
    expect(screen.getByText('Trust and recent changes')).toBeInTheDocument();
    expect(screen.getByText('91% confidence')).toBeInTheDocument();
    expect(screen.getByText('Detected a follow-up action')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'done' } });
    // Due date is an inline button until clicked; click to enter edit mode, then change.
    fireEvent.click(screen.getByRole('button', { name: 'Due date' }));
    fireEvent.change(screen.getByLabelText('Due date'), { target: { value: '2026-05-21T17:00' } });
    fireEvent.change(screen.getByLabelText('Priority'), { target: { value: 'high' } });
    expect(v4API.entities.update).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(v4API.entities.update).toHaveBeenCalledWith('t1', {
      title: 'Follow up',
      content: 'Body',
      status: 'done',
      due_at: '2026-05-21T17:00',
      properties: { priority: 'high' },
      tags: [],
    }));
    expect(await screen.findByText('Saved')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Remove' }));
    await waitFor(() => expect(v4API.relationships.delete).toHaveBeenCalledWith('r1'));
  });

  it('shows a contextual back action on detail pages', async () => {
    const detail = {
      entity: {
        id: 't-back',
        type: 'task',
        title: 'Follow up',
        content: 'Body',
        status: 'open',
        created_at: '2026-05-20T09:00:00+00:00',
        updated_at: '2026-05-20T10:00:00+00:00',
        due_at: null,
        follow_up_at: null,
        reference_url: null,
        properties: {},
        tags: [],
      },
      sections: [],
    };
    v4API.entities.detail.mockResolvedValue(detail);
    v4API.entities.events.mockResolvedValue({ data: [] });

    render(
      <MemoryRouter initialEntries={[{ pathname: '/tasks/t-back', state: { from: '/today' } }]}>
        <Routes>
          <Route path="/today" element={<div>Today view</div>} />
          <Route path="/tasks/:id" element={<V4EntityDetail type="task" />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('button', { name: 'Back to Today' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Back to Today' }));
    expect(await screen.findByText('Today view')).toBeInTheDocument();
  });

  it('allows detail sections to collapse and expand', async () => {
    const detail = {
      entity: {
        id: 't-collapse',
        type: 'task',
        title: 'Follow up',
        content: 'Body',
        status: 'open',
        created_at: '2026-05-20T09:00:00+00:00',
        updated_at: '2026-05-20T10:00:00+00:00',
        due_at: null,
        follow_up_at: null,
        reference_url: null,
        properties: {},
        tags: [],
      },
      sections: [
        {
          key: 'project',
          title: 'Project',
          items: [{
            entity: { id: 'p-collapse', type: 'project', title: 'Memory Lookup', status: 'active' },
            relationship: { id: 'r-collapse', relationship_type: 'parent' },
          }],
        },
      ],
    };
    v4API.entities.detail.mockResolvedValue(detail);
    v4API.entities.events.mockResolvedValue({ data: [] });

    render(
      <MemoryRouter initialEntries={['/tasks/t-collapse']}>
        <Routes>
          <Route path="/tasks/:id" element={<V4EntityDetail type="task" />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Execution context')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Remove' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Collapse Execution context' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Collapse Project' }));
    expect(screen.queryByRole('button', { name: 'Remove' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Expand Project' })).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(screen.getByRole('button', { name: 'Expand Project' }));
    expect(await screen.findByRole('button', { name: 'Remove' })).toBeInTheDocument();
  });

  it('archives separately from delete and hides note due date metadata', async () => {
    const detail = {
      entity: {
        id: 'n1',
        type: 'note',
        title: 'Captured note',
        content: 'Body',
        status: 'active',
        ai: { status: 'done', confidence: 0, summary: 'Summary text' },
        created_at: '2026-05-20T09:00:00+00:00',
        updated_at: '2026-05-20T10:00:00+00:00',
        due_at: null,
        follow_up_at: null,
        reference_url: null,
        properties: {},
        tags: [],
      },
      sections: [],
    };
    v4API.entities.detail.mockResolvedValue(detail);
    v4API.entities.events.mockResolvedValue({
      data: [
        {
          id: 'e0',
          event_type: 'ai_processed',
          actor: 'agent:v4-capture',
          confidence: 0,
          created_at: '2026-05-20T10:00:00+00:00',
        },
      ],
    });
    v4API.entities.update.mockResolvedValue({ data: { ...detail.entity, lifecycle: 'archived' } });
    v4API.entities.delete.mockResolvedValue({ data: { ...detail.entity, lifecycle: 'deleted' } });

    render(
      <MemoryRouter initialEntries={['/notes/n1']}>
        <Routes>
          <Route path="/notes" element={<div>Notes index</div>} />
          <Route path="/notes/:id" element={<V4EntityDetail type="note" />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('button', { name: 'Title' })).toHaveTextContent('Captured note');
    expect(screen.queryByLabelText('Due date')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Follow-up date')).toBeInTheDocument();
    expect(screen.queryByText('0% confidence')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Archive' }));
    await waitFor(() => expect(v4API.entities.update).toHaveBeenCalledWith('n1', { lifecycle: 'archived' }));
    expect(v4API.entities.delete).not.toHaveBeenCalled();

    vi.stubGlobal('confirm', vi.fn(() => true));
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(v4API.entities.delete).toHaveBeenCalledWith('n1'));
    expect(await screen.findByText('Notes index')).toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it('renders a note workspace overview with pending review context', async () => {
    const detail = {
      entity: {
        id: 'n2',
        type: 'note',
        title: 'Source note',
        content: 'Body',
        status: 'active',
        created_at: '2026-05-20T09:00:00+00:00',
        updated_at: '2026-05-20T10:00:00+00:00',
        follow_up_at: null,
        reference_url: null,
        properties: {},
        tags: [],
      },
      sections: [
        {
          key: 'derived_tasks',
          title: 'Derived Tasks',
          items: [{
            entity: { id: 't3', type: 'task', title: 'Follow up', status: 'open' },
            relationship: { id: 'r3', relationship_type: 'derived_from' },
          }],
        },
        {
          key: 'projects',
          title: 'Projects',
          items: [{
            entity: { id: 'p3', type: 'project', title: 'Memory Lookup', status: 'active' },
            relationship: { id: 'r4', relationship_type: 'related' },
          }],
        },
      ],
    };
    v4API.entities.detail.mockResolvedValue(detail);
    v4API.entities.events.mockResolvedValue({ data: [] });
    v4API.suggestions.list.mockResolvedValue({
      data: [
        { id: 's1', source_entity_id: 'n2', suggestion_type: 'create_task' },
        { id: 's2', source_entity_id: 'other', suggestion_type: 'create_project' },
      ],
    });

    render(
      <MemoryRouter initialEntries={['/notes/n2']}>
        <Routes>
          <Route path="/notes/:id" element={<V4EntityDetail type="note" />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Source note outcomes')).toBeInTheDocument();
    expect(screen.getByText('linked outcomes')).toBeInTheDocument();
    expect(screen.getByText('pending review')).toBeInTheDocument();
    expect(await screen.findByText(/1 suggestion from this note still needs review/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Open Suggestions/i })).toHaveAttribute('href', '/suggestions');
  });

  it('shows what the agent did on a note and allows reverting a change', async () => {
    const detail = {
      entity: {
        id: 'n9',
        type: 'note',
        title: 'Standup notes',
        content: 'Body',
        status: 'active',
        created_at: '2026-06-09T09:00:00+00:00',
        updated_at: '2026-06-09T10:00:00+00:00',
        follow_up_at: null,
        reference_url: null,
        properties: {},
        tags: [],
      },
      sections: [],
    };
    v4API.entities.detail.mockResolvedValue(detail);
    v4API.entities.events.mockResolvedValue({ data: [] });
    v4API.suggestions.list.mockResolvedValue({ data: [] });
    v4API.entities.captureChanges.mockResolvedValue({
      data: [
        {
          id: 'ev1',
          entity_id: 'task-1',
          event_type: 'ai_updated',
          actor: 'agent:v4-capture',
          old_value: { status: 'open' },
          new_value: { status: 'done' },
          confidence: 0.92,
          reason: 'task delivered',
          reverted_at: null,
          created_at: '2026-06-09T10:01:00+00:00',
        },
      ],
    });
    v4API.events.revert.mockResolvedValue({ data: { id: 'ev1', reverted_at: '2026-06-09T10:05:00+00:00' } });

    render(
      <MemoryRouter initialEntries={['/notes/n9']}>
        <Routes>
          <Route path="/notes/:id" element={<V4EntityDetail type="note" />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText('What the agent did')).toBeInTheDocument();
    v4API.entities.captureChanges.mockResolvedValue({
      data: [
        {
          id: 'ev1',
          entity_id: 'task-1',
          event_type: 'ai_updated',
          actor: 'agent:v4-capture',
          old_value: { status: 'open' },
          new_value: { status: 'done' },
          confidence: 0.92,
          reason: 'task delivered',
          reverted_at: '2026-06-09T10:05:00+00:00',
          created_at: '2026-06-09T10:01:00+00:00',
        },
      ],
    });

    fireEvent.click(await screen.findByRole('button', { name: 'Revert' }));
    await waitFor(() => expect(v4API.events.revert).toHaveBeenCalledWith('ev1'));
    expect(await screen.findByText('Reverted')).toBeInTheDocument();
  });

  it('renders a task workspace overview from existing detail sections', async () => {
    const detail = {
      entity: {
        id: 't7',
        type: 'task',
        title: 'Follow up with vendor',
        content: '',
        status: 'waiting',
        created_at: '2026-05-20T09:00:00+00:00',
        updated_at: '2026-05-20T10:00:00+00:00',
        due_at: null,
        follow_up_at: null,
        reference_url: null,
        properties: {},
        tags: [],
      },
      sections: [
        {
          key: 'project',
          title: 'Project',
          items: [{
            entity: { id: 'p7', type: 'project', title: 'Vendor rollout', status: 'active' },
            relationship: { id: 'r70', relationship_type: 'parent' },
          }],
        },
        {
          key: 'source_notes',
          title: 'Source Notes',
          items: [{
            entity: { id: 'n7', type: 'note', title: 'Call notes', status: 'active' },
            relationship: { id: 'r71', relationship_type: 'derived_from' },
          }],
        },
        {
          key: 'resources',
          title: 'Resources',
          items: [{
            entity: { id: 'res7', type: 'resource', title: 'Vendor contract', status: 'active' },
            relationship: { id: 'r72', relationship_type: 'references' },
          }],
        },
        {
          key: 'blocking',
          title: 'Blocking / Blocked By',
          items: [{
            entity: { id: 't8', type: 'task', title: 'Await signed quote', status: 'blocked' },
            relationship: { id: 'r73', relationship_type: 'blocks' },
            direction: 'incoming',
          }],
        },
      ],
    };
    v4API.entities.detail.mockResolvedValue(detail);
    v4API.entities.events.mockResolvedValue({ data: [] });
    v4API.activityUpdates.list.mockResolvedValue({ data: [] });

    render(
      <MemoryRouter initialEntries={['/tasks/t7']}>
        <Routes>
          <Route path="/tasks/:id" element={<V4EntityDetail type="task" />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Execution context')).toBeInTheDocument();
    expect(screen.getByText('blocking now')).toBeInTheDocument();
    expect(screen.getByText('notes linked')).toBeInTheDocument();
    expect(screen.getByText('Blocked by 1 task')).toBeInTheDocument();
    expect(screen.getByText('Waiting task has no owner linked')).toBeInTheDocument();
    expect(screen.getByText('No follow-up or due date set')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /Vendor rollout/i })[0]).toHaveAttribute('href', '/projects/p7');
    expect(screen.getAllByRole('link', { name: /Call notes/i })[0]).toHaveAttribute('href', '/notes/n7');
  });

  it('renders an area workspace overview from existing detail sections', async () => {
    const detail = {
      entity: {
        id: 'a9',
        type: 'area',
        title: 'Agent Platform',
        content: '',
        status: 'active',
        created_at: '2026-05-20T09:00:00+00:00',
        updated_at: '2026-05-20T10:00:00+00:00',
        due_at: null,
        follow_up_at: null,
        reference_url: null,
        properties: {},
        tags: [],
      },
      sections: [
        {
          key: 'projects',
          title: 'Projects',
          items: [
            {
              entity: {
                id: 'p9',
                type: 'project',
                title: 'Identity cleanup',
                status: 'active',
                task_counts: { open: 3, total: 5 },
              },
              relationship: { id: 'r90', relationship_type: 'parent' },
            },
            {
              entity: {
                id: 'p10',
                type: 'project',
                title: 'Legacy deprecation',
                status: 'completed',
                task_counts: { open: 0, total: 4 },
              },
              relationship: { id: 'r91', relationship_type: 'parent' },
            },
          ],
        },
        {
          key: 'tasks',
          title: 'Tasks',
          items: [{
            entity: { id: 't9', type: 'task', title: 'Document risks', status: 'open' },
            relationship: { id: 'r92', relationship_type: 'related' },
          }],
        },
      ],
    };
    v4API.entities.detail.mockResolvedValue(detail);
    v4API.entities.events.mockResolvedValue({ data: [] });
    v4API.activityUpdates.list.mockResolvedValue({ data: [] });

    render(
      <MemoryRouter initialEntries={['/areas/a9']}>
        <Routes>
          <Route path="/areas/:id" element={<V4EntityDetail type="area" />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Portfolio snapshot')).toBeInTheDocument();
    expect(screen.getByText('active projects')).toBeInTheDocument();
    expect(screen.getByText('open work')).toBeInTheDocument();
    expect(screen.getAllByText('Identity cleanup').length).toBeGreaterThan(0);
    expect(screen.getByText('3 open / 5 total tasks')).toBeInTheDocument();
    expect(screen.getByText('No review date set')).toBeInTheDocument();
    expect(screen.getByText('No area notes linked')).toBeInTheDocument();
    expect(screen.getByText('No people linked')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /Identity cleanup/i })[0]).toHaveAttribute('href', '/projects/p9');
  });

  it('renders a person workspace overview from existing detail sections', async () => {
    const detail = {
      entity: {
        id: 'person9',
        type: 'person',
        title: 'Gonick',
        content: '',
        status: 'active',
        is_owner: false,
        created_at: '2026-05-20T09:00:00+00:00',
        updated_at: '2026-05-20T10:00:00+00:00',
        due_at: null,
        follow_up_at: null,
        reference_url: null,
        properties: {},
        tags: [],
      },
      sections: [
        {
          key: 'assigned_tasks',
          title: 'Assigned Tasks',
          items: [
            {
              entity: { id: 't90', type: 'task', title: 'Prep review', status: 'in_progress', properties: { priority: 'high' } },
              relationship: { id: 'r900', relationship_type: 'assigned_to' },
            },
            {
              entity: { id: 't91', type: 'task', title: 'Wait on feedback', status: 'waiting' },
              relationship: { id: 'r901', relationship_type: 'assigned_to' },
            },
            {
              entity: { id: 't93', type: 'task', title: 'Prepare brief', status: 'open' },
              relationship: { id: 'r904', relationship_type: 'assigned_to' },
            },
          ],
        },
        {
          key: 'mentioned_in_notes',
          title: 'Mentioned In Notes',
          items: [{
            entity: { id: 'n90', type: 'note', title: '1:1 notes', status: 'active' },
            relationship: { id: 'r902', relationship_type: 'mentions' },
          }],
        },
        {
          key: 'projects',
          title: 'Projects',
          items: [{
            entity: { id: 'p90', type: 'project', title: 'Coordination stream', status: 'active' },
            relationship: { id: 'r903', relationship_type: 'assigned_to' },
          }],
        },
      ],
      current_load: [
        {
          task: { id: 't90', type: 'task', title: 'Prep review', status: 'in_progress', properties: { priority: 'high' } },
          last_heard_at: '2026-05-21T09:00:00+00:00',
          last_heard_preview: 'Akash shared the first draft',
        },
        {
          task: { id: 't91', type: 'task', title: 'Wait on feedback', status: 'waiting' },
          last_heard_at: null,
          last_heard_preview: null,
        },
        {
          task: { id: 't93', type: 'task', title: 'Prepare brief', status: 'open' },
          last_heard_at: null,
          last_heard_preview: null,
        },
      ],
      pulse: {
        headline: 'Focus the next 1:1 on 1 stuck task, 1 overdue follow-up, and 1 quiet task.',
        summary: {
          open_tasks: 3,
          stuck_tasks: 1,
          overdue_follow_ups: 1,
          quiet_tasks: 1,
        },
        focus_items: [
          {
            kind: 'stuck',
            label: 'Waiting',
            entity: { id: 't91', type: 'task', title: 'Wait on feedback', status: 'waiting' },
            last_heard_at: null,
            last_heard_preview: null,
          },
          {
            kind: 'overdue_follow_up',
            label: 'Follow-up overdue by 2 days',
            entity: { id: 't90', type: 'task', title: 'Prep review', status: 'in_progress', properties: { priority: 'high' } },
            last_heard_at: '2026-05-21T09:00:00+00:00',
            last_heard_preview: 'Akash shared the first draft',
          },
        ],
      },
      dependency_watch: {
        headline: 'Watch 1 blocked task, 1 external dependency, and 1 task blocking others.',
        summary: {
          blocked_tasks: 1,
          external_blockers: 1,
          blocking_tasks: 1,
        },
        focus_items: [
          {
            kind: 'external_blocker',
            label: 'Blocked by Security approval',
            entity: { id: 't91', type: 'task', title: 'Wait on feedback', status: 'waiting' },
            blocker: { id: 't92', type: 'task', title: 'Security approval', status: 'open' },
          },
          {
            kind: 'blocking',
            label: 'Blocking 1 open task',
            entity: { id: 't90', type: 'task', title: 'Prep review', status: 'in_progress', properties: { priority: 'high' } },
          },
        ],
      },
      meeting_prep: {
        headline: 'Go in with 3 agenda topics and 1 recent note.',
        counts: {
          agenda_items: 3,
          recent_notes: 1,
        },
        agenda_items: [
          {
            kind: 'stuck',
            title: 'Unblock Wait on feedback',
            reason: 'Waiting. Last heard: Akash shared the first draft',
            entity: { id: 't91', type: 'task', title: 'Wait on feedback', status: 'waiting' },
          },
          {
            kind: 'recent_progress',
            title: 'Acknowledge progress on Prep review',
            reason: 'Shared the latest draft with design',
            entity: { id: 't90', type: 'task', title: 'Prep review', status: 'in_progress', properties: { priority: 'high' } },
          },
          {
            kind: 'prep',
            title: 'Review project alignment with Coordination stream',
            reason: 'Confirm scope and sequencing for the next milestone',
            entity: { id: 'p90', type: 'project', title: 'Coordination stream', status: 'active' },
          },
        ],
        recent_notes: [
          {
            id: 'n90',
            type: 'note',
            title: '1:1 notes',
            updated_at: '2026-05-21T11:00:00+00:00',
            preview: 'Discuss launch blockers and support path',
          },
        ],
      },
    };
    v4API.entities.detail.mockResolvedValue(detail);
    v4API.entities.events.mockResolvedValue({ data: [] });

    render(
      <MemoryRouter initialEntries={['/people/person9']}>
        <Routes>
          <Route path="/people/:id" element={<V4EntityDetail type="person" />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Relationship snapshot')).toBeInTheDocument();
    expect(screen.getByText('1:1 pulse')).toBeInTheDocument();
    expect(screen.getByText('Focus the next 1:1 on 1 stuck task, 1 overdue follow-up, and 1 quiet task.')).toBeInTheDocument();
    expect(screen.getByText(/Follow-up overdue by 2 days/)).toBeInTheDocument();
    expect(screen.getByText('Waiting')).toBeInTheDocument();
    expect(screen.getByText('Dependency watch')).toBeInTheDocument();
    expect(screen.getByText('Watch 1 blocked task, 1 external dependency, and 1 task blocking others.')).toBeInTheDocument();
    expect(screen.getByText('Blocked by Security approval')).toBeInTheDocument();
    expect(screen.getByText('Meeting prep')).toBeInTheDocument();
    expect(screen.getByText('Go in with 3 agenda topics and 1 recent note.')).toBeInTheDocument();
    expect(screen.queryByText('Unblock Wait on feedback')).not.toBeInTheDocument();
    expect(screen.queryByText('Acknowledge progress on Prep review')).not.toBeInTheDocument();
    expect(screen.getByText('Review project alignment with Coordination stream')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /1:1 notes/i })[0]).toHaveAttribute('href', '/notes/n90');
    expect(screen.getByText('open tasks')).toBeInTheDocument();
    expect(screen.getByText('active projects')).toBeInTheDocument();
    expect(screen.getAllByText('Prep review').length).toBeGreaterThan(0);
    expect(screen.getByText('No follow-up date set')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Security approval/i })).toHaveAttribute('href', '/tasks/t92');
    expect(screen.getAllByRole('link', { name: /Prepare brief/i })[0]).toHaveAttribute('href', '/tasks/t93');
    expect(screen.getByText('No activity update yet')).toBeInTheDocument();
  });

  it('lets a person detail be marked as me and cleared again', async () => {
    const detail = {
      entity: {
        id: 'person-me',
        type: 'person',
        title: 'Danish',
        content: '',
        status: 'active',
        is_owner: false,
        created_at: '2026-05-20T09:00:00+00:00',
        updated_at: '2026-05-20T10:00:00+00:00',
        due_at: null,
        follow_up_at: null,
        reference_url: null,
        properties: {},
        tags: [],
      },
      sections: [],
      current_load: [],
      pulse: { headline: '', summary: {}, focus_items: [] },
      dependency_watch: { headline: '', summary: {}, focus_items: [] },
      meeting_prep: { headline: '', counts: {}, agenda_items: [], recent_notes: [] },
    };
    v4API.entities.detail
      .mockResolvedValueOnce(detail)
      .mockResolvedValueOnce({
        ...detail,
        entity: { ...detail.entity, is_owner: true },
      })
      .mockResolvedValueOnce({
        ...detail,
        entity: { ...detail.entity, is_owner: false },
      });
    v4API.entities.events.mockResolvedValue({ data: [] });

    render(
      <MemoryRouter initialEntries={['/people/person-me']}>
        <Routes>
          <Route path="/people/:id" element={<V4EntityDetail type="person" />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('button', { name: 'Mark as me' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Mark as me' }));
    await waitFor(() => expect(v4API.entities.setOwner).toHaveBeenCalledWith('person-me'));
    expect(await screen.findByRole('button', { name: 'Clear me' })).toBeInTheDocument();
    expect(screen.getByText('This is you')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Clear me' }));
    await waitFor(() => expect(v4API.entities.clearOwner).toHaveBeenCalledWith('person-me'));
    expect(await screen.findByRole('button', { name: 'Mark as me' })).toBeInTheDocument();
  });

  it('renders a project workspace overview with runtime project pulse', async () => {
    const detail = {
      entity: {
        id: 'project9',
        type: 'project',
        title: 'Coordination stream',
        content: '',
        status: 'active',
        created_at: '2026-05-20T09:00:00+00:00',
        updated_at: '2026-05-20T10:00:00+00:00',
        due_at: null,
        follow_up_at: null,
        reference_url: null,
        properties: {},
        tags: [],
      },
      sections: [
        {
          key: 'open_tasks',
          title: 'Open Tasks',
          items: [
            {
              entity: { id: 't70', type: 'task', title: 'Prep review', status: 'in_progress', properties: { priority: 'high' } },
              relationship: { id: 'r700', relationship_type: 'parent' },
            },
            {
              entity: { id: 't71', type: 'task', title: 'Wait on feedback', status: 'blocked' },
              relationship: { id: 'r701', relationship_type: 'parent' },
            },
          ],
        },
        {
          key: 'completed_tasks',
          title: 'Completed Tasks',
          items: [],
        },
        {
          key: 'notes',
          title: 'Notes',
          items: [{ entity: { id: 'n70', type: 'note', title: 'Kickoff notes', status: 'active' }, relationship: { id: 'r702', relationship_type: 'related' } }],
        },
        {
          key: 'people',
          title: 'People',
          items: [{ entity: { id: 'person70', type: 'person', title: 'Akash', status: 'active' }, relationship: { id: 'r703', relationship_type: 'assigned_to' } }],
        },
        {
          key: 'resources',
          title: 'Resources',
          items: [],
        },
        {
          key: 'area',
          title: 'Area',
          items: [{ entity: { id: 'a70', type: 'area', title: 'Execution', status: 'active' }, relationship: { id: 'r704', relationship_type: 'parent' } }],
        },
      ],
      project_pulse: {
        headline: 'Focus this project on 1 stuck task, 1 overdue task, and 1 quiet task.',
        summary: {
          open_tasks: 3,
          stuck_tasks: 1,
          overdue_tasks: 1,
          quiet_tasks: 1,
        },
        focus_items: [
          {
            kind: 'stuck',
            label: 'Blocked',
            entity: { id: 't71', type: 'task', title: 'Wait on feedback', status: 'blocked' },
            last_heard_at: '2026-05-21T09:00:00+00:00',
            last_heard_preview: 'Waiting on design sign-off',
          },
          {
            kind: 'overdue',
            label: 'Overdue by 2 days',
            entity: { id: 't70', type: 'task', title: 'Prep review', status: 'in_progress', properties: { priority: 'high' } },
            last_heard_at: null,
            last_heard_preview: null,
          },
        ],
      },
      dependency_watch: {
        headline: 'Watch 1 blocked task, 1 external dependency, and 1 task blocking others.',
        summary: {
          blocked_tasks: 1,
          external_blockers: 1,
          blocking_tasks: 1,
        },
        focus_items: [
          {
            kind: 'external_blocker',
            label: 'Blocked by Security approval',
            entity: { id: 't71', type: 'task', title: 'Wait on feedback', status: 'blocked' },
            blocker: { id: 't72', type: 'task', title: 'Security approval', status: 'open' },
          },
          {
            kind: 'blocking',
            label: 'Blocking 1 open task',
            entity: { id: 't70', type: 'task', title: 'Prep review', status: 'in_progress', properties: { priority: 'high' } },
          },
        ],
      },
    };
    v4API.entities.detail.mockResolvedValue(detail);
    v4API.entities.events.mockResolvedValue({ data: [] });

    render(
      <MemoryRouter initialEntries={['/projects/project9']}>
        <Routes>
          <Route path="/projects/:id" element={<V4EntityDetail type="project" />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Momentum at a glance')).toBeInTheDocument();
    expect(screen.getByText(/Project pulse/)).toBeInTheDocument();
    expect(screen.getByText('Focus this project on 1 stuck task, 1 overdue task, and 1 quiet task.')).toBeInTheDocument();
    expect(screen.getByText(/Dependency watch/)).toBeInTheDocument();
    expect(screen.getByText('Watch 1 blocked task, 1 external dependency, and 1 task blocking others.')).toBeInTheDocument();
    expect(screen.getByText('Blocked by Security approval')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Security approval/i })).toHaveAttribute('href', '/tasks/t72');
    expect(screen.getByText('Overdue by 2 days')).toBeInTheDocument();
    expect(screen.getByText('Waiting on design sign-off')).toBeInTheDocument();
    expect(screen.queryByText('Next step')).not.toBeInTheDocument();
  });

  it('submits activity updates from the detail page with markdown mention content', async () => {
    v4API.entities.detail.mockResolvedValue({
      entity: {
        id: 'p1',
        type: 'project',
        title: 'Memory Lookup',
        content: '',
        status: 'active',
        created_at: '2026-05-20T09:00:00+00:00',
        updated_at: '2026-05-20T10:00:00+00:00',
        due_at: null,
        follow_up_at: null,
        reference_url: null,
        properties: {},
        tags: [],
      },
      sections: [],
    });
    v4API.activityUpdates.list
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({
        data: [{
          id: 'n1',
          type: 'note',
          content: 'Worked with [Priya](/people/person1) on rollout.',
          updated_at: '2026-05-20T11:00:00+00:00',
        }],
      });
    v4API.activityUpdates.create.mockResolvedValue({
      data: {
        id: 'n1',
        type: 'note',
        content: 'Worked with [Priya](/people/person1) on rollout.',
        updated_at: '2026-05-20T11:00:00+00:00',
      },
    });

    render(
      <MemoryRouter initialEntries={['/projects/p1']}>
        <Routes>
          <Route path="/projects/:id" element={<V4EntityDetail type="project" />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Memory Lookup')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Activity update'), {
      target: { value: 'Worked with [Priya](/people/person1) on rollout.' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Add update/i }));

    await waitFor(() => {
      expect(v4API.activityUpdates.create).toHaveBeenCalledWith(
        'p1',
        'Worked with [Priya](/people/person1) on rollout.',
      );
    });
  });

  it('renders a resource workspace overview from existing detail sections', async () => {
    const detail = {
      entity: {
        id: 'resource9',
        type: 'resource',
        title: 'Admin HITL spec',
        content: '',
        status: 'active',
        created_at: '2026-05-20T09:00:00+00:00',
        updated_at: '2026-05-20T10:00:00+00:00',
        due_at: null,
        follow_up_at: null,
        reference_url: null,
        properties: {},
        tags: [],
      },
      sections: [
        {
          key: 'projects',
          title: 'Projects',
          items: [{
            entity: { id: 'p100', type: 'project', title: 'HITL State Management', status: 'active' },
            relationship: { id: 'r1000', relationship_type: 'references' },
          }],
        },
        {
          key: 'tasks',
          title: 'Tasks',
          items: [{
            entity: { id: 't100', type: 'task', title: 'Review rollout', status: 'open' },
            relationship: { id: 'r1001', relationship_type: 'references' },
          }],
        },
        {
          key: 'related_resources',
          title: 'Related Resources',
          items: [{
            entity: { id: 'resource10', type: 'resource', title: 'Approval examples', status: 'active' },
            relationship: { id: 'r1002', relationship_type: 'related' },
          }],
        },
      ],
    };
    v4API.entities.detail.mockResolvedValue(detail);
    v4API.entities.events.mockResolvedValue({ data: [] });

    render(
      <MemoryRouter initialEntries={['/resources/resource9']}>
        <Routes>
          <Route path="/resources/:id" element={<V4EntityDetail type="resource" />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Adoption snapshot')).toBeInTheDocument();
    expect(screen.getByText('active projects')).toBeInTheDocument();
    expect(screen.getByText('open tasks')).toBeInTheDocument();
    expect(screen.getAllByText('HITL State Management').length).toBeGreaterThan(0);
    expect(screen.getByText('No reference notes linked')).toBeInTheDocument();
    expect(screen.getByText('No follow-up date set')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /HITL State Management/i })[0]).toHaveAttribute('href', '/projects/p100');
  });

  it('renders a project workspace overview from existing detail sections', async () => {
    const detail = {
      entity: {
        id: 'p1',
        type: 'project',
        title: 'Memory Lookup',
        content: '',
        status: 'active',
        created_at: '2026-05-20T09:00:00+00:00',
        updated_at: '2026-05-20T10:00:00+00:00',
        due_at: null,
        follow_up_at: null,
        reference_url: null,
        properties: {},
        tags: [],
      },
      sections: [
        {
          key: 'open_tasks',
          title: 'Open Tasks',
          items: [{
            entity: { id: 't1', type: 'task', title: 'Ship rollout memo', status: 'open', properties: { priority: 'high' } },
            relationship: { id: 'r1', relationship_type: 'parent' },
          }],
        },
        {
          key: 'completed_tasks',
          title: 'Completed Tasks',
          items: [{
            entity: { id: 't2', type: 'task', title: 'Draft outline', status: 'done' },
            relationship: { id: 'r2', relationship_type: 'parent' },
          }],
        },
        {
          key: 'people',
          title: 'People',
          items: [{
            entity: { id: 'person1', type: 'person', title: 'Danish', status: 'active' },
            relationship: { id: 'r3', relationship_type: 'assigned_to' },
          }],
        },
      ],
    };
    v4API.entities.detail.mockResolvedValue(detail);
    v4API.entities.events.mockResolvedValue({
      data: [
        {
          id: 'e2',
          event_type: 'status_changed',
          actor: 'user',
          old_value: { status: 'open' },
          new_value: { status: 'in_progress' },
          created_at: '2026-05-20T11:00:00+00:00',
        },
        {
          id: 'e3',
          event_type: 'updated',
          actor: 'user',
          old_value: { status: 'open', updated_at: '2026-05-20T10:00:00+00:00' },
          new_value: { status: 'in_progress', updated_at: '2026-05-20T11:30:00+00:00' },
          created_at: '2026-05-20T11:30:00+00:00',
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={['/projects/p1']}>
        <Routes>
          <Route path="/projects/:id" element={<V4EntityDetail type="project" />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Momentum at a glance')).toBeInTheDocument();
    expect(screen.getByText('Status changed')).toBeInTheDocument();
    expect(screen.getByText('open -> in progress')).toBeInTheDocument();
    const historyPanel = screen.getByText('Recent history').closest('section');
    expect(within(historyPanel).queryByText(/^Updated$/)).not.toBeInTheDocument();
    expect(screen.getByText('open tasks')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /Ship rollout memo/i })[0]).toHaveAttribute('href', '/tasks/t1');
    expect(screen.getByText('Next step')).toBeInTheDocument();
    expect(screen.getByText('No review date set')).toBeInTheDocument();
    expect(screen.getByText('No project notes linked')).toBeInTheDocument();
    expect(screen.getAllByText('No area linked').length).toBeGreaterThan(0);
  });

  it('creates a new task from a project detail and links it as parent', async () => {
    const detail = {
      entity: {
        id: 'p1',
        type: 'project',
        title: 'Memory Lookup',
        content: '',
        status: 'active',
        created_at: '2026-05-20T09:00:00+00:00',
        updated_at: '2026-05-20T10:00:00+00:00',
        due_at: null,
        follow_up_at: null,
        reference_url: null,
        properties: {},
        tags: [],
      },
      sections: [],
    };
    v4API.entities.detail.mockResolvedValue(detail);
    v4API.entities.create.mockResolvedValue({
      data: { id: 't2', type: 'task', title: 'Draft rollout', status: 'open' },
    });
    v4API.relationships.create.mockResolvedValue({ data: { id: 'r2' } });

    render(
      <MemoryRouter initialEntries={['/projects/p1']}>
        <Routes>
          <Route path="/projects/:id" element={<V4EntityDetail type="project" />} />
        </Routes>
      </MemoryRouter>,
    );

    // Open the Tasks add modal, then switch to "Create new" tab
    fireEvent.click(await screen.findByRole('button', { name: 'Add task' }));

    fireEvent.click(await screen.findByRole('tab', { name: 'Create new' }));
    fireEvent.change(await screen.findByLabelText('Tasks title'), { target: { value: 'Draft rollout' } });
    fireEvent.change(screen.getByLabelText('Tasks due date'), { target: { value: '2026-05-22T12:00' } });
    fireEvent.change(screen.getByLabelText('Tasks priority'), { target: { value: 'urgent' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add new task' }));

    await waitFor(() => expect(v4API.entities.create).toHaveBeenCalledWith({
      type: 'task',
      title: 'Draft rollout',
      content: null,
      due_at: '2026-05-22T12:00',
      properties: { priority: 'urgent' },
    }));
    await waitFor(() => expect(v4API.relationships.create).toHaveBeenCalledWith('t2', {
      target_entity_id: 'p1',
      relationship_type: 'parent',
    }));
  });

  it('creates a project note through capture and links the source note', async () => {
    const detail = {
      entity: {
        id: 'p1',
        type: 'project',
        title: 'Memory Lookup',
        content: '',
        status: 'active',
        created_at: '2026-05-20T09:00:00+00:00',
        updated_at: '2026-05-20T10:00:00+00:00',
        due_at: null,
        follow_up_at: null,
        reference_url: null,
        properties: {},
        tags: [],
      },
      sections: [],
    };
    v4API.entities.detail.mockResolvedValue(detail);
    v4API.capture.mockResolvedValue({
      source_note: { id: 'n2', type: 'note', title: 'Meeting note', content: 'Meeting note', status: 'active' },
      applied_changes: [],
      suggestions: [],
      warnings: [],
    });
    v4API.relationships.create.mockResolvedValue({ data: { id: 'r4' } });

    render(
      <MemoryRouter initialEntries={['/projects/p1']}>
        <Routes>
          <Route path="/projects/:id" element={<V4EntityDetail type="project" />} />
        </Routes>
      </MemoryRouter>,
    );

    // Open the Notes add modal, then switch to "Create new"
    fireEvent.click(await screen.findByRole('button', { name: 'Add note' }));

    fireEvent.click(await screen.findByRole('tab', { name: 'Create new' }));
    fireEvent.change(await screen.findByLabelText('Notes title'), { target: { value: 'Meeting note' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add project note' }));

    await waitFor(() => expect(v4API.capture).toHaveBeenCalledWith({
      title: 'Meeting note',
      content: 'Meeting note',
      source: 'ui',
      mode: 'auto',
    }));
    await waitFor(() => expect(v4API.relationships.create).toHaveBeenCalledWith('p1', {
      target_entity_id: 'n2',
      relationship_type: 'related',
    }));
  });

  it('links an existing task from a project detail without raw IDs', async () => {
    const detail = {
      entity: {
        id: 'p1',
        type: 'project',
        title: 'Memory Lookup',
        content: '',
        status: 'active',
        created_at: '2026-05-20T09:00:00+00:00',
        updated_at: '2026-05-20T10:00:00+00:00',
        due_at: null,
        follow_up_at: null,
        reference_url: null,
        properties: {},
        tags: [],
      },
      sections: [],
    };
    v4API.entities.detail.mockResolvedValue(detail);
    v4API.entities.list.mockImplementation(({ type }) => Promise.resolve({
      data: type === 'task'
        ? [{ id: 't3', type: 'task', title: 'Existing task', status: 'open' }]
        : [],
    }));
    v4API.relationships.create.mockResolvedValue({ data: { id: 'r3' } });

    render(
      <MemoryRouter initialEntries={['/projects/p1']}>
        <Routes>
          <Route path="/projects/:id" element={<V4EntityDetail type="project" />} />
        </Routes>
      </MemoryRouter>,
    );

    // Open the Tasks add modal — default tab is "Link existing", which renders a combobox.
    fireEvent.click(await screen.findByRole('button', { name: 'Add task' }));

    const combobox = await screen.findByLabelText('Search and link Tasks');
    fireEvent.focus(combobox);
    fireEvent.change(combobox, { target: { value: 'Existing' } });
    const option = await screen.findByRole('option', { name: /Existing task/i });
    fireEvent.mouseDown(option);

    await waitFor(() => expect(v4API.relationships.create).toHaveBeenCalledWith('t3', {
      target_entity_id: 'p1',
      relationship_type: 'parent',
    }));
  });

  it('merges a duplicate project into a chosen survivor from the detail header', async () => {
    const detail = {
      entity: {
        id: 'p1',
        type: 'project',
        title: 'Plan agent platform roadmap',
        content: '',
        status: 'active',
        created_at: '2026-05-20T09:00:00+00:00',
        updated_at: '2026-05-20T10:00:00+00:00',
        due_at: null,
        follow_up_at: null,
        reference_url: null,
        properties: {},
        tags: [],
      },
      sections: [],
    };
    v4API.entities.detail.mockResolvedValue(detail);
    v4API.entities.list.mockResolvedValue({
      data: [
        { id: 'p1', type: 'project', title: 'Plan agent platform roadmap', status: 'active', lifecycle: 'active' },
        { id: 'p2', type: 'project', title: 'Define Agent Platform roadmap', status: 'active', lifecycle: 'active' },
      ],
    });
    v4API.entities.merge.mockResolvedValue({ data: { id: 'p2' }, merge: {} });
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);

    render(
      <MemoryRouter initialEntries={['/projects/p1']}>
        <Routes>
          <Route path="/projects/:id" element={<V4EntityDetail type="project" />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: 'Merge into another entity' }));

    const combobox = await screen.findByLabelText('Search for the entity to merge into');
    fireEvent.focus(combobox);
    fireEvent.change(combobox, { target: { value: 'Define' } });
    const option = await screen.findByRole('option', { name: /Define Agent Platform roadmap/i });
    fireEvent.mouseDown(option);

    await waitFor(() => expect(v4API.entities.merge).toHaveBeenCalledWith('p1', 'p2'));
    expect(confirmSpy).toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it('inline title edit keeps typed value and Escape restores the original', async () => {
    const detail = {
      entity: {
        id: 't1',
        type: 'task',
        title: 'Original title',
        content: '',
        status: 'open',
        created_at: '2026-05-20T09:00:00+00:00',
        updated_at: '2026-05-20T10:00:00+00:00',
        due_at: null,
        follow_up_at: null,
        reference_url: null,
        properties: {},
        tags: [],
      },
      sections: [],
    };
    v4API.entities.detail.mockResolvedValue(detail);

    render(
      <MemoryRouter initialEntries={['/tasks/t1']}>
        <Routes>
          <Route path="/tasks/:id" element={<V4EntityDetail type="task" />} />
        </Routes>
      </MemoryRouter>,
    );

    // Enter edit mode on the title
    fireEvent.click(await screen.findByRole('button', { name: 'Title' }));
    const input = await screen.findByLabelText('Title');

    // Simulate two successive edits — with the old [editing, value] effect
    // deps, initialRef was clobbered after each keystroke, so Escape only
    // undid the last keystroke instead of restoring the original.
    fireEvent.change(input, { target: { value: 'Changed once' } });
    fireEvent.change(input, { target: { value: 'Changed twice' } });
    expect(input.value).toBe('Changed twice');

    fireEvent.keyDown(input, { key: 'Escape' });

    // Back to display mode showing the ORIGINAL title.
    expect(await screen.findByRole('button', { name: 'Title' })).toHaveTextContent('Original title');
  });

  it('converts a project to a task from the detail header', async () => {
    const detail = {
      entity: {
        id: 'p1',
        type: 'project',
        title: 'Agent Platform leadership deck',
        content: '',
        status: 'active',
        created_at: '2026-05-20T09:00:00+00:00',
        updated_at: '2026-05-20T10:00:00+00:00',
        due_at: null,
        follow_up_at: null,
        reference_url: null,
        properties: {},
        tags: [],
      },
      sections: [],
    };
    v4API.entities.detail.mockResolvedValue(detail);
    v4API.entities.convert.mockResolvedValue({ data: { id: 'p1', type: 'task' } });

    render(
      <MemoryRouter initialEntries={['/projects/p1']}>
        <Routes>
          <Route path="/projects/:id" element={<V4EntityDetail type="project" />} />
          <Route path="/tasks/:id" element={<V4EntityDetail type="task" />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: 'Convert to task' }));

    await waitFor(() => expect(v4API.entities.convert).toHaveBeenCalledWith('p1', 'task'));
  });

  it('renders task detail when sections contain entity-less items (activity updates)', async () => {
    // Regression: activity_updates section items carry no entity ref; they
    // previously fell into the generic relationship renderer and crashed
    // the whole detail page (blank screen).
    v4API.entities.detail.mockResolvedValue({
      entity: {
        id: 't1',
        type: 'task',
        title: 'Explore P3 automation',
        content: 'Owner: Ola.',
        status: 'open',
        created_at: '2026-06-01T09:00:00+00:00',
        updated_at: '2026-06-11T10:00:00+00:00',
        due_at: null,
        follow_up_at: null,
        reference_url: null,
        properties: {},
        tags: [],
      },
      sections: [
        {
          key: 'activity_updates',
          title: 'Activity',
          items: [
            { id: 'n9', title: 'Update: Explore P3 automation (2026-06-11)', content: 'Ola tried this.', updated_at: '2026-06-11T10:00:00+00:00' },
          ],
        },
        {
          key: 'some_future_section',
          title: 'Future',
          items: [{ id: 'x1', title: 'No entity here' }],
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={['/tasks/t1']}>
        <Routes>
          <Route path="/tasks/:id" element={<V4EntityDetail type="task" />} />
        </Routes>
      </MemoryRouter>,
    );

    // The page renders (no blank-screen crash) and entity-less sections are
    // excluded from Additional Links.
    expect(await screen.findByText('Explore P3 automation')).toBeInTheDocument();
    expect(screen.queryByText('Additional Links')).not.toBeInTheDocument();
  });
});
