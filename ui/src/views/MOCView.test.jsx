import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import MOCView from './MOCView';
import useStore from '../stores/useStore';

vi.mock('../stores/useStore');

describe('MOCView', () => {
  beforeEach(() => {
    vi.mocked(useStore).mockReturnValue({ notes: [] });
  });

  it('lists MOC notes with link counts', () => {
    vi.mocked(useStore).mockReturnValue({
      notes: [
        {
          id: 'a',
          raw_text: '# Zebra MOC\n',
          note_type: 'MOC',
          link_count: 4,
          bucket: 'PROJECTS',
          created_at: '2026-01-01',
        },
        {
          id: 'b',
          raw_text: '# Alpha index\n',
          note_type: 'MOC',
          link_count: 1,
          bucket: 'PROJECTS',
          created_at: '2026-01-02',
        },
        { id: 'c', raw_text: '# Regular', note_type: 'NOTE', link_count: 99, bucket: 'INBOX', created_at: '2026-01-03' },
      ],
    });

    render(
      <MemoryRouter>
        <MOCView />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: /maps of content/i })).toBeInTheDocument();
    const list = screen.getByRole('list', { name: /maps of content/i });
    const links = Array.from(list.querySelectorAll('a')).map((a) => a.textContent);
    expect(links).toEqual(['Alpha index', 'Zebra MOC']);
    expect(screen.getByText('1 links')).toBeInTheDocument();
    expect(screen.getByText('4 links')).toBeInTheDocument();
    expect(screen.queryByText('Regular')).not.toBeInTheDocument();
  });

  it('shows empty state when there are no MOC notes', () => {
    vi.mocked(useStore).mockReturnValue({
      notes: [{ id: 'x', raw_text: 'Hi', note_type: 'NOTE', bucket: 'INBOX', created_at: '2026-01-01' }],
    });
    render(
      <MemoryRouter>
        <MOCView />
      </MemoryRouter>,
    );
    expect(screen.getByText(/no moc notes yet/i)).toBeInTheDocument();
  });
});
