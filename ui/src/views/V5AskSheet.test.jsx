import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import V5AskSheet from './V5AskSheet';

const mockAsk = vi.fn();
const mockOpenCapture = vi.fn();

vi.mock('../api/v4Client', () => ({
  v4API: {
    ask: (...args) => mockAsk(...args),
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

vi.mock('../context/CaptureContext', () => ({
  CaptureProvider: ({ children }) => <>{children}</>,
  useCapture: () => ({ openCapture: mockOpenCapture }),
}));

function renderSheet(initialPath = '/', props = {}) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="*" element={<V5AskSheet open {...props} />} />
      </Routes>
    </MemoryRouter>,
  );
}

const IDK_RESPONSE = {
  answer: "I don't have anything in the workspace that answers this.",
  citations: [],
  confidence: 'low',
  caveats: [
    'The retrieved context does not contain enough information to answer this question.',
  ],
  suggested_actions: [
    {
      type: 'capture',
      label: 'Capture starting point',
      payload: { content: 'What did Danish decide about Phase 4?' },
    },
  ],
};

const GROUNDED_RESPONSE = {
  answer: 'Danish decided to defer Phase 4 until the user research is complete.',
  citations: [
    {
      entity_id: 'note-1',
      snippet: 'Danish decided to defer Phase 4 until user research is complete.',
      relevance: 0.92,
    },
  ],
  confidence: 'medium',
  caveats: [],
  suggested_actions: [
    {
      type: 'open',
      label: 'Open source',
      payload: { entity_id: 'note-1' },
    },
  ],
};

describe('V5AskSheet', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the honest IDK state for the canonical low-confidence response', async () => {
    mockAsk.mockResolvedValue(IDK_RESPONSE);
    renderSheet();

    fireEvent.change(screen.getByLabelText('Question'), {
      target: { value: 'What did Danish decide about Phase 4?' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));

    await waitFor(() => {
      expect(screen.getByText(IDK_RESPONSE.answer)).toBeInTheDocument();
    });

    // Caveats from the IDK envelope should be visible.
    expect(screen.getByText(IDK_RESPONSE.caveats[0])).toBeInTheDocument();

    // The capture action should be offered, not source-open actions.
    expect(
      screen.getByRole('button', { name: /Capture starting point/i }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Open source/i })).not.toBeInTheDocument();

    // Citations must not be rendered as if this were a grounded answer.
    expect(screen.queryByText('📝')).not.toBeInTheDocument();
    expect(screen.queryByText(/Open citation/i)).not.toBeInTheDocument();
  });

  it('renders a grounded answer with citations when confidence is not low', async () => {
    mockAsk.mockResolvedValue(GROUNDED_RESPONSE);
    renderSheet();

    fireEvent.change(screen.getByLabelText('Question'), {
      target: { value: 'What did Danish decide?' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));

    await waitFor(() => {
      expect(screen.getByText(GROUNDED_RESPONSE.answer)).toBeInTheDocument();
    });

    // Citation glyph and snippet should be visible.
    expect(screen.getByText('📝')).toBeInTheDocument();
    expect(screen.getByText(GROUNDED_RESPONSE.citations[0].snippet)).toBeInTheDocument();

    // Open-source action should be offered.
    expect(screen.getByRole('button', { name: /Open source/i })).toBeInTheDocument();
  });

  it('opens capture with the question when the IDK capture action is clicked', async () => {
    const onClose = vi.fn();
    mockAsk.mockResolvedValue(IDK_RESPONSE);
    renderSheet('/', { onClose });

    fireEvent.change(screen.getByLabelText('Question'), {
      target: { value: 'What did Danish decide about Phase 4?' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Ask' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Capture starting point/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Capture starting point/i }));

    expect(onClose).toHaveBeenCalled();
    expect(mockOpenCapture).toHaveBeenCalledWith('What did Danish decide about Phase 4?');
  });
});
