import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import UniversalSearch, { ENTITY_TYPES, getEntityTitle, getEntityRoute } from './UniversalSearch';
import useStore from '../../stores/useStore';

vi.mock('../../stores/useStore');

const mockNotes = [
  { id: 'n1', raw_text: '# Meeting Notes\nDiscussed project roadmap', bucket: 'NOTES', type: 'note' },
  { id: 'n2', raw_text: '# Ideas\nRandom thoughts about the product', bucket: 'NOTES', type: 'note' },
];

const mockTasks = [
  { id: 't1', title: 'Fix login bug', status: 'pending' },
  { id: 't2', title: 'Write documentation', status: 'in_progress' },
];

const mockProjects = [
  { id: 'p1', name: 'Project Alpha' },
  { id: 'p2', name: 'Project Beta' },
];

const mockAreas = [
  { id: 'a1', name: 'Engineering' },
];

const mockPeople = [
  { id: 'pe1', name: 'Alice Johnson' },
];

const mockResources = [
  { id: 'r1', name: 'API Reference', url: 'https://example.com/api' },
];

const mockStore = {
  notes: mockNotes,
  tasks: mockTasks,
  projects: mockProjects,
  areas: mockAreas,
  people: mockPeople,
  resources: mockResources,
};

const renderSearch = (props = {}) => {
  vi.mocked(useStore).mockReturnValue({ ...mockStore });
  return render(
    <MemoryRouter>
      <UniversalSearch onClose={vi.fn()} {...props} />
    </MemoryRouter>
  );
};

describe('UniversalSearch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the search input', () => {
    renderSearch();
    expect(screen.getByTestId('universal-search-input')).toBeInTheDocument();
  });

  it('focuses the input on mount', () => {
    renderSearch();
    expect(screen.getByTestId('universal-search-input')).toHaveFocus();
  });

  it('shows placeholder text', () => {
    renderSearch();
    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
  });

  it('does not show results when query is empty', () => {
    renderSearch();
    expect(screen.queryByTestId('search-results')).not.toBeInTheDocument();
  });

  it('shows results grouped by type when query matches', async () => {
    const user = userEvent.setup();
    renderSearch();

    await user.type(screen.getByTestId('universal-search-input'), 'project');

    expect(screen.getByTestId('search-results')).toBeInTheDocument();
    expect(screen.getByText('Projects')).toBeInTheDocument();
  });

  it('shows results for notes when query matches', async () => {
    const user = userEvent.setup();
    renderSearch();

    await user.type(screen.getByTestId('universal-search-input'), 'meeting');

    expect(screen.getByText('Notes')).toBeInTheDocument();
    expect(screen.getByText('Meeting Notes')).toBeInTheDocument();
  });

  it('shows results for tasks when query matches', async () => {
    const user = userEvent.setup();
    renderSearch();

    await user.type(screen.getByTestId('universal-search-input'), 'login');

    expect(screen.getByText('Tasks')).toBeInTheDocument();
    expect(screen.getByText('Fix login bug')).toBeInTheDocument();
  });

  it('shows results for people when query matches', async () => {
    const user = userEvent.setup();
    renderSearch();

    await user.type(screen.getByTestId('universal-search-input'), 'alice');

    expect(screen.getByText('People')).toBeInTheDocument();
    expect(screen.getByText('Alice Johnson')).toBeInTheDocument();
  });

  it('shows results for areas when query matches', async () => {
    const user = userEvent.setup();
    renderSearch();

    await user.type(screen.getByTestId('universal-search-input'), 'engineering');

    expect(screen.getByText('Areas')).toBeInTheDocument();
    expect(screen.getByText('Engineering')).toBeInTheDocument();
  });

  it('shows results for resources when query matches', async () => {
    const user = userEvent.setup();
    renderSearch();

    await user.type(screen.getByTestId('universal-search-input'), 'api');

    expect(screen.getByText('Resources')).toBeInTheDocument();
    expect(screen.getByText('API Reference')).toBeInTheDocument();
  });

  it('shows "No results" when query has no matches', async () => {
    const user = userEvent.setup();
    renderSearch();

    await user.type(screen.getByTestId('universal-search-input'), 'xyznonexistent');

    expect(screen.getByText(/no results/i)).toBeInTheDocument();
  });

  it('supports keyboard navigation with arrow down', async () => {
    const user = userEvent.setup();
    renderSearch();

    await user.type(screen.getByTestId('universal-search-input'), 'project');

    await user.keyboard('{ArrowDown}');

    const results = screen.getAllByRole('button', { name: /project alpha|project beta/i });
    expect(results[0].className).not.toMatch(/resultActive/);
    expect(results[1].className).toMatch(/resultActive/);
  });

  it('supports keyboard navigation with arrow up', async () => {
    const user = userEvent.setup();
    renderSearch();

    await user.type(screen.getByTestId('universal-search-input'), 'project');

    await user.keyboard('{ArrowDown}');
    await user.keyboard('{ArrowDown}');
    await user.keyboard('{ArrowUp}');

    const results = screen.getAllByRole('button', { name: /project alpha|project beta/i });
    expect(results[0].className).toMatch(/resultActive/);
  });

  it('closes on Escape key', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    vi.mocked(useStore).mockReturnValue({ ...mockStore });
    render(
      <MemoryRouter>
        <UniversalSearch onClose={onClose} />
      </MemoryRouter>
    );

    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose when clicking backdrop', async () => {
    const onClose = vi.fn();
    vi.mocked(useStore).mockReturnValue({ ...mockStore });
    const { container } = render(
      <MemoryRouter>
        <UniversalSearch onClose={onClose} />
      </MemoryRouter>
    );

    fireEvent.click(container.firstChild);
    expect(onClose).toHaveBeenCalled();
  });

  it('does not call onClose when clicking inside palette', async () => {
    const onClose = vi.fn();
    vi.mocked(useStore).mockReturnValue({ ...mockStore });
    const { container } = render(
      <MemoryRouter>
        <UniversalSearch onClose={onClose} />
      </MemoryRouter>
    );

    const palette = container.querySelector('[data-testid="universal-search-palette"]');
    fireEvent.click(palette);
    expect(onClose).not.toHaveBeenCalled();
  });

  it('highlights result on mouse enter', async () => {
    const user = userEvent.setup();
    renderSearch();

    await user.type(screen.getByTestId('universal-search-input'), 'project');

    const firstResult = screen.getByText('Project Alpha').closest('button');
    await user.hover(firstResult);

    expect(firstResult.className).toMatch(/resultActive/);
  });
});

describe('getEntityTitle', () => {
  it('returns raw_text first line for notes', () => {
    const note = { raw_text: '# Meeting Notes\nMore content' };
    expect(getEntityTitle(note, 'note')).toBe('Meeting Notes');
  });

  it('returns name for projects', () => {
    expect(getEntityTitle({ name: 'Project Alpha' }, 'project')).toBe('Project Alpha');
  });

  it('returns name for areas', () => {
    expect(getEntityTitle({ name: 'Engineering' }, 'area')).toBe('Engineering');
  });

  it('returns name for people', () => {
    expect(getEntityTitle({ name: 'Alice' }, 'person')).toBe('Alice');
  });

  it('returns title for tasks', () => {
    expect(getEntityTitle({ title: 'Fix bug' }, 'task')).toBe('Fix bug');
  });

  it('returns name for resources', () => {
    expect(getEntityTitle({ name: 'API Docs' }, 'resource')).toBe('API Docs');
  });

  it('returns Untitled for empty entities', () => {
    expect(getEntityTitle({}, 'note')).toBe('Untitled');
  });
});

describe('getEntityRoute', () => {
  it('returns note route', () => {
    expect(getEntityRoute('n1', 'note')).toBe('/notes/n1');
  });

  it('returns project route', () => {
    expect(getEntityRoute('p1', 'project')).toBe('/projects/p1');
  });

  it('returns area route', () => {
    expect(getEntityRoute('a1', 'area')).toBe('/areas/a1');
  });

  it('returns people list route', () => {
    expect(getEntityRoute('pe1', 'person')).toBe('/people');
  });

  it('returns tasks list route', () => {
    expect(getEntityRoute('t1', 'task')).toBe('/tasks');
  });

  it('returns resources list route', () => {
    expect(getEntityRoute('r1', 'resource')).toBe('/resources');
  });
});

describe('ENTITY_TYPES', () => {
  it('contains all six entity types', () => {
    expect(ENTITY_TYPES).toContain('note');
    expect(ENTITY_TYPES).toContain('task');
    expect(ENTITY_TYPES).toContain('project');
    expect(ENTITY_TYPES).toContain('area');
    expect(ENTITY_TYPES).toContain('resource');
    expect(ENTITY_TYPES).toContain('person');
  });
});
