import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
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
});
