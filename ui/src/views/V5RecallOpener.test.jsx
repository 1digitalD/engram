import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import {
  MemoryRouter, Routes, Route, useLocation,
} from 'react-router-dom';
import V5RecallOpener from './V5RecallOpener';

vi.mock('../context/RecallContext', () => ({
  useRecall: vi.fn(),
}));

function LocationDisplay() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}</span>;
}

function renderOpener(initialEntry) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/recall" element={<V5RecallOpener />} />
        <Route path="/now" element={<div>Now lens</div>} />
        <Route path="/projects" element={<div>Projects lens</div>} />
        <Route path="*" element={<div>Not found</div>} />
      </Routes>
      <LocationDisplay />
    </MemoryRouter>,
  );
}

describe('V5RecallOpener', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('opens recall and redirects to /now on direct load', async () => {
    const openRecall = vi.fn();
    const { useRecall } = await import('../context/RecallContext');
    useRecall.mockReturnValue({ openRecall });

    renderOpener('/recall');

    await waitFor(() => expect(openRecall).toHaveBeenCalled());
    expect(screen.getByTestId('location')).toHaveTextContent('/now');
  });

  it('redirects to the background location when provided', async () => {
    const openRecall = vi.fn();
    const { useRecall } = await import('../context/RecallContext');
    useRecall.mockReturnValue({ openRecall });

    renderOpener({
      pathname: '/recall',
      state: { backgroundLocation: { pathname: '/projects' } },
    });

    await waitFor(() => expect(openRecall).toHaveBeenCalled());
    expect(screen.getByTestId('location')).toHaveTextContent('/projects');
  });

  it('falls back to /now when background location state is missing', async () => {
    const openRecall = vi.fn();
    const { useRecall } = await import('../context/RecallContext');
    useRecall.mockReturnValue({ openRecall });

    renderOpener({ pathname: '/recall' });

    await waitFor(() => expect(openRecall).toHaveBeenCalled());
    expect(screen.getByTestId('location')).toHaveTextContent('/now');
  });
});
