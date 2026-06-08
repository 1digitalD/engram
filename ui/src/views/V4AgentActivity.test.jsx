import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { v4API } from '../api/v4Client';
import V4AgentActivity from './V4AgentActivity';

vi.mock('../api/v4Client', () => ({
  v4API: {
    agentActivity: vi.fn(),
  },
}));

describe('V4AgentActivity', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders agent automation audit items', async () => {
    v4API.agentActivity.mockResolvedValue({
      meta: { counts: { auto_applied: 1, suggested: 1, failed: 0, review_action: 0 } },
      data: [
        {
          id: 'e1',
          kind: 'event',
          category: 'auto_applied',
          event_type: 'ai_updated',
          actor: 'agent:v4-capture',
          confidence: 0.91,
          reason: 'summary updated',
          created_at: '2026-06-07T10:00:00Z',
          entity: { id: 'n1', type: 'note', title: 'Source note' },
        },
        {
          id: 's1',
          kind: 'suggestion',
          category: 'suggested',
          event_type: 'create_task',
          actor: 'agent:v4-capture',
          confidence: 0.64,
          reason: 'low confidence task',
          created_at: '2026-06-07T09:00:00Z',
          entity: { id: 'n1', type: 'note', title: 'Source note' },
        },
      ],
    });

    render(
      <MemoryRouter>
        <V4AgentActivity />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Recent automation')).toBeInTheDocument();
    expect(screen.getAllByText('auto applied').length).toBeGreaterThan(0);
    expect(screen.getByText('create task')).toBeInTheDocument();
    expect(screen.getAllByText(/Source note/).length).toBeGreaterThan(0);
    expect(screen.getByText('91%')).toBeInTheDocument();
    expect(v4API.agentActivity).toHaveBeenCalledWith({ limit: 80 });
  });
});
