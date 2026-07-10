import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { v4API } from '../api/v4Client';
import { CaptureProvider, useCapture } from '../context/CaptureContext';
import { ReviewProvider } from '../context/ReviewContext';
import V5ThreadDetail from './V5ThreadDetail';
import V5CaptureSheet, { CaptureFab } from './V5CaptureSheet';
import { fixtureForType } from './V5ThreadDetail.fixtures';
import { BUMP_FOLLOW_UP_LABEL, FOLLOW_UP_24H_TITLE } from '../utils/followUpActions';

vi.mock('../api/v4Client', () => ({
  v4API: {
    entities: {
      detail: vi.fn(),
      events: vi.fn(),
      canonical: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
    },
    activityUpdates: {
      create: vi.fn(),
      list: vi.fn(),
    },
    decisions: {
      list: vi.fn(),
      create: vi.fn(),
    },
    mentions: vi.fn(),
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

const entityTypes = ['project', 'person', 'area', 'resource', 'task', 'note'];

function ThreadProviders({ children }) {
  return (
    <CaptureProvider>
      <ReviewProvider>{children}</ReviewProvider>
    </CaptureProvider>
  );
}

function renderThread(type) {
  const fixture = fixtureForType(type);
  const basePath = type === 'person' ? 'people' : `${type}s`;
  const path = `/${basePath}/${fixture.detail.entity.id}`;

  return render(
    <MemoryRouter initialEntries={[path]}>
      <ThreadProviders>
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
      </ThreadProviders>
    </MemoryRouter>,
  );
}

async function typeUpdate(text) {
  const field = screen.getByLabelText('Update text');
  field.focus();
  const user = userEvent.setup();
  await user.type(field, text, { skipClick: true });
}

describe('V5ThreadDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.decisions.list.mockResolvedValue({ data: [] });
    v4API.mentions.mockResolvedValue({ results: {} });
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

      if (type !== 'resource') {
        expect(screen.getByRole('region', { name: 'People' })).toBeInTheDocument();
      } else {
        expect(screen.queryByRole('region', { name: 'People' })).not.toBeInTheDocument();
      }
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

  it('omits People, Related threads, and References sections when empty', async () => {
    const fixture = fixtureForType('project');
    const emptyDetail = {
      ...fixture.detail,
      sections: [],
    };

    render(
      <MemoryRouter initialEntries={['/projects/project-hitl']}>
        <ThreadProviders>
          <Routes>
            <Route
              path="/projects/:id"
              element={(
                <V5ThreadDetail
                  type="project"
                  previewDetail={emptyDetail}
                  previewEvents={fixture.events}
                  previewCanonical={fixture.canonical}
                />
              )}
            />
          </Routes>
        </ThreadProviders>
      </MemoryRouter>,
    );

    await screen.findByRole('heading', { level: 1, name: fixture.detail.entity.title });
    expect(screen.queryByRole('region', { name: 'People' })).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Related threads' })).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'References' })).not.toBeInTheDocument();
    expect(screen.queryByText('No people linked yet.')).not.toBeInTheDocument();
    expect(screen.queryByText('No related threads yet.')).not.toBeInTheDocument();
    expect(screen.queryByText('No references yet.')).not.toBeInTheDocument();
  });

  it('does not render dead Decide actions on blocker rows', async () => {
    renderThread('task');
    await screen.findByText('Blocked by Security approval');
    expect(screen.queryByRole('button', { name: 'Decide' })).not.toBeInTheDocument();
  });

  it('shows honest follow-up labels on next-action remind buttons', async () => {
    renderThread('task');
    const remindButtons = await screen.findAllByRole('button', { name: BUMP_FOLLOW_UP_LABEL });
    expect(remindButtons.length).toBeGreaterThan(0);
    remindButtons.forEach((button) => {
      expect(button).toHaveAttribute('title', FOLLOW_UP_24H_TITLE);
    });
  });

  it('does not open the quick-action sheet from timeline rows', async () => {
    renderThread('task');
    const row = screen.getByTestId('timeline-row-e1');

    vi.useFakeTimers();
    try {
      await act(async () => {
        fireEvent.touchStart(row);
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
        <ThreadProviders>
          <CaptureObserver />
          <V5CaptureSheet
            attachmentOptions={[
              { id: '', label: 'None', type: '' },
              { id: 'project-hitl', label: 'HITL Pilot', type: 'project' },
            ]}
          />
          <CaptureFab />
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
        </ThreadProviders>
      </MemoryRouter>,
    );

    expect(screen.getAllByRole('button', { name: /^(Capture|Open capture)$/i })).toHaveLength(1);

    fireEvent.click(screen.getByRole('button', { name: 'Open capture' }));
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
        <ThreadProviders>
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
        </ThreadProviders>
      </MemoryRouter>,
    );

    await waitFor(() => expect(v4API.entities.detail).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: 'Write update' }));
    await typeUpdate('Shipped parser fix to design partners.');
    fireEvent.click(screen.getByRole('button', { name: 'Save update' }));

    await waitFor(() => expect(v4API.activityUpdates.create).toHaveBeenCalledWith(
      'project-hitl',
      'Shipped parser fix to design partners.',
    ));
    await waitFor(() => expect(v4API.entities.detail).toHaveBeenCalledTimes(2));
  });

  it('renders the mention-enabled markdown editor for update text', async () => {
    renderThread('project');
    await screen.findByRole('region', { name: 'Add update' });
    fireEvent.click(screen.getByRole('button', { name: 'Write update' }));
    const field = screen.getByLabelText('Update text');
    expect(field.closest('[data-testid="markdown-editor"]')).not.toBeNull();
  });

  it('submits a mention picked with @ as a markdown link', async () => {
    const fixture = fixtureForType('project');
    v4API.mentions.mockResolvedValue({
      results: { person: [{ id: 'person-henry', title: 'Henry', path: '/people/person-henry' }] },
    });
    v4API.activityUpdates.create.mockResolvedValue({
      data: { id: 'note-new-update', type: 'note', source: 'activity_update' },
      suggestions: [],
    });
    v4API.entities.detail.mockResolvedValue(fixture.detail);
    v4API.entities.events.mockResolvedValue({ data: fixture.events });
    v4API.entities.canonical.mockResolvedValue({ canonical: fixture.canonical });

    render(
      <MemoryRouter initialEntries={['/projects/project-hitl']}>
        <ThreadProviders>
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
        </ThreadProviders>
      </MemoryRouter>,
    );

    await waitFor(() => expect(v4API.entities.detail).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: 'Write update' }));
    await typeUpdate('Ping @Henry');

    // The @ trigger opens the mention picker; picking Henry replaces the
    // query with a markdown link that must reach the API unchanged.
    const option = await screen.findByRole('button', { name: 'Henry' });
    fireEvent.mouseDown(option);
    fireEvent.click(screen.getByRole('button', { name: 'Save update' }));

    await waitFor(() => expect(v4API.activityUpdates.create).toHaveBeenCalledWith(
      'project-hitl',
      'Ping [Henry](/people/person-henry)',
    ));
  });

  it('shows applied and suggested outcomes after a successful update', async () => {
    const fixture = fixtureForType('project');
    const updatedEntity = {
      ...fixture.detail.entity,
      follow_up_at: '2026-07-10T09:00:00Z',
    };
    const updatedDetail = { ...fixture.detail, entity: updatedEntity };

    v4API.activityUpdates.create.mockResolvedValue({
      data: { id: 'note-new-update', type: 'note', source: 'activity_update' },
      target: updatedEntity,
      extracted: { follow_up_at: '2026-07-10T09:00:00Z', tasks: [] },
      suggestions: [
        { id: 's1', suggestion_type: 'create_task', payload: { title: 'Schedule design review' } },
        { id: 's2', suggestion_type: 'create_task', payload: { title: 'Notify stakeholders' } },
      ],
    });
    v4API.entities.detail
      .mockResolvedValueOnce(fixture.detail)
      .mockResolvedValueOnce(updatedDetail);
    v4API.entities.events.mockResolvedValue({ data: fixture.events });
    v4API.entities.canonical.mockResolvedValue({ canonical: fixture.canonical });

    render(
      <MemoryRouter initialEntries={['/projects/project-hitl']}>
        <ThreadProviders>
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
        </ThreadProviders>
      </MemoryRouter>,
    );

    await waitFor(() => expect(v4API.entities.detail).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: 'Write update' }));
    await typeUpdate('Shipped parser fix to design partners.');
    fireEvent.click(screen.getByRole('button', { name: 'Save update' }));

    await waitFor(() => expect(v4API.activityUpdates.create).toHaveBeenCalled());
    expect(await screen.findByText('2 suggested tasks')).toBeInTheDocument();
    expect(screen.getByText('Schedule design review')).toBeInTheDocument();
    expect(screen.getByText('Notify stakeholders')).toBeInTheDocument();
    expect(screen.getByText(/Follow-up set to/)).toBeInTheDocument();

    const detailsSection = screen.getByRole('region', { name: 'Details' });
    expect(within(detailsSection).getByText(/Jul 10/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss update outcome' }));
    await waitFor(() => expect(screen.queryByText('2 suggested tasks')).not.toBeInTheDocument());
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
        <ThreadProviders>
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
        </ThreadProviders>
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
        <ThreadProviders>
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
        </ThreadProviders>
      </MemoryRouter>,
    );

    await screen.findByRole('region', { name: 'Add update' });
    expect(screen.queryByRole('region', { name: 'Activity' })).not.toBeInTheDocument();
  });

  it('renders meeting prep and current load on person detail', async () => {
    renderThread('person');

    const meetingPrepSection = await screen.findByRole('region', { name: 'Meeting prep' });
    expect(within(meetingPrepSection).getByText('Go in with 2 agenda topics and 1 recent note.')).toBeInTheDocument();
    expect(within(meetingPrepSection).getByText('Unblock Review PR #847')).toBeInTheDocument();
    expect(within(meetingPrepSection).getByText(/Mary said she would review by end of week/)).toBeInTheDocument();
    expect(within(meetingPrepSection).getByText('Mary 1:1 notes')).toBeInTheDocument();
    expect(within(meetingPrepSection).getByText('Discuss HITL rollout blockers and support path.')).toBeInTheDocument();

    const currentLoadSection = screen.getByRole('region', { name: 'Current load' });
    expect(within(currentLoadSection).getByText('Review PR #847')).toBeInTheDocument();
    expect(within(currentLoadSection).getByText(/Last heard/)).toBeInTheDocument();
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
        <ThreadProviders>
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
        </ThreadProviders>
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
        <ThreadProviders>
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
        </ThreadProviders>
      </MemoryRouter>,
    );

    const openThreadLink = await screen.findByRole('link', { name: 'Open thread' });
    expect(openThreadLink).toHaveAttribute('href', '/projects/project-hitl');

    const remindButton = screen.getByRole('button', { name: BUMP_FOLLOW_UP_LABEL });
    expect(remindButton).toHaveAttribute('title', FOLLOW_UP_24H_TITLE);
  });

  it('renders decisions section with fetched decisions', async () => {
    const fixture = fixtureForType('project');
    v4API.decisions.list.mockResolvedValue({
      data: [
        {
          id: 'd1',
          statement: 'Use PostgreSQL for the v4 schema',
          context: 'Architecture review',
          decided_at: '2026-06-20T10:00:00+00:00',
          decided_by: 'user',
        },
        {
          id: 'd2',
          statement: 'Ship HITL piece by Friday',
          decided_at: '2026-06-22T14:00:00+00:00',
          decided_by: 'agent:v4-capture',
        },
      ],
    });

    renderThread('project');

    const section = await screen.findByRole('region', { name: 'Decisions' });
    expect(within(section).getByText('Use PostgreSQL for the v4 schema')).toBeInTheDocument();
    expect(within(section).getByText('Architecture review')).toBeInTheDocument();
    expect(within(section).getByText('Ship HITL piece by Friday')).toBeInTheDocument();
    expect(v4API.decisions.list).toHaveBeenCalledWith({ thread_id: fixture.detail.entity.id });

    const chip = screen.getByRole('link', { name: '2 decisions' });
    expect(chip).toHaveAttribute('href', '#decisions-section');
  });

  it('records a decision via POST /api/v4/decisions and refreshes the list', async () => {
    v4API.decisions.list.mockResolvedValue({ data: [] });
    v4API.decisions.create.mockResolvedValue({
      data: {
        id: 'd-new',
        thread_id: 'project-hitl',
        statement: 'Use Vite for the build',
        decided_by: 'user',
      },
    });

    renderThread('project');

    const section = await screen.findByRole('region', { name: 'Decisions' });
    fireEvent.click(within(section).getByRole('button', { name: 'Record decision' }));
    fireEvent.change(within(section).getByLabelText('Decision statement'), {
      target: { value: 'Use Vite for the build' },
    });
    fireEvent.click(within(section).getByRole('button', { name: 'Save decision' }));

    await waitFor(() => expect(v4API.decisions.create).toHaveBeenCalledWith({
      thread_id: 'project-hitl',
      statement: 'Use Vite for the build',
      decided_by: 'user',
    }));
    await waitFor(() => expect(v4API.decisions.list).toHaveBeenCalledTimes(2));
  });

  it('shows task context chips on person current load and project next actions', async () => {
    renderThread('person');

    const currentLoad = await screen.findByRole('region', { name: 'Current load' });
    expect(within(currentLoad).getByRole('link', { name: /HITL Pilot/i })).toHaveAttribute('href', '/projects/p-hitl');
    expect(within(currentLoad).getByRole('link', { name: /Execution/i })).toHaveAttribute('href', '/areas/a-exec');
    expect(within(currentLoad).getByRole('link', { name: /^Mary$/i })).toHaveAttribute('href', '/people/person-mary');
  });

  it('shows delete on resource detail pages', async () => {
    renderThread('resource');

    expect(await screen.findByRole('button', { name: /Delete PRD v5 draft/i })).toBeInTheDocument();
  });

  it('does not show delete on task detail pages', async () => {
    renderThread('task');

    expect(await screen.findByRole('heading', { level: 1, name: /Review PR #847/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Delete /i })).not.toBeInTheDocument();
  });

  it('shows task context chips on project next actions', async () => {
    renderThread('project');

    const nextActions = await screen.findByRole('region', { name: 'Next actions' });
    expect(within(nextActions).getByRole('link', { name: /HITL Pilot/i })).toHaveAttribute('href', '/projects/p-hitl');
    expect(within(nextActions).getByRole('link', { name: /Execution/i })).toHaveAttribute('href', '/areas/a-exec');
  });
});
