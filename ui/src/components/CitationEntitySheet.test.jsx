import { useState } from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CitationEntitySheet from './CitationEntitySheet';

vi.mock('../api/v4Client', () => ({
  v4API: {
    entities: {
      detail: vi.fn(),
      events: vi.fn(),
      canonical: vi.fn(),
    },
  },
}));

vi.mock('../views/V5ThreadDetail', () => ({
  ThreadDetailContent: ({ detail }) => (
    <div data-testid="thread-detail-content">
      {detail?.entity?.title || 'no-entity'}
    </div>
  ),
}));

import { v4API } from '../api/v4Client';

describe('CitationEntitySheet', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.entities.detail.mockResolvedValue({
      entity: { id: 'note-1', type: 'note', title: 'Citation source' },
    });
    v4API.entities.events.mockResolvedValue({ data: [] });
    v4API.entities.canonical.mockResolvedValue({ canonical: 'Body text' });
  });

  it('renders nothing when closed', () => {
    render(<CitationEntitySheet entityId="note-1" open={false} onClose={vi.fn()} />);
    // When closed, Sheet returns null — query for content should not find it.
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders the citation content when open', async () => {
    render(<CitationEntitySheet entityId="note-1" open onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTestId('thread-detail-content')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /Back/i })).toBeInTheDocument();
  });

  it('closes when Back button is clicked', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<CitationEntitySheet entityId="note-1" open onClose={onClose} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Back/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /Back/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('closes when Escape is pressed', async () => {
    const onClose = vi.fn();
    render(<CitationEntitySheet entityId="note-1" open onClose={onClose} />);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    await userEvent.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  describe('B-016 focus restoration', () => {
    // Helper: render a trigger + controlled sheet. The trigger toggles the
    // sheet's open state via the parent's setOpen hook, mirroring how
    // production callers use CitationEntitySheet.
    function ControlledSheet({ onCloseSpy }) {
      const [open, setOpen] = useState(false);
      return (
        <div>
          <button
            type="button"
            data-testid="trigger-button"
            onClick={() => setOpen(true)}
          >
            Open citation
          </button>
          <CitationEntitySheet
            entityId="note-1"
            open={open}
            onClose={() => {
              onCloseSpy?.();
              setOpen(false);
            }}
          />
        </div>,
      );
    }

    it('restores focus to the trigger element after closing via Back', async () => {
      const user = userEvent.setup();
      render(<ControlledSheet />);

      await user.click(screen.getByTestId('trigger-button'));

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Click Back — the controlled parent flips open=false, the sheet
      // unmounts, and our useEffect cleanup restores focus to the trigger.
      await user.click(screen.getByRole('button', { name: /Back/i }));

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });

      expect(document.activeElement).toBe(screen.getByTestId('trigger-button'));
    });

    it('restores focus after closing via Escape', async () => {
      const user = userEvent.setup();
      render(<ControlledSheet />);

      await user.click(screen.getByTestId('trigger-button'));

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.keyboard('{Escape}');

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });

      expect(document.activeElement).toBe(screen.getByTestId('trigger-button'));
    });

    it('does not throw if trigger element is no longer in the DOM at close time', async () => {
      const user = userEvent.setup();

      const { rerender } = render(
        <div>
          <button type="button" data-testid="trigger-button">
            Open citation
          </button>
          <CitationEntitySheet entityId="note-1" open onClose={vi.fn()} />
        </div>,
      );

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Remove the trigger from DOM and close.
      rerender(
        <div>
          <CitationEntitySheet entityId="note-1" open={false} onClose={vi.fn()} />
        </div>,
      );

      // No exception means the focus code handled the missing element.
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('shows loading state initially', () => {
    // Defer the resolution to keep loading state visible
    v4API.entities.detail.mockReturnValue(new Promise(() => {}));

    render(<CitationEntitySheet entityId="note-1" open onClose={vi.fn()} />);
    expect(screen.getByText(/Loading citation/i)).toBeInTheDocument();
  });

  it('shows error state when fetch fails', async () => {
    v4API.entities.detail.mockRejectedValue(new Error('Network down'));

    render(<CitationEntitySheet entityId="note-1" open onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('Network down')).toBeInTheDocument();
    });
  });
});