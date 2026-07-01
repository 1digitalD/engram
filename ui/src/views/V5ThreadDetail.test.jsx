import React from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { v4API } from '../api/v4Client';
import { CaptureProvider, useCapture } from '../context/CaptureContext';
import V5ThreadDetail from './V5ThreadDetail';
import V5CaptureSheet from './V5CaptureSheet';
import { fixtureForType } from './V5ThreadDetail.fixtures';
import { narrativeSummary } from './v5ThreadDetailUtils';

vi.mock('../api/v4Client', () => ({
  v4API: {
    entities: {
      detail: vi.fn(),
      events: vi.fn(),
      canonical: vi.fn(),
      update: vi.fn(),
    },
  },
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
      expect(screen.getByText('Summary')).toBeInTheDocument();
      expect(screen.getByText('Next actions')).toBeInTheDocument();
      expect(screen.getByText('Timeline')).toBeInTheDocument();
      expect(screen.getByText('People')).toBeInTheDocument();
      expect(screen.getByText('Related threads')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Capture' })).toBeInTheDocument();
    });
  });

  it('renders pulse cards inside next actions', async () => {
    renderThread('project');
    expect(await screen.findByText('Project pulse')).toBeInTheDocument();
    expect(screen.getByText('Dependency watch')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'Open' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: '✓' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: '👋' }).length).toBeGreaterThan(0);
  });

  it('limits next actions to three items', async () => {
    renderThread('project');
    await screen.findByText('Next actions');
    expect(screen.getAllByTestId(/^action-row-/).length).toBeLessThanOrEqual(3);
  });

  it('shows person pulse cards for person threads', async () => {
    renderThread('person');
    expect(await screen.findByText('1:1 pulse')).toBeInTheDocument();
  });

  it('falls back to the unsummarized message', () => {
    expect(narrativeSummary({ ai: {}, content: '' }, '')).toBe("I haven't summarized this yet");
  });

  it('loads thread data from the API when preview props are absent', async () => {
    const fixture = fixtureForType('note');
    v4API.entities.detail.mockResolvedValue(fixture.detail);
    v4API.entities.events.mockResolvedValue({ data: fixture.events });
    v4API.entities.canonical.mockResolvedValue({ canonical: fixture.canonical });

    render(
      <MemoryRouter initialEntries={[`/notes/${fixture.detail.entity.id}`]}>
        <CaptureProvider>
          <Routes>
            <Route path="/notes/:id" element={<V5ThreadDetail type="note" />} />
          </Routes>
        </CaptureProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Mary PR review note')).toBeInTheDocument();
    expect(v4API.entities.detail).toHaveBeenCalledWith(fixture.detail.entity.id);
    expect(v4API.entities.events).toHaveBeenCalledWith(fixture.detail.entity.id);
  });

  it('opens a long-press action sheet on action rows', () => {
    renderThread('task');
    const row = screen.getByTestId('action-row-blocker-t-review');

    vi.useFakeTimers();
    try {
      fireEvent.touchStart(row);
      act(() => {
        vi.advanceTimersByTime(600);
      });
    } finally {
      vi.useRealTimers();
    }

    expect(screen.getByRole('dialog', { name: 'Quick actions' })).toBeInTheDocument();
  });

  it('does not render dead Decide actions for blocker rows', async () => {
    renderThread('task');

    await screen.findByText('Blocked by Security approval');
    expect(screen.queryByRole('button', { name: 'Decide' })).not.toBeInTheDocument();
  });

  it('does not open a dead quick-action sheet from timeline rows', () => {
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

  it('opens capture in place from the thread detail fab with the current thread attached', async () => {
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

  it('exposes accessible section headings', async () => {
    renderThread('area');
    await screen.findByRole('heading', { level: 1, name: 'Execution' });
    expect(screen.getByRole('region', { name: 'Summary' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Next actions' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Timeline' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'People' })).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Related threads' })).toBeInTheDocument();
  });

  it('renders typed people relationships', async () => {
    renderThread('note');
    const peopleSection = await screen.findByRole('region', { name: 'People' });
    expect(within(peopleSection).getByText('Mary')).toBeInTheDocument();
    expect(within(peopleSection).getByText(/mentions/i)).toBeInTheDocument();
  });

  it('renders the references section with related entities', async () => {
    renderThread('project');
    const referencesSection = await screen.findByRole('region', { name: 'References' });
    expect(referencesSection).toBeInTheDocument();
    expect(within(referencesSection).getAllByRole('button', { name: /Open citation/i }).length).toBeGreaterThan(0);
  });
});
