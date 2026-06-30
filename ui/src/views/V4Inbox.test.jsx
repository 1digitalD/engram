/* eslint-disable no-unused-vars */
import React from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { CaptureProvider } from '../context/CaptureContext';
import V4Inbox from './V4Inbox';
import V5CaptureSheet from './V5CaptureSheet';
import { v4API } from '../api/v4Client';

vi.mock('../components/MarkdownContent', () => ({
  default: ({ content }) => content || null,
}));

vi.mock('../api/v4Client', () => ({
  v4API: {
    capture: vi.fn(),
    inbox: vi.fn(),
    entities: { update: vi.fn(), list: vi.fn(), get: vi.fn() },
  },
}));

function renderInbox() {
  return render(
    <MemoryRouter>
      <CaptureProvider>
        <V4Inbox />
        <V5CaptureSheet attachmentOptions={[
          { id: '', label: 'None', type: '' },
          { id: 'p1', label: 'HITL Pilot', type: 'project' },
        ]}
        />
      </CaptureProvider>
    </MemoryRouter>,
  );
}

describe('V4Inbox', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.inbox.mockResolvedValue({
      needs_review: [],
      recent: [
        { id: 'n-old', title: 'Older note', content: 'Already captured', created_at: '2026-05-20T09:00:00Z', tags: [], pending_suggestion_count: 0 },
      ],
    });
  });

  it('opens the capture sheet instead of rendering an inline capture form', async () => {
    renderInbox();
    await screen.findByText('Older note');

    expect(screen.queryByLabelText(/capture text/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^capture$/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /open capture/i }));
    expect(await screen.findByRole('dialog', { name: 'Capture' })).toBeInTheDocument();
  });

  it('lists recent notes from the v4 inbox API', async () => {
    renderInbox();
    expect(await screen.findByText('Older note')).toBeInTheDocument();
    expect(screen.getByText('Capture first, then review or file the note.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Open review queue/i })).toHaveAttribute('href', '/suggestions');
    expect(screen.queryByText('Already captured')).not.toBeInTheDocument();
    expect(v4API.inbox).toHaveBeenCalledWith({ limit: 30 });
  });

  it('surfaces notes that need review separately from recent', async () => {
    v4API.inbox.mockResolvedValue({
      needs_review: [
        { id: 'n-review', title: 'Has pending suggestion', content: 'body', tags: [], pending_suggestion_count: 2, ai: { status: 'done', intent: 'task_signal' } },
      ],
      recent: [
        { id: 'n-recent', title: 'Already processed', content: 'body', tags: [], pending_suggestion_count: 0 },
      ],
    });
    renderInbox();
    expect(await screen.findByText('Needs review')).toBeInTheDocument();
    expect(screen.getByText('Has pending suggestion')).toBeInTheDocument();
    expect(screen.getByText('Intent · task signal')).toBeInTheDocument();
    expect(screen.getByText(/2 suggestions/)).toBeInTheDocument();
    expect(screen.getByText('Already processed')).toBeInTheDocument();
    expect(screen.getByText('body')).toBeInTheDocument();
  });

  it('keeps tag navigation separate from the main note link', async () => {
    v4API.inbox.mockResolvedValue({
      needs_review: [],
      recent: [
        {
          id: 'n-tagged',
          title: 'Tagged note',
          content: 'body',
          tags: [{ id: 't1', name: 'ops' }],
          pending_suggestion_count: 0,
        },
      ],
    });

    renderInbox();

    expect(await screen.findByRole('link', { name: /Tagged note/ })).toHaveAttribute('href', '/notes/n-tagged');
    expect(screen.getByRole('link', { name: '#ops' })).toHaveAttribute('href', '/search?tag=ops');
  });
});
