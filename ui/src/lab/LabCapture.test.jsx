import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import LabCapture, {
  captureEventLabel,
  formatAppliedChangeLabel,
  formatConfidence,
} from './LabCapture';

vi.mock('../api/v4Client', () => ({
  v4API: {
    capture: vi.fn(),
    entities: {
      captureChanges: vi.fn(),
    },
    events: {
      revert: vi.fn(),
    },
    suggestions: {
      accept: vi.fn(),
      dismiss: vi.fn(),
      resolveToExisting: vi.fn(),
    },
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

import { v4API } from '../api/v4Client';

const CAPTURE_RESULT = {
  source_note: { id: 'note-1', title: 'Rollout note', type: 'note' },
  applied_changes: [
    {
      type: 'entity_created',
      entity_id: 'task-1',
      entity_type: 'task',
      title: 'Follow up with Henry',
      confidence: 0.91,
      reason: 'concrete follow-up with named owner',
      match_confidence: 0.91,
      matched_entity: { id: 'task-1', type: 'task', title: 'Follow up with Henry' },
    },
  ],
  suggestions: [
    {
      id: 'sug-1',
      suggestion_type: 'create_task',
      payload: {
        title: 'Review vendor terms',
        evidence: 'maybe review vendor terms next week',
        near_match: { entity_id: 'task-2', title: 'Vendor contract', score: 0.72 },
      },
      confidence: 0.62,
      reason: 'maybe review vendor terms next week',
      match_confidence: 0.72,
      matched_entity: { id: 'task-2', type: 'task', title: 'Vendor contract' },
    },
  ],
  warnings: [],
};

const RECEIPT_EVENTS = [
  {
    id: 'evt-1',
    event_type: 'created',
    reason: 'Need to follow up with Henry about rollout',
    confidence: 0.91,
    new_value: { type: 'task', title: 'Follow up with Henry' },
    reverted_at: null,
  },
];

function renderCapture(props = {}) {
  return render(
    <LabCapture open onClose={() => {}} captureFn={v4API.capture} {...props} />,
  );
}

describe('LabCapture helpers', () => {
  it('formats applied change labels and confidence', () => {
    expect(formatAppliedChangeLabel({ type: 'entity_created', entity_type: 'task', title: 'Ship' }))
      .toBe('Created task: Ship');
    expect(formatConfidence(0.91)).toBe('91%');
    expect(captureEventLabel(RECEIPT_EVENTS[0])).toContain('Follow up with Henry');
  });
});

describe('LabCapture', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.capture.mockResolvedValue(CAPTURE_RESULT);
    v4API.entities.captureChanges.mockResolvedValue({ data: RECEIPT_EVENTS });
    v4API.events.revert.mockResolvedValue({});
    v4API.suggestions.accept.mockResolvedValue({});
    v4API.suggestions.dismiss.mockResolvedValue({});
    v4API.suggestions.resolveToExisting.mockResolvedValue({});
  });

  it('runs capture and shows auto-applied reasoning in review', async () => {
    renderCapture();

    fireEvent.change(screen.getByLabelText('Capture text'), {
      target: { value: 'Need to follow up with Henry about rollout' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Capture' }));

    await waitFor(() => expect(screen.getByText('Review capture')).toBeInTheDocument());
    expect(v4API.capture).toHaveBeenCalledWith({
      content: 'Need to follow up with Henry about rollout',
      source: 'lab',
      mode: 'auto',
    });
    expect(screen.getByText('Created task: Follow up with Henry')).toBeInTheDocument();
    expect(screen.getByText('concrete follow-up with named owner')).toBeInTheDocument();
    expect(screen.getByText('Confidence: 91%')).toBeInTheDocument();
  });

  it('resolves ambiguous suggestions inline before receipt', async () => {
    renderCapture();

    fireEvent.change(screen.getByLabelText('Capture text'), {
      target: { value: 'Need to follow up with Henry about rollout' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Capture' }));
    await waitFor(() => expect(screen.getByText('Review vendor terms')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Use match' }));
    await waitFor(() => expect(v4API.suggestions.resolveToExisting).toHaveBeenCalledWith('sug-1', 'task-2'));
    expect(screen.queryByText('Review vendor terms')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'View receipt' }));
    await waitFor(() => expect(screen.getByText('Capture receipt')).toBeInTheDocument());
    expect(v4API.entities.captureChanges).toHaveBeenCalledWith('note-1');
  });

  it('shows receipt undo controls and reverts a change', async () => {
    renderCapture();

    fireEvent.change(screen.getByLabelText('Capture text'), {
      target: { value: 'Need to follow up with Henry about rollout' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Capture' }));
    await waitFor(() => expect(screen.getByText('Review capture')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    await waitFor(() => expect(v4API.suggestions.dismiss).toHaveBeenCalledWith('sug-1'));

    fireEvent.click(screen.getByRole('button', { name: 'View receipt' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Undo' })).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: 'Undo' }));
    await waitFor(() => expect(v4API.events.revert).toHaveBeenCalledWith('evt-1'));
    expect(v4API.entities.captureChanges).toHaveBeenCalledTimes(2);
  });
});
