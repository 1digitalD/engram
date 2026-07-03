import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import V5ReviewSheet, { formatSuggestionType, suggestionTitle } from './V5ReviewSheet';
import { SummaryProvider } from '../context/SummaryContext';

vi.mock('../api/v4Client', () => ({
  v4API: {
    suggestions: {
      list: vi.fn(),
      accept: vi.fn(),
      dismiss: vi.fn(),
    },
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

import { v4API } from '../api/v4Client';

const SAMPLE_ROWS = [
  {
    id: 's1',
    suggestion_type: 'create_task',
    source_note_title: 'Standup note',
    reason: 'Follow up with design',
    payload: { title: 'Schedule design review' },
  },
  {
    id: 's2',
    suggestion_type: 'create_project',
    payload: { title: 'Launch pilot' },
  },
];

const GROUPED_ROWS = [
  {
    id: 'g1',
    suggestion_type: 'create_task',
    source_note_title: 'Weekly sync',
    payload: { title: 'Ship L2 rollout plan', group_id: 'note-1' },
  },
  {
    id: 'g2',
    suggestion_type: 'create_task',
    source_note_title: 'Weekly sync',
    payload: { title: 'Follow up with legal', group_id: 'note-1' },
  },
  {
    id: 'g3',
    suggestion_type: 'create_task',
    source_note_title: 'Weekly sync',
    payload: { title: 'Schedule migration call', group_id: 'note-1' },
  },
  {
    id: 's3',
    suggestion_type: 'create_task',
    payload: { title: 'Ungrouped task' },
  },
];

function renderSheet(props = {}) {
  const refreshSummary = vi.fn();
  const view = render(
    <SummaryProvider value={{ refreshSummary }}>
      <V5ReviewSheet open onClose={() => {}} {...props} />
    </SummaryProvider>,
  );
  return { refreshSummary, ...view };
}

describe('V5ReviewSheet helpers', () => {
  it('formats suggestion types for display', () => {
    expect(formatSuggestionType('create_task')).toBe('New task');
    expect(formatSuggestionType('link_existing')).toBe('link existing');
  });

  it('prefers payload title for row labels', () => {
    expect(suggestionTitle({ payload: { title: 'My task' } })).toBe('My task');
  });
});

describe('V5ReviewSheet', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.suggestions.list.mockResolvedValue({ data: SAMPLE_ROWS, meta: { total: 2 } });
    v4API.suggestions.accept.mockResolvedValue({ data: { id: 's1', status: 'accepted' } });
    v4API.suggestions.dismiss.mockResolvedValue({ data: { id: 's2', status: 'dismissed' } });
  });

  it('lists pending suggestions when opened', async () => {
    renderSheet();

    expect(await screen.findByRole('dialog', { name: 'Review suggestions' })).toBeInTheDocument();
    expect(await screen.findByText('Schedule design review')).toBeInTheDocument();
    expect(screen.getByText('Launch pilot')).toBeInTheDocument();
    expect(screen.getByText('From: Standup note')).toBeInTheDocument();
    expect(v4API.suggestions.list).toHaveBeenCalledWith({ status: 'pending' });
  });

  it('accepts a suggestion and refreshes summary', async () => {
    const { refreshSummary } = renderSheet();

    await screen.findByText('Schedule design review');
    const card = screen.getByText('Schedule design review').closest('li');
    fireEvent.click(within(card).getByRole('button', { name: 'Accept' }));
    await waitFor(() => expect(v4API.suggestions.accept).toHaveBeenCalledWith('s1'));
    await waitFor(() => expect(screen.queryByText('Schedule design review')).not.toBeInTheDocument());
    expect(refreshSummary).toHaveBeenCalled();
  });

  it('dismisses a suggestion without a reason', async () => {
    renderSheet();

    await screen.findByText('Launch pilot');
    const card = screen.getByText('Launch pilot').closest('li');
    fireEvent.click(within(card).getByRole('button', { name: 'Dismiss' }));
    fireEvent.click(await within(card).findByRole('button', { name: 'no reason' }));
    await waitFor(() => expect(v4API.suggestions.dismiss).toHaveBeenCalledWith('s2'));
    await waitFor(() => expect(screen.queryByText('Launch pilot')).not.toBeInTheDocument());
  });

  it('shows the evidence quote in the row when present', async () => {
    v4API.suggestions.list.mockResolvedValue({
      data: [
        {
          id: 's-evidence',
          suggestion_type: 'create_task',
          source_note_title: 'Standup note',
          payload: { title: 'Schedule design review', evidence: 'follow up with design tomorrow' },
        },
      ],
      meta: { total: 1 },
    });
    renderSheet();

    expect(await screen.findByText('follow up with design tomorrow')).toBeInTheDocument();
  });

  it('lets the user pick a dismiss reason', async () => {
    renderSheet();

    await screen.findByText('Launch pilot');
    const card = screen.getByText('Launch pilot').closest('li');
    fireEvent.click(within(card).getByRole('button', { name: 'Dismiss' }));

    const reasonButton = await within(card).findByRole('button', { name: 'not mine' });
    fireEvent.click(reasonButton);

    await waitFor(() => expect(v4API.suggestions.dismiss).toHaveBeenCalledWith('s2', { dismiss_reason: 'not mine' }));
    await waitFor(() => expect(screen.queryByText('Launch pilot')).not.toBeInTheDocument());
  });

  it('cancels the dismiss reason picker', async () => {
    renderSheet();

    await screen.findByText('Launch pilot');
    const card = screen.getByText('Launch pilot').closest('li');
    fireEvent.click(within(card).getByRole('button', { name: 'Dismiss' }));

    const cancelButton = await within(card).findByRole('button', { name: 'Cancel' });
    fireEvent.click(cancelButton);

    expect(v4API.suggestions.dismiss).not.toHaveBeenCalled();
    expect(within(card).getByRole('button', { name: 'Dismiss' })).toBeInTheDocument();
  });

  it('renders grouped suggestions with accept-all control', async () => {
    v4API.suggestions.list.mockResolvedValue({ data: GROUPED_ROWS, meta: { total: 4 } });
    renderSheet();

    expect(await screen.findByText('3 action items from this note')).toBeInTheDocument();
    expect(screen.getByText('Ship L2 rollout plan')).toBeInTheDocument();
    expect(screen.getByText('Follow up with legal')).toBeInTheDocument();
    expect(screen.getByText('Schedule migration call')).toBeInTheDocument();
    expect(screen.getByText('Ungrouped task')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Accept all' })).toBeInTheDocument();
  });

  it('accepts all grouped suggestions and refreshes summary', async () => {
    v4API.suggestions.list.mockResolvedValue({ data: GROUPED_ROWS, meta: { total: 4 } });
    const { refreshSummary } = renderSheet();

    await screen.findByText('3 action items from this note');
    fireEvent.click(screen.getByRole('button', { name: 'Accept all' }));

    await waitFor(() => expect(v4API.suggestions.accept).toHaveBeenCalledTimes(3));
    expect(v4API.suggestions.accept).toHaveBeenCalledWith('g1');
    expect(v4API.suggestions.accept).toHaveBeenCalledWith('g2');
    expect(v4API.suggestions.accept).toHaveBeenCalledWith('g3');

    await waitFor(() => expect(screen.queryByText('Ship L2 rollout plan')).not.toBeInTheDocument());
    expect(screen.queryByText('Follow up with legal')).not.toBeInTheDocument();
    expect(screen.queryByText('Schedule migration call')).not.toBeInTheDocument();
    expect(screen.getByText('Ungrouped task')).toBeInTheDocument();
    expect(refreshSummary).toHaveBeenCalled();
  });

  it('still supports per-row dismiss within a group', async () => {
    v4API.suggestions.list.mockResolvedValue({ data: GROUPED_ROWS, meta: { total: 4 } });
    renderSheet();

    await screen.findByText('Ship L2 rollout plan');
    const groupRow = screen.getByText('Ship L2 rollout plan').closest('li');
    fireEvent.click(within(groupRow).getByRole('button', { name: 'Dismiss' }));
    fireEvent.click(await within(groupRow).findByRole('button', { name: 'no reason' }));

    await waitFor(() => expect(v4API.suggestions.dismiss).toHaveBeenCalledWith('g1'));
    await waitFor(() => expect(screen.queryByText('Ship L2 rollout plan')).not.toBeInTheDocument());
    expect(screen.getByText('Follow up with legal')).toBeInTheDocument();
  });
});
