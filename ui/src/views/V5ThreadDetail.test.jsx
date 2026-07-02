import React from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { v4API } from '../api/v4Client';
import { CaptureProvider, useCapture } from '../context/CaptureContext';
import V5ThreadDetail from './V5ThreadDetail';
import V5CaptureSheet from './V5CaptureSheet';
import { fixtureForType } from './V5ThreadDetail.fixtures';

vi.mock('../api/v4Client', () => ({
  v4API: {
    entities: {
      detail: vi.fn(),
      events: vi.fn(),
      canonical: vi.fn(),
      update: vi.fn(),
    },
    activityUpdates: {
      create: vi.fn(),
      list: vi.fn(),
    },
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

const entityTypes = ['project', 'person', 'area', 'resource', 'task', 'note'];

function renderThread(type) {
  const fixture = fixtureForType(type);
  const basePath = type === 'person' ? 'people' : `${type}s`;
  const path = `/${basePath}/${fixture.detail.entity.id}`;

  return render(
    <MemoryRouter initialEntries={[path]}>
      <CaptureProvider>
        <Routes>
          <Route
            path={`/${basePath}/:id`}
            element={(
              <V5ThreadDetail
                type={type}
                previewDetail={fixture.detail}
                previewEvents={fixture.events}
                previewCanonical={fixture.canonical}
              />
            )}
          />
        </Routes>
      </CaptureProvider>
    </MemoryRouter>,
  );
}

describe('V5ThreadDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  entityTypes.forEach((type) => {
    it(`renders all thread regions for ${type}`, async () => {
      renderThread(type);
      const fixture = fixtureForType(type);

      expect(await screen.findByRole('heading', { level: 1, name: fixture.detail.entity.title })).toBeInTheDocument();
      expect(screen.getByRole('main', { name: `${type} thread detail` })).toBeInTheDocument();
      expect(screen.getByRole('region', { name: 'Details' })).toBeInTheDocument();
      expect(screen.getByRole('region', { name: 'Summary' })).toBeInTheDocument();
      expect(screen.getByRole('region', { name: 'Timeline' })).toBeInTheDocument();
      expect(screen.getByRole('region', { name: 'People' })).toBeInTheDocument();
      expect(screen.getByRole('region', { name: 'Related threads' })).toBeInTheDocument();
      expect(screen.getByRole('region', { name: 'References' })).toBeInTheDocument();

      if (['project', 'task', 'area'].includes(type)) {
        expect(screen.getByRole('region', { name: 'Add update' })).toBeInTheDocument();
        expect(screen.getByRole('region', { name: 'Activity' })).toBeInTheDocument();
      } else {
        expect(screen.queryByRole('region', { name: 'Add update' })).not.toBeInTheDocument();
        expect(screen.queryByRole('region', { name: 'Activity' })).not.toBeInTheDocument();
      }
    });
  });

  it('does not render dead Decide actions on blocker rows', async () => {
    renderThread('task');
    await screen.findByText('Blocked by Security approval');
    expect(screen.queryByRole('button', { name: 'Decide' })).not.toBeInTheDocument();
  });

  it('does not open the quick-action sheet from timeline rows', () => {
    renderThread('task');
    const row = screen.getByTestId('timeline-row-e1');

    vi.useFakeTimers();
    try {
      fireEvent.touchStart(row);
      act(() => {
        vi.advanceTimersByTime(600);
      });
    } finally {
      vi.useRealTimers();
    }

    expect(screen.queryByRole('dialog', { name: 'Quick actions' })).not.toBeInTheDocument();
  });

  it('opens generic capture from thread detail without using activity update API', async () => {
    function CaptureObserver() {
      const { open, initialContent } = useCapture();
      return (
        <div>
          <span data-testid="capture-open">{open ? 'open' : 'closed'}</span>
          <span data-testid="capture-content">{initialContent}</span>
        </div>
      );
    }

    const fixture = fixtureForType('project');
    render(
      <MemoryRouter initialEntries={['/projects/project-hitl']}>
        <CaptureProvider>
          <CaptureObserver />
          <V5CaptureSheet
            attachmentOptions={[
              { id: '', label: 'None', type: '' },
              { id: 'project-hitl', label: 'HITL Pilot', type: 'project' },
            ]}
          />
          <Routes>
            <Route
              path="/projects/:id"
              element={(
                <V5ThreadDetail
                  type="project"
                  previewDetail={fixture.detail}
                  previewEvents={fixture.events}
                  previewCanonical={fixture.canonical}
                />
              )}
            />
          </Routes>
        </CaptureProvider>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Capture' }));
    await waitFor(() => expect(screen.getByTestId('capture-open')).toHaveTextContent('open'));
    expect(screen.getByTestId('capture-content')).toHaveTextContent('');
    await waitFor(() => expect(screen.getByLabelText('Capture thread context')).toHaveValue('project-hitl'));
    expect(v4API.activityUpdates.create).not.toHaveBeenCalled();
  });

  it('submits Add update via activityUpdates.create and reloads thread detail', async () => {
    const fixture = fixtureForType('project');
    v4API.activityUpdates.create.mockResolvedValue({
      data: { id: 'note-new-update', type: 'note', source: 'activity_update' },
      suggestions: [],
    });
    v4API.entities.detail.mockResolvedValue(fixture.detail);
    v4API.entities.events.mockResolvedValue({ data: fixture.events });
    v4API.entities.canonical.mockResolvedValue({ canonical: fixture.canonical });

    render(
      <MemoryRouter initialEntries={['/projects/project-hitl']}>
        <CaptureProvider>
          <Routes>
            <Route
              path="/projects/:id"
              element={(
                <V5ThreadDetail
                  type="project"
                  previewDetail={null}
                  previewEvents={null}
                  previewCanonical=""
                />
              )}
            />
          </Routes>
        </CaptureProvider>
      </MemoryRouter>,
    );

    await waitFor(() => expect(v4API.entities.detail).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: 'Write update' }));
    fireEvent.change(screen.getByLabelText('Update text'), {
      target: { value: 'Shipped parser fix to design partners.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save update' }));

    await waitFor(() => expect(v4API.activityUpdates.create).toHaveBeenCalledWith(
      'project-hitl',
      'Shipped parser fix to design partners.',
    ));
    await waitFor(() => expect(v4API.entities.detail).toHaveBeenCalledTimes(2));
  });

  it('renders activity updates from detail sections', async () => {
    renderThread('project');
    const activitySection = await screen.findByRole('region', { name: 'Activity' });
    expect(within(activitySection).getByText('Mary said she would review by end of week.')).toBeInTheDocument();
    expect(within(activitySection).getByRole('link', { name: 'Open update' })).toHaveAttribute('href', '/notes/note-update-1');
  });

  it('loads more activity updates when detail preview is truncated', async () => {
    const fixture = fixtureForType('project');
    const detailWithMore = {
      ...fixture.detail,
      sections: (fixture.detail.sections || []).map((section) => {
        if (section.key !== 'activity_updates') return section;
        return {
          ...section,
          meta: { total: 3, limit: 1, offset: 0 },
          items: [section.items[0]],
        };
      }),
    };

    v4API.activityUpdates.list.mockResolvedValue({
      data: [
        {
          id: 'note-update-2',
          title: 'Update 2',
          content: 'Parser fix shipped to staging.',
          updated_at: '2026-06-21T14:00:00+00:00',
        },
        {
          id: 'note-update-3',
          title: 'Update 3',
          content: 'Kickoff notes captured.',
          updated_at: '2026-06-20T14:00:00+00:00',
        },
      ],
      meta: { total: 3, limit: 10, offset: 1 },
    });

    render(
      <MemoryRouter initialEntries={['/projects/project-hitl']}>
        <CaptureProvider>
          <Routes>
            <Route
              path="/projects/:id"
              element={(
                <V5ThreadDetail
                  type="project"
                  previewDetail={detailWithMore}
                  previewEvents={fixture.events}
                  previewCanonical={fixture.canonical}
                />
              )}
            />
          </Routes>
        </CaptureProvider>
      </MemoryRouter>,
    );

    const activitySection = await screen.findByRole('region', { name: 'Activity' });
    const loadMore = within(activitySection).getByRole('button', { name: 'Load more' });
    fireEvent.click(loadMore);

    await waitFor(() => expect(v4API.activityUpdates.list).toHaveBeenCalledWith(
      'project-hitl',
      { limit: 10, offset: 1 },
    ));
    expect(await within(activitySection).findByText('Parser fix shipped to staging.')).toBeInTheDocument();
    expect(within(activitySection).queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument();
  });

  it('omits Activity section when no updates exist', async () => {
    const fixture = fixtureForType('project');
    const detailWithoutActivity = {
      ...fixture.detail,
      sections: (fixture.detail.sections || []).filter((section) => section.key !== 'activity_updates'),
    };

    render(
      <MemoryRouter initialEntries={['/projects/project-hitl']}>
        <CaptureProvider>
          <Routes>
            <Route
              path="/projects/:id"
              element={(
                <V5ThreadDetail
                  type="project"
                  previewDetail={detailWithoutActivity}
                  previewEvents={fixture.events}
                  previewCanonical={fixture.canonical}
                />
              )}
            />
          </Routes>
        </CaptureProvider>
      </MemoryRouter>,
    );

    await screen.findByRole('region', { name: 'Add update' });
    expect(screen.queryByRole('region', { name: 'Activity' })).not.toBeInTheDocument();
  });

  it('renders typed people relationships and reference citations', async () => {
    renderThread('project');

    const peopleSection = await screen.findByRole('region', { name: 'People' });
    expect(within(peopleSection).getByText('Mary')).toBeInTheDocument();

    const referencesSection = screen.getByRole('region', { name: 'References' });
    expect(within(referencesSection).getAllByRole('button', { name: /Open citation/i }).length).toBeGreaterThan(0);
  });

  it('restores direct editing for core thread attributes', async () => {
    const fixture = fixtureForType('task');

    v4API.entities.update.mockResolvedValue({ data: { id: fixture.detail.entity.id } });
    v4API.entities.detail.mockResolvedValue({
      ...fixture.detail,
      entity: {
        ...fixture.detail.entity,
        title: 'Updated task title',
        status: 'waiting',
        due_at: '2026-07-04T12:30:00Z',
        properties: { ...(fixture.detail.entity.properties || {}), priority: 'urgent' },
      },
    });
    v4API.entities.events.mockResolvedValue({ data: fixture.events });
    v4API.entities.canonical.mockResolvedValue({ canonical: fixture.canonical });

    render(
      <MemoryRouter initialEntries={[`/tasks/${fixture.detail.entity.id}`]}>
        <CaptureProvider>
          <Routes>
            <Route
              path="/tasks/:id"
              element={(
                <V5ThreadDetail
                  type="task"
                  previewDetail={fixture.detail}
                  previewEvents={fixture.events}
                  previewCanonical={fixture.canonical}
                />
              )}
            />
          </Routes>
        </CaptureProvider>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: /Edit details/i }));
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Updated task title' } });
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'waiting' } });
    fireEvent.change(screen.getByLabelText('Priority'), { target: { value: 'urgent' } });
    fireEvent.change(screen.getByLabelText('Due at'), { target: { value: '2026-07-04T12:30' } });
    fireEvent.click(screen.getByRole('button', { name: /Save changes/i }));

    await waitFor(() => expect(v4API.entities.update).toHaveBeenCalledWith(
      fixture.detail.entity.id,
      expect.objectContaining({
        title: 'Updated task title',
        status: 'waiting',
        due_at: expect.stringMatching(/^2026-07-04T/),
        properties: expect.objectContaining({ priority: 'urgent' }),
      }),
    ));

    await waitFor(() => expect(v4API.entities.detail).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByRole('heading', { level: 1, name: 'Updated task title' })).toBeInTheDocument());
  });

  it('routes fallback open thread actions to a related thread instead of the current task', async () => {
    const fixture = fixtureForType('task');
    const detail = {
      ...fixture.detail,
      entity: {
        ...fixture.detail.entity,
        follow_up_at: '2026-07-03T09:00:00Z',
      },
      sections: (fixture.detail.sections || []).filter((section) => section.key === 'project'),
      dependency_watch: {
        ...fixture.detail.dependency_watch,
        focus_items: [],
      },
    };

    render(
      <MemoryRouter initialEntries={[`/tasks/${detail.entity.id}`]}>
        <CaptureProvider>
          <Routes>
            <Route
              path="/tasks/:id"
              element={(
                <V5ThreadDetail
                  type="task"
                  previewDetail={detail}
                  previewEvents={fixture.events}
                  previewCanonical={fixture.canonical}
                />
              )}
            />
          </Routes>
        </CaptureProvider>
      </MemoryRouter>,
    );

    const openThreadLink = await screen.findByRole('link', { name: 'Open thread' });
    expect(openThreadLink).toHaveAttribute('href', '/projects/project-hitl');
  });
});
