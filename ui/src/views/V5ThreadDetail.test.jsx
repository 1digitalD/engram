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

  it('opens capture in place from thread detail with the current thread attached', async () => {
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
    await waitFor(() => expect(screen.getByLabelText('Capture attachment')).toHaveValue('project-hitl'));
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

    renderThread('task');

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

 await screen.findByText('Updated task title');
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
