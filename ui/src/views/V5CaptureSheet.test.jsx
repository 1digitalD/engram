/* eslint-disable no-unused-vars */
import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { CaptureProvider } from '../context/CaptureContext';
import V5CaptureSheet, { CAPTURE_PLACEHOLDER } from './V5CaptureSheet';

vi.mock('../api/v4Client', () => ({
  v4API: {
    entities: {
      get: vi.fn(),
      list: vi.fn(),
    },
    relationships: {
      create: vi.fn(),
    },
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

import { v4API } from '../api/v4Client';

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
    expect(screen.getByLabelText('Capture text')).toHaveAttribute('placeholder', CAPTURE_PLACEHOLDER);
    expect(screen.queryByText(/AI will figure out what you mean/i)).not.toBeInTheDocument();
  });

  it('auto-attaches when opened from a thread route', async () => {
    renderSheet('/projects/p1');
    await waitFor(() => {
      expect(screen.getByLabelText('Capture attachment')).toHaveValue('p1');
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

    fireEvent.change(screen.getByLabelText('Capture text'), {
      target: { value: 'Ask Henry about rollout' },
    });
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

    fireEvent.change(screen.getByLabelText('Capture text'), {
      target: { value: 'Broken capture' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^Save$/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('pipeline broke');
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });

  it('passes thread_id when a project is attached', async () => {
    const captureFn = vi.fn(async () => ({
      source_note: { id: 'n1' },
      applied_changes: [],
      suggestions: [],
      warnings: [],
    }));

    renderSheet('/projects/p1', { captureFn });

    await waitFor(() => expect(screen.getByLabelText('Capture attachment')).toHaveValue('p1'));

    fireEvent.change(screen.getByLabelText('Capture text'), {
      target: { value: 'Status update' },
    });
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

    fireEvent.change(screen.getByLabelText('Capture text'), {
      target: { value: 'Retry me' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^Save$/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent('pipeline broke');
    expect(captureFn).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: /retry/i }));

    await waitFor(() => expect(captureFn).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(onSaved).toHaveBeenCalledWith(successResult);
  });
});
