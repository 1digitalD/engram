import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import NoteDetailView from './NoteDetailView';
import useStore from '../stores/useStore';
import { linksAPI, proposalsAPI } from '../api/engram';

vi.mock('../stores/useStore');
vi.mock('../api/engram', () => ({
  linksAPI: { forNote: vi.fn(), create: vi.fn() },
  proposalsAPI: { list: vi.fn() },
}));

const baseStore = {
  projects: [],
  areas: [],
  people: [],
  tasks: [],
  resources: [],
  updateNote: vi.fn(),
  deleteNote: vi.fn(),
  createTask: vi.fn(),
  updateTask: vi.fn(),
  addToast: vi.fn(),
};

function renderNoteDetail(initialPath, notes) {
  vi.mocked(useStore).mockReturnValue({
    ...baseStore,
    notes,
  });
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/notes/:id" element={<NoteDetailView />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('NoteDetailView MOC note type', () => {
  beforeEach(() => {
    vi.mocked(proposalsAPI.list).mockResolvedValue({ data: [] });
  });

  it('shows MOC badge in meta bar when note_type is MOC', async () => {
    vi.mocked(linksAPI.forNote).mockResolvedValue({ outgoing: [], incoming: [] });
    const moc = {
      id: 'moc-badge-1',
      raw_text: '# Badge MOC\n',
      note_type: 'MOC',
      bucket: 'AREAS',
      created_at: '2026-05-01T12:00:00Z',
      modified_at: '2026-05-01T12:00:00Z',
      tag_names: [],
    };
    renderNoteDetail('/notes/moc-badge-1', [moc]);

    await waitFor(() => {
      expect(screen.getByTestId('moc-badge')).toHaveTextContent('MOC');
    });
  });

  it('renders MOC header when note_type is MOC', async () => {
    vi.mocked(linksAPI.forNote).mockResolvedValue({ outgoing: [], incoming: [] });
    const moc = {
      id: 'moc-1',
      raw_text: '# Product MOC\n\nIndex body.',
      note_type: 'MOC',
      bucket: 'AREAS',
      created_at: '2026-05-01T12:00:00Z',
      modified_at: '2026-05-01T12:00:00Z',
      tag_names: [],
    };
    renderNoteDetail('/notes/moc-1', [moc]);

    expect(await screen.findByTestId('moc-header')).toBeInTheDocument();
    expect(screen.getByText('Map of contents')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: 'Product MOC' })).toBeInTheDocument();
  });

  it('renders auto-generated TOC from outgoing links', async () => {
    vi.mocked(linksAPI.forNote).mockResolvedValue({
      outgoing: [
        { id: 'l1', src_id: 'moc-1', dst_id: 'child-a', link_type: 'related', weight: 1 },
      ],
      incoming: [],
    });
    const moc = {
      id: 'moc-1',
      raw_text: '# Topic map',
      note_type: 'MOC',
      bucket: 'AREAS',
      created_at: '2026-05-01T12:00:00Z',
      modified_at: '2026-05-01T12:00:00Z',
      tag_names: [],
    };
    const child = {
      id: 'child-a',
      raw_text: '# First linked note\n\nBody.',
      note_type: 'NOTE',
      bucket: 'INBOX',
      created_at: '2026-05-02T12:00:00Z',
      modified_at: '2026-05-02T12:00:00Z',
      tag_names: [],
    };
    renderNoteDetail('/notes/moc-1', [moc, child]);

    const toc = await screen.findByTestId('moc-toc');
    expect(toc).toBeInTheDocument();
    await waitFor(() => {
      const link = within(toc).getByRole('link', { name: 'First linked note' });
      expect(link).toHaveAttribute('href', '/notes/child-a');
    });
  });

  it('does not render MOC chrome for standard notes', async () => {
    vi.mocked(linksAPI.forNote).mockResolvedValue({ outgoing: [], incoming: [] });
    const plain = {
      id: 'n-plain',
      raw_text: '# Regular',
      note_type: 'NOTE',
      bucket: 'INBOX',
      created_at: '2026-05-01T12:00:00Z',
      modified_at: '2026-05-01T12:00:00Z',
      tag_names: [],
    };
    renderNoteDetail('/notes/n-plain', [plain]);

    await waitFor(() => {
      expect(linksAPI.forNote).toHaveBeenCalled();
    });
    expect(screen.queryByTestId('moc-header')).not.toBeInTheDocument();
    expect(screen.queryByTestId('moc-toc')).not.toBeInTheDocument();
    expect(screen.queryByTestId('moc-badge')).not.toBeInTheDocument();
  });

  it('renders stored HTML content and strips unsafe attributes', async () => {
    vi.mocked(linksAPI.forNote).mockResolvedValue({ outgoing: [], incoming: [] });
    const note = {
      id: 'html-note',
      raw_text: '<h1>Safe title</h1><p><img src="x" onerror="alert(1)" />Body copy</p>',
      note_type: 'NOTE',
      bucket: 'INBOX',
      created_at: '2026-05-01T12:00:00Z',
      modified_at: '2026-05-01T12:00:00Z',
      tag_names: [],
    };
    const { container } = renderNoteDetail('/notes/html-note', [note]);

    const article = await screen.findByRole('button', { name: 'Edit note text' });
    expect(article.innerHTML).toContain('Safe title');
    expect(article.innerHTML).toContain('<h1>');
    const image = container.querySelector('img');
    expect(image).toBeInTheDocument();
    expect(image).not.toHaveAttribute('onerror');
  });

  it('saves edited note HTML through the content field', async () => {
    vi.mocked(linksAPI.forNote).mockResolvedValue({ outgoing: [], incoming: [] });
    const note = {
      id: 'editable-note',
      raw_text: '# Editable note',
      note_type: 'NOTE',
      bucket: 'INBOX',
      created_at: '2026-05-01T12:00:00Z',
      modified_at: '2026-05-01T12:00:00Z',
      tag_names: [],
    };
    const user = userEvent.setup();
    renderNoteDetail('/notes/editable-note', [note]);

    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    await user.click(await screen.findByTestId('btn-save'));

    await waitFor(() => {
      expect(baseStore.updateNote).toHaveBeenCalledWith('editable-note', { content: '<h1>Editable note</h1>' });
    });
  });

  it('resolves typed links from the store and routes them by entity type', async () => {
    vi.mocked(linksAPI.forNote).mockResolvedValue({
      outgoing: [
        { id: 'link-task', src_id: 'note-1', dst_id: 'task-1', link_type: 'related' },
        { id: 'link-project', src_id: 'note-1', dst_id: 'project-1', link_type: 'supports' },
      ],
      incoming: [
        { id: 'link-person', src_id: 'person-1', dst_id: 'note-1', link_type: 'mentions' },
      ],
    });

    vi.mocked(useStore).mockReturnValue({
      ...baseStore,
      notes: [
        {
          id: 'note-1',
          raw_text: '# Source note',
          note_type: 'NOTE',
          bucket: 'INBOX',
          created_at: '2026-05-01T12:00:00Z',
          modified_at: '2026-05-01T12:00:00Z',
          tag_names: [],
        },
      ],
      tasks: [{ id: 'task-1', title: 'Ship the release' }],
      projects: [{ id: 'project-1', name: 'Apollo' }],
      people: [{ id: 'person-1', name: 'Ada Lovelace' }],
      resources: [],
    });

    render(
      <MemoryRouter initialEntries={['/notes/note-1']}>
        <Routes>
          <Route path="/notes/:id" element={<NoteDetailView />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByRole('link', { name: /ship the release/i })).toHaveAttribute('href', '/tasks/task-1');
    expect(screen.getByRole('link', { name: /apollo/i })).toHaveAttribute('href', '/projects/project-1');
    expect(screen.getByRole('link', { name: /ada lovelace/i })).toHaveAttribute('href', '/people/person-1');
    expect(screen.queryByText(/Note task-1/i)).not.toBeInTheDocument();
  });
});
