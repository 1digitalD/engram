import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import CommitmentDetailSurface from './CommitmentDetailSurface';

vi.mock('../api/v4Client', () => ({
  v4API: {
    entities: {
      detail: vi.fn(),
      list: vi.fn(),
      update: vi.fn(),
      createLink: vi.fn(),
    },
    activityUpdates: {
      create: vi.fn(),
    },
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

import { v4API } from '../api/v4Client';

const TASK_DETAIL = {
  entity: {
    id: 'task-contract',
    type: 'task',
    title: 'Close contract',
    status: 'open',
    content: 'Finalize the renewal paperwork.',
    due_at: '2026-07-11T12:00:00Z',
    projects: [],
    areas: [],
    people: [{ id: 'person-operator', title: 'Operator' }],
  },
  sections: [
    {
      key: 'source_notes',
      items: [{ entity: { id: 'note-1', title: 'Standup note' } }],
    },
  ],
};

function renderDetail(taskId = 'task-contract') {
  return render(
    <MemoryRouter initialEntries={[`/commitments/${taskId}`]}>
      <Routes>
        <Route path="/commitments/:taskId" element={<CommitmentDetailSurface />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('CommitmentDetailSurface', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.entities.detail.mockResolvedValue(TASK_DETAIL);
    v4API.entities.list.mockImplementation(async (params = {}) => {
      if (params.type === 'person') {
        return { data: [{ id: 'person-operator', title: 'Operator' }] };
      }
      return { data: [{ id: 'space-apollo', title: 'Apollo', type: 'project' }] };
    });
  });

  it('loads stand-alone commitment detail with assign affordance', async () => {
    renderDetail();

    expect(await screen.findByRole('heading', { name: 'Close contract' })).toBeInTheDocument();
    expect(screen.getByText('Finalize the renewal paperwork.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /assign to space/i })).toBeInTheDocument();
    expect(screen.getByText('Standup note')).toBeInTheDocument();
    expect(v4API.entities.detail).toHaveBeenCalledWith('task-contract');
  });

  it('assigns a stand-alone commitment to a space from the modal', async () => {
    v4API.entities.createLink.mockResolvedValue({});
    renderDetail();

    fireEvent.click(await screen.findByRole('button', { name: /assign to space/i }));
    fireEvent.click(await screen.findByRole('button', { name: 'Apollo' }));

    await waitFor(() =>
      expect(v4API.entities.createLink).toHaveBeenCalledWith('task-contract', {
        target_id: 'space-apollo',
        relationship_type: 'parent',
        replace_existing: true,
        batch_summary: 'assign commitment to space',
      }),
    );
    await waitFor(() =>
      expect(v4API.entities.detail).toHaveBeenCalledTimes(2),
    );
  });
});
