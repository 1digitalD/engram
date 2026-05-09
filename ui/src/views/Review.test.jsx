import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import Review from './Review';
import useStore from '../stores/useStore';
import { summariesAPI, proposalsAPI } from '../api/engram';
import { REVIEW_WORKFLOW_STORAGE_KEY } from './reviewWorkflowState';

vi.mock('../components/notes/NoteCard', () => ({
  default: ({ note }) => <div data-testid="note-card">{note?.id}</div>,
}));

vi.mock('../stores/useStore');

vi.mock('../api/engram', () => ({
  summariesAPI: { list: vi.fn() },
  proposalsAPI: { list: vi.fn() },
}));

function renderReview() {
  return render(
    <MemoryRouter>
      <Review />
    </MemoryRouter>
  );
}

describe('Review weekly workflow', () => {
  beforeEach(() => {
    globalThis.localStorage.clear();
    vi.mocked(summariesAPI.list).mockResolvedValue({ data: [] });
    vi.mocked(proposalsAPI.list).mockResolvedValue({ data: [] });
    vi.mocked(useStore).mockReturnValue({
      notes: [],
      tasks: [],
      projects: [{ id: 'p1', name: 'Alpha', is_archived: false }],
      areas: [{ id: 'a1', name: 'Work', is_archived: false }],
      addToast: vi.fn(),
      updateNote: vi.fn().mockResolvedValue({}),
    });
  });

  it('renders progress rail and seven workflow steps', async () => {
    renderReview();
    expect(await screen.findByTestId('review-workflow-progress')).toBeInTheDocument();
    for (const id of ['inbox', 'projects', 'areas', 'orphans', 'proposals', 'insights', 'plan']) {
      expect(screen.getByTestId(`review-step-${id}`)).toBeInTheDocument();
    }
  });

  it('restores expanded section from localStorage after hydration', async () => {
    localStorage.setItem(
      REVIEW_WORKFLOW_STORAGE_KEY,
      JSON.stringify({
        expanded: {
          inbox: false,
          projects: true,
          areas: false,
          orphans: false,
          proposals: false,
          insights: false,
          plan: false,
        },
        completed: {
          inbox: false,
          projects: false,
          areas: false,
          orphans: false,
          proposals: false,
          insights: false,
          plan: false,
        },
        lastActiveStepId: 'projects',
      })
    );
    renderReview();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Review Projects/i })).toHaveAttribute('aria-expanded', 'true')
    );
  });

  it('shows orphan notes only when zero links and no project or area', async () => {
    const user = userEvent.setup();
    vi.mocked(useStore).mockReturnValue({
      notes: [
        {
          id: 'o1',
          raw_text: '# Orphan only',
          bucket: 'PROJECTS',
          is_archived: false,
          link_count: 0,
          project_id: null,
          project_ids: [],
          area_id: null,
        },
        {
          id: 'x1',
          raw_text: '# Has links',
          bucket: 'PROJECTS',
          is_archived: false,
          link_count: 1,
          project_id: null,
          project_ids: [],
          area_id: null,
        },
        {
          id: 'x2',
          raw_text: '# Has project',
          bucket: 'PROJECTS',
          is_archived: false,
          link_count: 0,
          project_id: 'p1',
          project_ids: ['p1'],
          area_id: null,
        },
        {
          id: 'x3',
          raw_text: '# Has area',
          bucket: 'PROJECTS',
          is_archived: false,
          link_count: 0,
          project_id: null,
          project_ids: [],
          area_id: 'a1',
        },
        {
          id: 'x4',
          raw_text: '# Inbox',
          bucket: 'INBOX',
          is_archived: false,
          link_count: 0,
          project_id: null,
          project_ids: [],
          area_id: null,
        },
      ],
      tasks: [],
      projects: [{ id: 'p1', name: 'Alpha', is_archived: false }],
      areas: [{ id: 'a1', name: 'Work', is_archived: false }],
      addToast: vi.fn(),
      updateNote: vi.fn().mockResolvedValue({}),
    });
    renderReview();
    await screen.findByTestId('review-step-orphans');
    await user.click(screen.getByRole('button', { name: /Orphan Notes/i }));
    const orphanList = await screen.findByRole('list', { name: /Orphan notes/i });
    expect(within(orphanList).getAllByRole('listitem')).toHaveLength(1);
    expect(within(orphanList).getByRole('link', { name: /Orphan only/i })).toBeInTheDocument();
    expect(within(orphanList).queryByText(/Has links/i)).not.toBeInTheDocument();
  });

  it('bulk archive all orphans confirms then archives with silent updates', async () => {
    const user = userEvent.setup();
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const updateNote = vi.fn().mockResolvedValue({});
    vi.mocked(useStore).mockReturnValue({
      notes: [
        {
          id: 'o1',
          raw_text: '# One',
          bucket: 'PROJECTS',
          is_archived: false,
          link_count: 0,
          project_id: null,
          project_ids: [],
          area_id: null,
        },
        {
          id: 'o2',
          raw_text: '# Two',
          bucket: 'PROJECTS',
          is_archived: false,
          link_count: 0,
          project_id: null,
          project_ids: [],
          area_id: null,
        },
      ],
      tasks: [],
      projects: [{ id: 'p1', name: 'Alpha', is_archived: false }],
      areas: [{ id: 'a1', name: 'Work', is_archived: false }],
      addToast: vi.fn(),
      updateNote,
    });
    renderReview();
    await screen.findByTestId('review-step-orphans');
    await user.click(screen.getByRole('button', { name: /Orphan Notes/i }));
    await user.click(screen.getByRole('button', { name: /Archive all orphans/i }));
    expect(confirmSpy).toHaveBeenCalled();
    expect(updateNote).toHaveBeenCalledTimes(2);
    expect(updateNote).toHaveBeenCalledWith('o1', { is_archived: true }, { silent: true });
    expect(updateNote).toHaveBeenCalledWith('o2', { is_archived: true }, { silent: true });
    confirmSpy.mockRestore();
  });
});
