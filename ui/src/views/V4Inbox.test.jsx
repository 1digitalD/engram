/* eslint-disable no-unused-vars */
import React from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import V4Inbox from './V4Inbox';
import { v4API } from '../api/v4Client';

vi.mock('../components/MarkdownContent', () => ({
  default: ({ content }) => content || null,
}));

// Mock MarkdownEditor as a plain textarea so tests can drive it with fireEvent.
vi.mock('../components/MarkdownEditor', () => ({
  default: ({ value, onChange, placeholder }) => (
    <textarea
      aria-label="Capture text"
      placeholder={placeholder}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  ),
}));

vi.mock('../api/v4Client', () => ({
  v4API: {
    capture: vi.fn(),
    inbox: vi.fn(),
    entities: { update: vi.fn() },
  },
}));

function renderInbox() {
  return render(<MemoryRouter><V4Inbox /></MemoryRouter>);
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

  it('captures text and surfaces the result in the capture log', async () => {
    v4API.capture.mockResolvedValue({
      source_note: { id: 'n1', title: 'Captured note', content: 'Ask Henry about rollout' },
      applied_changes: [{ type: 'summary_updated' }],
      suggestions: [{ id: 's1', suggestion_type: 'create_task', payload: { title: 'Follow up with Henry' } }],
      warnings: ['AI extraction degraded'],
    });

    renderInbox();
    await screen.findByText('Older note');

    fireEvent.change(screen.getByLabelText(/capture text/i), {
      target: { value: 'Ask Henry about rollout' },
    });
    fireEvent.click(screen.getByRole('button', { name: /capture/i }));

    await waitFor(() => {
      expect(v4API.capture).toHaveBeenCalledWith({
        content: 'Ask Henry about rollout',
        source: 'ui',
        mode: 'auto',
      });
    });
    // Capture log surfaces the saved note, warning, applied count, and suggestion link.
    expect(await screen.findByText(/Saved · Captured note/)).toBeInTheDocument();
    expect(screen.getByText('AI extraction degraded')).toBeInTheDocument();
    expect(screen.getByText(/1 applied/)).toBeInTheDocument();
    expect(screen.getByText(/1 suggestion pending/)).toBeInTheDocument();
  });

  it('lists recent notes from the v4 inbox API', async () => {
    renderInbox();
    expect(await screen.findByText('Older note')).toBeInTheDocument();
    expect(screen.getByText('Capture first, then review or file the note.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Review suggestions/i })).toHaveAttribute('href', '/suggestions');
    expect(screen.queryByText('Already captured')).not.toBeInTheDocument();
    expect(v4API.inbox).toHaveBeenCalledWith({ limit: 30 });
  });

  it('surfaces notes that need review separately from recent', async () => {
    v4API.inbox.mockResolvedValue({
      needs_review: [
        { id: 'n-review', title: 'Has pending suggestion', content: 'body', tags: [], pending_suggestion_count: 2, ai: { status: 'done' } },
      ],
      recent: [
        { id: 'n-recent', title: 'Already processed', content: 'body', tags: [], pending_suggestion_count: 0 },
      ],
    });
    renderInbox();
    expect(await screen.findByText('Needs review')).toBeInTheDocument();
    expect(screen.getByText('Has pending suggestion')).toBeInTheDocument();
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
