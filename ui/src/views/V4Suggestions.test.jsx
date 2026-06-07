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
    entities: {
      get: vi.fn(),
    },
    suggestions: {
      list: vi.fn(),
      accept: vi.fn(),
      dismiss: vi.fn(),
      update: vi.fn(),
    },
    reprocess: vi.fn(),
  },
}));

describe('V4Suggestions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('lists pending suggestions and accepts one through the v4 review API', async () => {
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
    v4API.entities.get.mockResolvedValue({
      data: {
        id: 'n1',
        type: 'note',
        title: 'Weekly note',
        content: 'Ask Henry about rollout',
        updated_at: '2026-05-20T10:00:00+00:00',
        ai: { status: 'done', confidence: 0.88 },
      },
    });
    v4API.suggestions.accept.mockResolvedValue({ suggestion: { id: 's1', status: 'accepted' } });

    render(<MemoryRouter><V4Suggestions /></MemoryRouter>);

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
    expect(screen.queryByText('Follow up with Henry')).not.toBeInTheDocument();
    expect(screen.getByText('Memory Lookup')).toBeInTheDocument();
  });

  it('dismisses suggestions without accepting risky changes', async () => {
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
    v4API.entities.get.mockResolvedValue({
      data: { id: 'n2', type: 'note', title: 'Maybe note', content: 'maybe content' },
    });
    v4API.suggestions.dismiss.mockResolvedValue({ data: { id: 's3', status: 'dismissed' } });

    render(<MemoryRouter><V4Suggestions /></MemoryRouter>);

    const card = (await screen.findByText('Maybe project')).closest('li');
    await userEvent.click(within(card).getByRole('button', { name: 'Dismiss' }));

    await waitFor(() => expect(v4API.suggestions.dismiss).toHaveBeenCalledWith('s3'));
    expect(screen.queryByText('Maybe project')).not.toBeInTheDocument();
  });

  it('supports clearing a whole source-note group at once', async () => {
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
    v4API.entities.get.mockResolvedValue({
      data: { id: 'n10', type: 'note', title: 'Grouped note', content: 'note body' },
    });
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
    v4API.entities.get.mockResolvedValue({
      data: {
        id: 'n20',
        type: 'note',
        title: 'Zero note',
        content: 'body',
        ai: { status: 'done', confidence: 0 },
      },
    });

    render(<MemoryRouter><V4Suggestions /></MemoryRouter>);

    expect(await screen.findByText('Zero note')).toBeInTheDocument();
    expect(screen.queryByText('0% confidence')).not.toBeInTheDocument();
  });
});
