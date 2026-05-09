import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
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
});
