import React from 'react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import { v4API } from '../api/v4Client';
import V4Suggestions from './V4Suggestions';

vi.mock('../api/v4Client', () => ({
  v4API: {
    suggestions: {
      list: vi.fn(),
      accept: vi.fn(),
      dismiss: vi.fn(),
    },
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
          payload: { type: 'task', title: 'Follow up with Henry' },
          reason: 'follow up',
        },
        {
          id: 's2',
          suggestion_type: 'link_existing',
          operation_type: 'link_existing',
          payload: { title: 'Memory Lookup', target_type: 'project', relationship_type: 'related' },
          reason: 'mentions Memory Lookup',
        },
      ],
    });
    v4API.suggestions.accept.mockResolvedValue({ suggestion: { id: 's1', status: 'accepted' } });

    render(<V4Suggestions />);

    expect(await screen.findByText('Follow up with Henry')).toBeInTheDocument();
    expect(screen.getByText('Memory Lookup')).toBeInTheDocument();

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
          payload: { type: 'project', title: 'Maybe project' },
        },
      ],
    });
    v4API.suggestions.dismiss.mockResolvedValue({ data: { id: 's3', status: 'dismissed' } });

    render(<V4Suggestions />);

    const card = (await screen.findByText('Maybe project')).closest('li');
    await userEvent.click(within(card).getByRole('button', { name: 'Dismiss' }));

    await waitFor(() => expect(v4API.suggestions.dismiss).toHaveBeenCalledWith('s3'));
    expect(screen.queryByText('Maybe project')).not.toBeInTheDocument();
  });
});
