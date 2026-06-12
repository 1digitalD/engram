/* eslint-disable no-unused-vars */
import React from 'react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import { v4API } from '../api/v4Client';
import V4Suggestions from './V4Suggestions';

vi.mock('../components/MarkdownContent', () => ({
  default: ({ content }) => content || null,
}));

vi.mock('../api/v4Client', () => ({
  v4API: {
    inbox: vi.fn(),
    entities: {
      get: vi.fn(),
      update: vi.fn(),
      delete: vi.fn(),
    },
    suggestions: {
      list: vi.fn(),
      accept: vi.fn(),
      dismiss: vi.fn(),
      update: vi.fn(),
      reconcile: vi.fn(),
    },
    review: {
      resolve: vi.fn(),
    },
    reprocess: vi.fn(),
  },
}));

describe('V4Suggestions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.inbox.mockResolvedValue({ needs_review: [], recent: [] });
    v4API.entities.update.mockResolvedValue({});
    v4API.entities.delete.mockResolvedValue({});
    v4API.review.resolve.mockResolvedValue({ data: {} });
  });

  it('lists pending suggestions and accepts one through the v4 review API', async () => {
    v4API.inbox.mockResolvedValue({
      needs_review: [
        {
          id: 'n1',
          type: 'note',
          title: 'Weekly note',
          content: 'Ask Henry about rollout',
          updated_at: '2026-05-20T10:00:00+00:00',
          pending_suggestion_count: 2,
          ai: { status: 'done', confidence: 0.88 },
        },
      ],
      recent: [],
    });
    v4API.suggestions.list.mockResolvedValue({
      data: [
        {
          id: 's1',
          suggestion_type: 'create_task',
          operation_type: 'create_entity',
          source_entity_id: 'n1',
          source_note_title: 'Weekly note',
          payload: { type: 'task', title: 'Follow up with Henry' },
          confidence: 0.91,
          reason: 'follow up',
          created_at: '2026-05-20T09:00:00+00:00',
        },
        {
          id: 's2',
          suggestion_type: 'link_existing',
          operation_type: 'link_existing',
          source_entity_id: 'n1',
          source_note_title: 'Weekly note',
          payload: { title: 'Memory Lookup', target_type: 'project', relationship_type: 'related' },
          reason: 'mentions Memory Lookup',
        },
      ],
    });
    v4API.suggestions.accept.mockResolvedValue({ suggestion: { id: 's1', status: 'accepted' } });
    v4API.suggestions.list
      .mockResolvedValueOnce({
        data: [
          {
            id: 's1',
            suggestion_type: 'create_task',
            operation_type: 'create_entity',
            source_entity_id: 'n1',
            source_note_title: 'Weekly note',
            payload: { type: 'task', title: 'Follow up with Henry' },
            confidence: 0.91,
            reason: 'follow up',
            created_at: '2026-05-20T09:00:00+00:00',
          },
          {
            id: 's2',
            suggestion_type: 'link_existing',
            operation_type: 'link_existing',
            source_entity_id: 'n1',
            source_note_title: 'Weekly note',
            payload: { title: 'Memory Lookup', target_type: 'project', relationship_type: 'related' },
            reason: 'mentions Memory Lookup',
          },
        ],
      })
      .mockResolvedValueOnce({ data: [] });
    v4API.inbox
      .mockResolvedValueOnce({
        needs_review: [
          {
            id: 'n1',
            type: 'note',
            title: 'Weekly note',
            content: 'Ask Henry about rollout',
            updated_at: '2026-05-20T10:00:00+00:00',
            pending_suggestion_count: 2,
            ai: { status: 'done', confidence: 0.88 },
          },
        ],
        recent: [],
      })
      .mockResolvedValueOnce({ needs_review: [], recent: [] });

    render(<MemoryRouter><V4Suggestions /></MemoryRouter>);

    expect(await screen.findByText('Review queue')).toBeInTheDocument();
    expect(await screen.findByText('Weekly note')).toBeInTheDocument();
    expect(screen.getByText('Ask Henry about rollout')).toBeInTheDocument();
    expect(screen.getByText('Follow up with Henry')).toBeInTheDocument();
    expect(screen.getByText('Memory Lookup')).toBeInTheDocument();
    expect(screen.getByText('91% confidence')).toBeInTheDocument();
    expect(screen.getByText('AI · done')).toBeInTheDocument();
    expect(screen.getByText('88% confidence')).toBeInTheDocument();

    const card = screen.getByText('Follow up with Henry').closest('li');
    await userEvent.click(within(card).getByRole('button', { name: 'Accept' }));

    await waitFor(() => expect(v4API.suggestions.accept).toHaveBeenCalledWith('s1'));
    await waitFor(() => expect(v4API.suggestions.list).toHaveBeenCalledTimes(2));
    expect(screen.queryByText('Follow up with Henry')).not.toBeInTheDocument();
    expect(screen.getByText('No pending suggestions.')).toBeInTheDocument();
  });

  it('dismisses suggestions without accepting risky changes', async () => {
    v4API.inbox.mockResolvedValue({
      needs_review: [
        { id: 'n2', type: 'note', title: 'Maybe note', content: 'maybe content', pending_suggestion_count: 1, ai: { status: 'done' } },
      ],
      recent: [],
    });
    v4API.suggestions.list.mockResolvedValue({
      data: [
        {
          id: 's3',
          suggestion_type: 'create_project',
          operation_type: 'create_entity',
          source_entity_id: 'n2',
          payload: { type: 'project', title: 'Maybe project' },
        },
      ],
    });
    v4API.suggestions.list.mockResolvedValueOnce({
      data: [
        {
          id: 's3',
          suggestion_type: 'create_project',
          operation_type: 'create_entity',
          source_entity_id: 'n2',
          payload: { type: 'project', title: 'Maybe project' },
        },
      ],
    }).mockResolvedValueOnce({ data: [] });
    v4API.inbox.mockResolvedValueOnce({
      needs_review: [
        { id: 'n2', type: 'note', title: 'Maybe note', content: 'maybe content', pending_suggestion_count: 1, ai: { status: 'done' } },
      ],
      recent: [],
    }).mockResolvedValueOnce({ needs_review: [], recent: [] });
    v4API.suggestions.dismiss.mockResolvedValue({ data: { id: 's3', status: 'dismissed' } });

    render(<MemoryRouter><V4Suggestions /></MemoryRouter>);

    const card = (await screen.findByText('Maybe project')).closest('li');
    await userEvent.click(within(card).getByRole('button', { name: 'Dismiss' }));

    await waitFor(() => expect(v4API.suggestions.dismiss).toHaveBeenCalledWith('s3'));
    expect(screen.queryByText('Maybe project')).not.toBeInTheDocument();
  });

  it('supports clearing a whole source-note group at once', async () => {
    v4API.inbox.mockResolvedValue({
      needs_review: [
        { id: 'n10', type: 'note', title: 'Grouped note', content: 'note body', pending_suggestion_count: 2, ai: { status: 'done' } },
      ],
      recent: [],
    });
    v4API.suggestions.list.mockResolvedValue({
      data: [
        {
          id: 's10',
          suggestion_type: 'create_task',
          operation_type: 'create_entity',
          source_entity_id: 'n10',
          payload: { type: 'task', title: 'Task one' },
        },
        {
          id: 's11',
          suggestion_type: 'create_task',
          operation_type: 'create_entity',
          source_entity_id: 'n10',
          payload: { type: 'task', title: 'Task two' },
        },
      ],
    });
    v4API.suggestions.list
      .mockResolvedValueOnce({
        data: [
          {
            id: 's10',
            suggestion_type: 'create_task',
            operation_type: 'create_entity',
            source_entity_id: 'n10',
            payload: { type: 'task', title: 'Task one' },
          },
          {
            id: 's11',
            suggestion_type: 'create_task',
            operation_type: 'create_entity',
            source_entity_id: 'n10',
            payload: { type: 'task', title: 'Task two' },
          },
        ],
      })
      .mockResolvedValueOnce({ data: [] });
    v4API.inbox
      .mockResolvedValueOnce({
        needs_review: [
          { id: 'n10', type: 'note', title: 'Grouped note', content: 'note body', pending_suggestion_count: 2, ai: { status: 'done' } },
        ],
        recent: [],
      })
      .mockResolvedValueOnce({ needs_review: [], recent: [] });
    v4API.suggestions.accept.mockResolvedValue({});

    render(<MemoryRouter><V4Suggestions /></MemoryRouter>);

    expect(await screen.findByText('Grouped note')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Accept all' }));

    await waitFor(() => expect(v4API.suggestions.accept).toHaveBeenCalledWith('s10'));
    expect(v4API.suggestions.accept).toHaveBeenCalledWith('s11');
    expect(screen.queryByText('Task one')).not.toBeInTheDocument();
    expect(screen.queryByText('Task two')).not.toBeInTheDocument();
  });

  it('hides zero-confidence provenance pills', async () => {
    v4API.inbox.mockResolvedValue({
      needs_review: [
        {
          id: 'n20',
          type: 'note',
          title: 'Zero note',
          content: 'body',
          pending_suggestion_count: 1,
          ai: { status: 'done', confidence: 0 },
        },
      ],
      recent: [],
    });
    v4API.suggestions.list.mockResolvedValue({
      data: [
        {
          id: 's20',
          suggestion_type: 'create_task',
          operation_type: 'create_entity',
          source_entity_id: 'n20',
          payload: { type: 'task', title: 'Task zero' },
          confidence: 0,
        },
      ],
    });

    render(<MemoryRouter><V4Suggestions /></MemoryRouter>);

    expect(await screen.findByText('Zero note')).toBeInTheDocument();
    expect(screen.queryByText('0% confidence')).not.toBeInTheDocument();
  });

  it('reconciles stale suggestions and refreshes the queue', async () => {
    v4API.inbox
      .mockResolvedValueOnce({
        needs_review: [
          { id: 'n30', type: 'note', title: 'Stale note', content: 'body', pending_suggestion_count: 1, ai: { status: 'done' } },
        ],
        recent: [],
      })
      .mockResolvedValueOnce({ needs_review: [], recent: [] });
    v4API.suggestions.list
      .mockResolvedValueOnce({
        data: [
          {
            id: 's30',
            suggestion_type: 'create_task',
            operation_type: 'create_entity',
            source_entity_id: 'n30',
            payload: { type: 'task', title: 'Task stale' },
          },
        ],
      })
      .mockResolvedValueOnce({ data: [] });
    v4API.suggestions.reconcile.mockResolvedValue({
      data: [{ id: 's30', suggestion_type: 'create_task' }],
      meta: { expired: 1, scanned: 1 },
    });

    render(<MemoryRouter><V4Suggestions /></MemoryRouter>);

    expect(await screen.findByText('Stale note')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Reconcile stale suggestions/i }));

    await waitFor(() => expect(v4API.suggestions.reconcile).toHaveBeenCalledWith({ limit: 200 }));
    await waitFor(() => expect(v4API.suggestions.list).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('Expired 1 stale suggestion.')).toBeInTheDocument();
    expect(screen.getByText('No pending suggestions.')).toBeInTheDocument();
  });

  it('shows AI attention notes even when there are no pending suggestions', async () => {
    v4API.inbox.mockResolvedValue({
      needs_review: [
        {
          id: 'n40',
          type: 'note',
          title: 'Failed note',
          content: 'stuck body',
          pending_suggestion_count: 0,
          updated_at: '2026-05-20T10:00:00+00:00',
          ai: { status: 'failed' },
        },
      ],
      recent: [],
    });
    v4API.suggestions.list.mockResolvedValue({ data: [] });

    render(<MemoryRouter><V4Suggestions /></MemoryRouter>);

    expect(await screen.findByText('AI attention')).toBeInTheDocument();
    expect(screen.getByText('Failed note')).toBeInTheDocument();
    expect(screen.getByText('AI · failed')).toBeInTheDocument();
    expect(screen.getByText(/AI extraction failed. Re-run extraction to move this note forward./i)).toBeInTheDocument();
    expect(screen.getByText('No pending suggestions.')).toBeInTheDocument();
  });

  it('allows archiving a review note directly from the review queue', async () => {
    v4API.inbox
      .mockResolvedValueOnce({
        needs_review: [
          {
            id: 'n50',
            type: 'note',
            title: 'Archive me',
            content: 'clear this from review',
            pending_suggestion_count: 0,
            updated_at: '2026-05-20T10:00:00+00:00',
            ai: { status: 'failed' },
          },
        ],
        recent: [],
      })
      .mockResolvedValueOnce({ needs_review: [], recent: [] });
    v4API.suggestions.list
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: [] });

    render(<MemoryRouter><V4Suggestions /></MemoryRouter>);

    const card = (await screen.findByText('Archive me')).closest('li');
    await userEvent.hover(card);
    await userEvent.click(within(card).getByRole('button', { name: /Archive Archive me/i }));

    await waitFor(() => expect(v4API.entities.update).toHaveBeenCalledWith('n50', { lifecycle: 'archived' }));
    await waitFor(() => expect(v4API.inbox).toHaveBeenCalledTimes(2));
    expect(screen.queryByText('Archive me')).not.toBeInTheDocument();
  });

  it('marks a review note as reviewed without archiving or deleting it', async () => {
    v4API.inbox
      .mockResolvedValueOnce({
        needs_review: [
          {
            id: 'n60',
            type: 'note',
            title: 'Looks fine',
            content: 'leave as-is',
            pending_suggestion_count: 0,
            updated_at: '2026-05-20T10:00:00+00:00',
            ai: { status: 'failed' },
          },
        ],
        recent: [],
      })
      .mockResolvedValueOnce({ needs_review: [], recent: [] });
    v4API.suggestions.list
      .mockResolvedValueOnce({ data: [] })
      .mockResolvedValueOnce({ data: [] });

    render(<MemoryRouter><V4Suggestions /></MemoryRouter>);

    const card = (await screen.findByText('Looks fine')).closest('li');
    await userEvent.click(within(card).getByRole('button', { name: /Mark reviewed/i }));

    await waitFor(() => expect(v4API.review.resolve).toHaveBeenCalledWith('n60'));
    await waitFor(() => expect(v4API.inbox).toHaveBeenCalledTimes(2));
    expect(screen.queryByText('Looks fine')).not.toBeInTheDocument();
  });
});

describe('near-match resolution', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.inbox.mockResolvedValue({ needs_review: [], recent: [] });
  });

  it('offers "Use existing" on suggestions with a near match and resolves through the API', async () => {
    v4API.suggestions.list.mockResolvedValue({
      data: [
        {
          id: 's9',
          suggestion_type: 'create_project',
          operation_type: 'create_entity',
          source_entity_id: 'n1',
          source_note_title: 'Roadmap note',
          payload: {
            type: 'project',
            title: 'Plan agent platform roadmap',
            near_match: { entity_id: 'p1', title: 'Define Agent Platform roadmap', score: 0.82 },
          },
          confidence: 0.9,
          created_at: '2026-06-11T09:00:00+00:00',
        },
      ],
    });
    v4API.entities.get.mockResolvedValue({ data: { id: 'n1', title: 'Roadmap note', type: 'note' } });
    v4API.suggestions.resolveToExisting = vi.fn().mockResolvedValue({ suggestion: { id: 's9', status: 'accepted' } });

    render(
      <MemoryRouter>
        <V4Suggestions />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Define Agent Platform roadmap/)).toBeInTheDocument();
    expect(screen.getByText(/82% similar/)).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Use existing' }));

    await waitFor(() => expect(v4API.suggestions.resolveToExisting).toHaveBeenCalledWith('s9'));
  });
});
