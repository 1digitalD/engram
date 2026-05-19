import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import V4Inbox from './V4Inbox';
import { v4API } from '../api/v4Client';

vi.mock('../api/v4Client', () => ({
  v4API: {
    capture: vi.fn(),
    entities: {
      list: vi.fn(),
    },
  },
}));

describe('V4Inbox', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.entities.list.mockResolvedValue({
      data: [{ id: 'n-old', title: 'Older note', content: 'Already captured' }],
    });
  });

  it('captures text and shows the saved note, warnings, and suggestions', async () => {
    v4API.capture.mockResolvedValue({
      source_note: { id: 'n1', title: 'Captured note', content: 'Ask Henry about rollout' },
      applied_changes: [{ type: 'summary_updated' }],
      suggestions: [{ id: 's1', suggestion_type: 'create_task', payload: { title: 'Follow up with Henry' } }],
      warnings: ['AI extraction degraded'],
    });

    render(<V4Inbox />);

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
    expect(await screen.findAllByText('Captured note')).toHaveLength(2);
    expect(screen.getByText('AI extraction degraded')).toBeInTheDocument();
    expect(screen.getByText('Follow up with Henry')).toBeInTheDocument();
    expect(screen.getByText('summary_updated')).toBeInTheDocument();
  });

  it('lists recent notes from the v4 entity API', async () => {
    render(<V4Inbox />);

    expect(await screen.findByText('Older note')).toBeInTheDocument();
    expect(v4API.entities.list).toHaveBeenCalledWith({ type: 'note', limit: 20 });
  });
});
