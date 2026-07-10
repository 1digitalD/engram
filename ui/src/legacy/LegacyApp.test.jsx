import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import LegacyApp from './LegacyApp';
import { v4API } from '../api/v4Client';

vi.mock('../api/v4Client', () => ({
  v4API: {
    capture: vi.fn(),
    entities: {
      list: vi.fn(),
      create: vi.fn(),
      get: vi.fn(),
    },
    today: vi.fn(),
    summary: vi.fn(),
    search: vi.fn(),
    threads: vi.fn(),
    metrics: {
      trust: vi.fn().mockResolvedValue({ correction_rate: null }),
    },
    suggestions: {
      list: vi.fn().mockResolvedValue({ data: [], meta: { total: 0 } }),
      accept: vi.fn(),
      dismiss: vi.fn(),
    },
  },
}));

vi.mock('../views/V5Now', () => ({ default: () => <main>Now view</main> }));
vi.mock('../views/V5Threads', () => ({ default: () => <main>Threads view</main> }));
vi.mock('../views/V5EntityList', () => ({ default: ({ type }) => <main>{type} list</main> }));
vi.mock('../views/V5ThreadDetail', () => ({ default: () => <main>Detail view</main> }));

function renderLegacy(initialEntry) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/legacy/*" element={<LegacyApp />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('Legacy V5 App shell', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.entities.list.mockResolvedValue({ data: [] });
    v4API.entities.get.mockResolvedValue({ id: 'p1', title: 'Project' });
    v4API.today.mockResolvedValue({});
    v4API.summary.mockResolvedValue({ today_count: 0, threads_count: 0 });
    v4API.threads.mockResolvedValue({ threads: [] });
    v4API.search.mockResolvedValue({ data: [] });
    v4API.metrics.trust.mockResolvedValue({ correction_rate: null });
  });

  it('redirects /legacy to /legacy/now and renders the Now lens', async () => {
    renderLegacy('/legacy');

    expect(await screen.findByText('Now view')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Now/i })).toHaveAttribute('href', '/legacy/now');
    expect(screen.getByRole('link', { name: /Threads/i })).toHaveAttribute('href', '/legacy/threads');
  });

  it('renders lens counts from the summary endpoint', async () => {
    v4API.summary.mockResolvedValue({ today_count: 3, threads_count: 7, suggestions_count: 4 });

    renderLegacy('/legacy/now');

    await waitFor(() => expect(v4API.summary).toHaveBeenCalled());
    expect(screen.getByRole('link', { name: /Now/i })).toHaveTextContent('3');
    expect(screen.getByRole('link', { name: /Threads/i })).toHaveTextContent('7');
    expect(screen.getByRole('button', { name: /Review 4 pending suggestions/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Open Recall/i)).not.toHaveTextContent(/\d/);
  });

  it('opens the review sheet from the top bar badge', async () => {
    v4API.summary.mockResolvedValue({ today_count: 0, threads_count: 0, suggestions_count: 2 });

    renderLegacy('/legacy/now');

    fireEvent.click(await screen.findByRole('button', { name: /Review 2 pending suggestions/i }));
    expect(await screen.findByRole('dialog', { name: 'Review suggestions' })).toBeInTheDocument();
    await waitFor(() => expect(v4API.suggestions.list).toHaveBeenCalledWith({ status: 'pending' }));
  });

  it('exposes a global capture FAB', async () => {
    renderLegacy('/legacy/now');

    expect(await screen.findByRole('button', { name: /open capture/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /open capture/i }));
    expect(await screen.findByRole('dialog', { name: 'Capture' })).toBeInTheDocument();
  });

  it('wires the Recall lens to the legacy recall route', async () => {
    renderLegacy('/legacy/now');

    expect(await screen.findByLabelText(/Open Recall/i)).toHaveAttribute('href', '/legacy/recall');
  });

  it('opens the Recall sheet with Cmd+K', async () => {
    renderLegacy('/legacy/now');

    await screen.findByText('Now view');
    fireEvent.keyDown(window, { key: 'k', metaKey: true });
    expect(await screen.findByRole('dialog', { name: 'Recall search' })).toBeInTheDocument();
  });

  it('renders entity list routes', async () => {
    renderLegacy('/legacy/projects');

    expect(await screen.findByText('project list')).toBeInTheDocument();
  });

  describe('theme switcher', () => {
    beforeEach(() => {
      localStorage.removeItem('engram-theme');
    });

    afterEach(() => {
      delete document.documentElement.dataset.theme;
      localStorage.removeItem('engram-theme');
    });

    it('switches theme from the top bar and persists only on explicit choice', async () => {
      renderLegacy('/legacy/now');

      expect(await screen.findByText('Now view')).toBeInTheDocument();
      expect(screen.getByRole('group', { name: 'Theme' })).toBeInTheDocument();
      expect(document.documentElement.dataset.theme).toBe('light');
      expect(localStorage.getItem('engram-theme')).toBeNull();

      fireEvent.click(screen.getByRole('button', { name: /Glass theme/i }));
      expect(document.documentElement.dataset.theme).toBe('glass');
      expect(localStorage.getItem('engram-theme')).toBe('glass');
      expect(screen.getByRole('button', { name: /Glass theme/i })).toHaveAttribute('aria-pressed', 'true');
    });

    it('restores the saved theme on load', async () => {
      localStorage.setItem('engram-theme', 'dark');

      renderLegacy('/legacy/now');

      expect(await screen.findByText('Now view')).toBeInTheDocument();
      expect(document.documentElement.dataset.theme).toBe('dark');
      expect(screen.getByRole('button', { name: /Dark theme/i })).toHaveAttribute('aria-pressed', 'true');
    });
  });
});
