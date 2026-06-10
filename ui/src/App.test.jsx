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
    summary: vi.fn(),
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
vi.mock('./views/V4Suggestions', () => ({ default: () => <main>Review view</main> }));
vi.mock('./views/V4AgentActivity', () => ({ default: () => <main>Agent log view</main> }));
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
    v4API.summary.mockResolvedValue({ inbox_count: 1, today_count: 0, suggestions_count: 1 });
    v4API.suggestions.list.mockResolvedValue({ meta: { total: 2 }, data: [] });

    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Home view')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Home/i })).toHaveAttribute('href', '/');
    expect(screen.getByRole('link', { name: /Inbox/i })).toHaveAttribute('href', '/inbox');
    expect(screen.getByRole('link', { name: /Agent log/i })).toHaveAttribute('href', '/agent-activity');
  });

  it('renders sidebar counts from the summary endpoint', async () => {
    v4API.inbox.mockResolvedValue({ needs_review: [{ id: 'n1' }, { id: 'n2' }] });
    v4API.entities.list.mockResolvedValue({ meta: { total: 4 }, data: [] });
    v4API.today.mockResolvedValue({});
    v4API.suggestions.list.mockResolvedValue({ meta: { total: 2 }, data: [] });
    v4API.summary.mockResolvedValue({ inbox_count: 2, today_count: 7, suggestions_count: 2 });

    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    );

    await waitFor(() => expect(v4API.summary).toHaveBeenCalled());
    expect(screen.getByRole('link', { name: /Today/i })).toHaveTextContent('7');
    expect(screen.getByRole('link', { name: /Inbox/i })).toHaveTextContent('2');
    expect(screen.getByRole('link', { name: /Review/i })).toHaveTextContent('2');
  });

  it('supports quick note capture from the shell', async () => {
    v4API.inbox.mockResolvedValue({ needs_review: [] });
    v4API.entities.list.mockResolvedValue({ meta: { total: 0 }, data: [] });
    v4API.today.mockResolvedValue({});
    v4API.suggestions.list.mockResolvedValue({ meta: { total: 0 }, data: [] });
    v4API.summary.mockResolvedValue({ inbox_count: 0, today_count: 0, suggestions_count: 0 });
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
    v4API.summary.mockResolvedValue({ inbox_count: 0, today_count: 0, suggestions_count: 0 });

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
