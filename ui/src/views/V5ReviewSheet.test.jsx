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

  it('dismisses a suggestion', async () => {
    renderSheet();

    const dismissButtons = await screen.findAllByRole('button', { name: 'Dismiss' });
    fireEvent.click(dismissButtons[1]);
    await waitFor(() => expect(v4API.suggestions.dismiss).toHaveBeenCalledWith('s2'));
    await waitFor(() => expect(screen.queryByText('Launch pilot')).not.toBeInTheDocument());
  });
});
