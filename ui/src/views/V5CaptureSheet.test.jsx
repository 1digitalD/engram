/* eslint-disable no-unused-vars */
import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { CaptureProvider, useCapture } from '../context/CaptureContext';
import V5CaptureSheet, { CAPTURE_ATTACHMENT_HINT, CAPTURE_PLACEHOLDER, CaptureToast } from './V5CaptureSheet';

vi.mock('../api/v4Client', () => ({
  v4API: {
    entities: {
      get: vi.fn(),
      list: vi.fn(),
    },
    relationships: {
      create: vi.fn(),
    },
    mentions: vi.fn().mockResolvedValue({ results: {} }),
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

import { v4API } from '../api/v4Client';

// The capture textarea was replaced by the mention-enabled MarkdownEditor,
// a Tiptap contenteditable surface. fireEvent.change doesn't drive it, so
// tests type through it with userEvent instead.
async function typeCapture(text) {
  const field = screen.getByLabelText('Capture text');
  field.focus();
  const user = userEvent.setup();
  await user.type(field, text, { skipClick: true });
}

// A mention is normally inserted by picking an entity from the @/[[ popup,
// which the mention extension turns into a real markdown link node (see
// mentionExtension.js). To exercise the round trip without driving that
// popup, seed the sheet's initial content (as CaptureContext.openCapture
// does for voice/attachment flows) with mention markdown already in it.
function OpenWithContent({ content }) {
  const { openCapture } = useCapture();
  return (
    <button type="button" onClick={() => openCapture(content)}>
      Open with content
    </button>
  );
}

const SAMPLE_OPTIONS = [
  { id: '', label: 'None', type: '' },
  { id: 'p1', label: 'HITL Pilot', type: 'project' },
];

function renderSheet(initialPath = '/', props = {}) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <CaptureProvider>
        <Routes>
          <Route path="*" element={<V5CaptureSheet open attachmentOptions={SAMPLE_OPTIONS} {...props} />} />
        </Routes>
      </CaptureProvider>
    </MemoryRouter>,
  );
}

describe('V5CaptureSheet', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.entities.get.mockResolvedValue({ id: 'p1', type: 'project', title: 'HITL Pilot' });
    v4API.entities.list.mockResolvedValue({ data: [] });
    v4API.relationships.create.mockResolvedValue({});
  });

  it('uses honest placeholder copy', () => {
    renderSheet();
    const field = screen.getByLabelText('Capture text');
    expect(field.querySelector('[data-placeholder]')).toHaveAttribute('data-placeholder', CAPTURE_PLACEHOLDER);
    expect(screen.queryByText(/AI will figure out what you mean/i)).not.toBeInTheDocument();
  });

  it('renders the mention-enabled markdown editor for capture text', () => {
    renderSheet();
    expect(screen.getByTestId('markdown-editor')).toBeInTheDocument();
  });

  it('falls back to /notes for toast view links', () => {
    render(
      <MemoryRouter>
        <CaptureToast toast={{ applied: 1, suggested: 0 }} />
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: 'View' })).toHaveAttribute('href', '/notes');
  });

  it('offers a review action when suggestions were returned', () => {
    const onOpenReview = vi.fn();
    render(
      <MemoryRouter>
        <CaptureToast toast={{ applied: 1, suggested: 2 }} onOpenReview={onOpenReview} />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Review' }));
    expect(onOpenReview).toHaveBeenCalledTimes(1);
  });

  it('auto-attaches when opened from a thread route', async () => {
    renderSheet('/projects/p1');
    await waitFor(() => {
      expect(screen.getByLabelText('Capture thread context')).toHaveValue('p1');
    });
  });

  it('streams capture events and closes on done', async () => {
    const onClose = vi.fn();
    const onSaved = vi.fn();
    const captureFn = vi.fn(async (_body, { onEvent }) => {
      onEvent({ type: 'extracting', data: {} });
      onEvent({ type: 'linking', data: { links_created: 1 } });
      onEvent({ type: 'done', data: {
        source_note: { id: 'n1', title: 'Captured' },
        applied_changes: [{ type: 'summary_updated' }],
        suggestions: [{ id: 's1' }, { id: 's2' }],
        warnings: [],
      } });
      return {
        source_note: { id: 'n1', title: 'Captured' },
        applied_changes: [{ type: 'summary_updated' }],
        suggestions: [{ id: 's1' }, { id: 's2' }],
        warnings: [],
      };
    });

    renderSheet('/', { onClose, onSaved, captureFn });

    await typeCapture('Ask Henry about rollout');
    fireEvent.click(screen.getByRole('button', { name: /^Save$/i }));

    await waitFor(() => expect(captureFn).toHaveBeenCalledWith(
      expect.objectContaining({
        content: 'Ask Henry about rollout',
        source: 'ui',
        mode: 'auto',
      }),
      expect.any(Object),
    ));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(onSaved).toHaveBeenCalled();
  });

  it('keeps the sheet open and shows retry on stream error', async () => {
    const onClose = vi.fn();
    const captureFn = vi.fn(async (_body, { onEvent }) => {
      onEvent({ type: 'extracting', data: {} });
      onEvent({ type: 'error', data: { message: 'pipeline broke' } });
      throw new Error('pipeline broke');
    });

    renderSheet('/', { onClose, captureFn });

    await typeCapture('Broken capture');
    fireEvent.click(screen.getByRole('button', { name: /^Save$/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('pipeline broke');
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });

  it('shows honest thread-context copy when a thread is attached', async () => {
    renderSheet('/projects/p1');
    await waitFor(() => expect(screen.getByLabelText('Capture thread context')).toHaveValue('p1'));
    expect(screen.getByText(CAPTURE_ATTACHMENT_HINT)).toBeInTheDocument();
    expect(screen.queryByText(/activity update/i, { selector: 'option' })).not.toBeInTheDocument();
  });

  it('passes thread_id when a project is attached', async () => {
    const captureFn = vi.fn(async () => ({
      source_note: { id: 'n1' },
      applied_changes: [],
      suggestions: [],
      warnings: [],
    }));

    renderSheet('/projects/p1', { captureFn });

    await waitFor(() => expect(screen.getByLabelText('Capture thread context')).toHaveValue('p1'));

    await typeCapture('Status update');
    fireEvent.click(screen.getByRole('button', { name: /^Save$/i }));

    await waitFor(() => expect(captureFn).toHaveBeenCalledWith(
      expect.objectContaining({ thread_id: 'p1' }),
      expect.any(Object),
    ));
  });

  it('retries capture and succeeds after failure', async () => {
    const onClose = vi.fn();
    const onSaved = vi.fn();
    const successResult = {
      source_note: { id: 'n1', title: 'Captured on retry' },
      applied_changes: [{ type: 'summary_updated' }],
      suggestions: [],
      warnings: [],
    };

    const captureFn = vi.fn()
      .mockImplementationOnce(async (_body, { onEvent }) => {
        onEvent({ type: 'extracting', data: {} });
        onEvent({ type: 'error', data: { message: 'pipeline broke' } });
        throw new Error('pipeline broke');
      })
      .mockImplementationOnce(async (_body, { onEvent }) => {
        onEvent({ type: 'extracting', data: {} });
        onEvent({ type: 'done', data: successResult });
        return successResult;
      });

    renderSheet('/', { onClose, onSaved, captureFn });

    await typeCapture('Retry me');
    fireEvent.click(screen.getByRole('button', { name: /^Save$/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('pipeline broke');
    expect(captureFn).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: /retry/i }));

    await waitFor(() => expect(captureFn).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(onSaved).toHaveBeenCalledWith(successResult);
  });

  it('passes mention markdown links through to the API unchanged', async () => {
    const mentionMarkdown = 'Ask [Henry](/people/henry-1) about rollout';
    const captureFn = vi.fn(async () => ({
      source_note: { id: 'n1' },
      applied_changes: [],
      suggestions: [],
      warnings: [],
    }));

    render(
      <MemoryRouter initialEntries={['/']}>
        <CaptureProvider>
          <OpenWithContent content={mentionMarkdown} />
          <Routes>
            <Route
              path="*"
              element={<V5CaptureSheet attachmentOptions={SAMPLE_OPTIONS} captureFn={captureFn} />}
            />
          </Routes>
        </CaptureProvider>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open with content' }));

    const field = await screen.findByLabelText('Capture text');
    await waitFor(() => {
      expect(field.querySelector('a[href="/people/henry-1"]')).toHaveTextContent('Henry');
    });

    fireEvent.click(screen.getByRole('button', { name: /^Save$/i }));

    await waitFor(() => expect(captureFn).toHaveBeenCalledWith(
      expect.objectContaining({ content: mentionMarkdown }),
      expect.any(Object),
    ));
  });
});
