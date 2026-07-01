import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { v4API } from '../api/v4Client';
import { CaptureProvider } from '../context/CaptureContext';
import V5Recall from './V5Recall';

vi.mock('../api/v4Client', () => ({
  v4API: {
    search: vi.fn(),
  },
}));

describe('V5Recall', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.search.mockResolvedValue({ data: [] });
  });

  it('does not render when closed', () => {
    render(
      <MemoryRouter>
        <CaptureProvider>
          <V5Recall open={false} onClose={vi.fn()} />
        </CaptureProvider>
      </MemoryRouter>,
    );

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders the search palette when open', () => {
    render(
      <MemoryRouter>
        <CaptureProvider>
          <V5Recall open onClose={vi.fn()} />
        </CaptureProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole('dialog', { name: 'Recall search' })).toBeInTheDocument();
    expect(screen.getByLabelText('Search terms')).toBeInTheDocument();
  });

  it('searches and navigates to a result on enter', async () => {
    const onClose = vi.fn();
    v4API.search.mockResolvedValue({
      data: [
        { id: 'p1', type: 'project', title: 'Agent Memory', status: 'active' },
      ],
    });

    render(
      <MemoryRouter>
        <CaptureProvider>
          <V5Recall open onClose={onClose} />
        </CaptureProvider>
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText('Search terms'), { target: { value: 'agent' } });

    await waitFor(() => expect(v4API.search).toHaveBeenCalledWith({ q: 'agent', limit: 24 }));
    expect(await screen.findByRole('option', { name: /Agent Memory/i })).toBeInTheDocument();

    fireEvent.keyDown(screen.getByLabelText('Search terms'), { key: 'Enter' });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('closes on escape', async () => {
    const onClose = vi.fn();
    render(
      <MemoryRouter>
        <CaptureProvider>
          <V5Recall open onClose={onClose} />
        </CaptureProvider>
      </MemoryRouter>,
    );

    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('ignores stale responses from older queries', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const onClose = vi.fn();
    let resolveOld;
    let resolveNew;

    v4API.search.mockImplementation(({ q }) => {
      if (q === 'old') {
        return new Promise((resolve) => {
          resolveOld = () => resolve({ data: [{ id: 'old1', type: 'note', title: 'Old result' }] });
        });
      }
      if (q === 'new') {
        return new Promise((resolve) => {
          resolveNew = () => resolve({ data: [{ id: 'new1', type: 'note', title: 'New result' }] });
        });
      }
      return Promise.resolve({ data: [] });
    });

    render(
      <MemoryRouter>
        <CaptureProvider>
          <V5Recall open onClose={onClose} />
        </CaptureProvider>
      </MemoryRouter>,
    );

    const input = screen.getByLabelText('Search terms');

    fireEvent.change(input, { target: { value: 'old' } });
    await vi.advanceTimersByTimeAsync(200);
    expect(v4API.search).toHaveBeenCalledWith({ q: 'old', limit: 24 });

    fireEvent.change(input, { target: { value: 'new' } });
    await vi.advanceTimersByTimeAsync(200);
    expect(v4API.search).toHaveBeenLastCalledWith({ q: 'new', limit: 24 });

    // Resolve the newer query first.
    resolveNew();
    await screen.findByRole('option', { name: /New result/i });

    // Then resolve the older, stale query.
    resolveOld();
    await waitFor(() => expect(screen.queryByRole('option', { name: /Old result/i })).not.toBeInTheDocument());
    expect(screen.getByRole('option', { name: /New result/i })).toBeInTheDocument();

    vi.useRealTimers();
  });
});
