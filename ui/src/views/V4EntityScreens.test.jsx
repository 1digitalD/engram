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

vi.mock('../api/v4Client', () => ({
  v4API: {
    entities: {
      list: vi.fn(),
      create: vi.fn(),
      detail: vi.fn(),
      events: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
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
  },
}));

describe('v4 entity screens', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.entities.list.mockResolvedValue({ data: [] });
    v4API.entities.events.mockResolvedValue({ data: [] });
    v4API.activityUpdates.list.mockResolvedValue({ data: [] });
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

    expect(await screen.findByText('Memory Lookup')).toBeInTheDocument();
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

  it('archives separately from delete and hides note due date metadata', async () => {
    const detail = {
      entity: {
        id: 'n1',
        type: 'note',
        title: 'Captured note',
        content: 'Body',
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
    v4API.entities.events.mockResolvedValue({ data: [] });
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

    fireEvent.click(screen.getByRole('button', { name: 'Archive' }));
    await waitFor(() => expect(v4API.entities.update).toHaveBeenCalledWith('n1', { lifecycle: 'archived' }));
    expect(v4API.entities.delete).not.toHaveBeenCalled();

    vi.stubGlobal('confirm', vi.fn(() => true));
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(v4API.entities.delete).toHaveBeenCalledWith('n1'));
    expect(await screen.findByText('Notes index')).toBeInTheDocument();
    vi.unstubAllGlobals();
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
});
