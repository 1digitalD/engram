import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import App from './App';
import { v4API } from './api/v4Client';

vi.mock('./api/v4Client', () => ({
  v4API: {
    capture: vi.fn(),
    inbox: vi.fn(),
    entities: {
      list: vi.fn(),
      create: vi.fn(),
    },
    today: vi.fn(),
    suggestions: {
      list: vi.fn(),
    },
  },
}));

vi.mock('./components/MarkdownEditor', () => ({
  default: ({ value, onChange, placeholder }) => (
    <textarea
      aria-label="Quick note content"
      placeholder={placeholder}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  ),
}));

vi.mock('./views/V4Home', () => ({ default: () => <main>Home view</main> }));
vi.mock('./views/V4Inbox', () => ({ default: () => <main>Inbox view</main> }));
vi.mock('./views/V4Today', () => ({ default: () => <main>Today view</main> }));
vi.mock('./views/V4Search', () => ({ default: () => <main>Search view</main> }));
vi.mock('./views/V4Suggestions', () => ({ default: () => <main>Suggestions view</main> }));
vi.mock('./views/V4EntityList', () => ({ default: ({ type }) => <main>{type} list</main> }));
vi.mock('./views/V4EntityDetail', () => ({ default: () => <main>Detail view</main> }));

describe('App shell', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders Home at the root route while keeping Inbox available separately', async () => {
    v4API.inbox.mockResolvedValue({ needs_review: [{ id: 'n1' }] });
    v4API.entities.list.mockResolvedValue({ meta: { total: 4 }, data: [] });
    v4API.today.mockResolvedValue({});
    v4API.suggestions.list.mockResolvedValue({ meta: { total: 2 }, data: [] });

    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Home view')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Home/i })).toHaveAttribute('href', '/');
    expect(screen.getByRole('link', { name: /Inbox/i })).toHaveAttribute('href', '/inbox');
  });

  it('uses the same actionable today buckets as the Today screen', async () => {
    v4API.inbox.mockResolvedValue({ needs_review: [{ id: 'n1' }, { id: 'n2' }] });
    v4API.entities.list.mockResolvedValue({ meta: { total: 4 }, data: [] });
    v4API.today.mockResolvedValue({
      overdue: [{ id: '1' }],
      due_today: [{ id: '2' }],
      overdue_follow_ups: [{ id: '1' }, { id: '3' }],
      follow_ups: [{ id: '4' }],
      blocked_tasks: [{ id: '5' }],
      waiting_tasks: [{ id: '5' }, { id: '6' }],
      recent_notes: [{ id: 'n3', ai: { intent: 'blocker' } }],
    });
    v4API.suggestions.list.mockResolvedValue({ meta: { total: 2 }, data: [] });

    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() => expect(v4API.today).toHaveBeenCalled());
    expect(screen.getByRole('link', { name: /Today/i })).toHaveTextContent('7');
    expect(screen.getByRole('link', { name: /Inbox/i })).toHaveTextContent('2');
    expect(screen.getByRole('link', { name: /Suggestions/i })).toHaveTextContent('2');
  });

  it('supports quick note capture from the shell', async () => {
    v4API.inbox.mockResolvedValue({ needs_review: [] });
    v4API.entities.list.mockResolvedValue({ meta: { total: 0 }, data: [] });
    v4API.today.mockResolvedValue({});
    v4API.suggestions.list.mockResolvedValue({ meta: { total: 0 }, data: [] });
    v4API.capture.mockResolvedValue({ source_note: { id: 'n1' } });

    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: /note/i }));
    fireEvent.change(screen.getByLabelText('Quick note content'), {
      target: { value: 'Remember this from anywhere' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save note/i }));

    await waitFor(() => expect(v4API.capture).toHaveBeenCalledWith({
      content: 'Remember this from anywhere',
      source: 'ui',
      mode: 'auto',
    }));
    expect(await screen.findByText('Saved note')).toBeInTheDocument();
  });

  it('does not render the shell quick-action bar on entity list routes', async () => {
    v4API.inbox.mockResolvedValue({ needs_review: [] });
    v4API.entities.list.mockResolvedValue({ meta: { total: 0 }, data: [] });
    v4API.today.mockResolvedValue({});
    v4API.suggestions.list.mockResolvedValue({ meta: { total: 0 }, data: [] });

    render(
      <MemoryRouter initialEntries={['/projects']}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText('project list')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Save note/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /New task/i })).not.toBeInTheDocument();
  });
});
