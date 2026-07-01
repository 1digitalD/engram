import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CitationsList, { truncateSnippet, formatCitationDate } from './CitationsList';

describe('CitationsList', () => {
  it('renders a card for each citation with glyph, snippet, date, and open button', () => {
    const citations = [
      {
        entity_id: 'note-1',
        snippet: 'Mary said she would review by Friday.',
        created_at: '2026-06-22T14:00:00+00:00',
      },
    ];

    render(<CitationsList citations={citations} onOpen={() => {}} />);

    expect(screen.getByText('📝')).toBeInTheDocument();
    expect(screen.getByText('Mary said she would review by Friday.')).toBeInTheDocument();
    expect(screen.getByText('Jun 22, 2026')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Open citation 1/i })).toBeInTheDocument();
  });

  it('truncates snippets longer than 140 characters', () => {
    const longSnippet = 'a'.repeat(200);
    const citations = [{ entity_id: 'note-1', snippet: longSnippet }];

    render(<CitationsList citations={citations} />);

    const expected = `${'a'.repeat(140)}…`;
    expect(screen.getByText(expected)).toBeInTheDocument();
  });

  it('calls onOpen with the citation when the open button is clicked', async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    const citations = [
      {
        entity_id: 'note-1',
        snippet: 'Mary said she would review by Friday.',
        created_at: '2026-06-22T14:00:00+00:00',
      },
    ];

    render(<CitationsList citations={citations} onOpen={onOpen} />);
    await user.click(screen.getByRole('button', { name: /Open citation 1/i }));

    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(onOpen).toHaveBeenCalledWith(citations[0]);
  });

  it('renders empty text when there are no citations', () => {
    render(<CitationsList citations={[]} emptyText="No citations available." />);
    expect(screen.getByText('No citations available.')).toBeInTheDocument();
  });

  it('returns null for empty citations when no empty text is provided', () => {
    const { container } = render(<CitationsList citations={[]} />);
    expect(container.firstChild).toBeNull();
  });
});

describe('truncateSnippet', () => {
  it('truncates long snippets to the default length', () => {
    expect(truncateSnippet('a'.repeat(200))).toBe(`${'a'.repeat(140)}…`);
  });

  it('returns short snippets unchanged', () => {
    expect(truncateSnippet('short')).toBe('short');
  });

  it('handles empty and null snippets', () => {
    expect(truncateSnippet('')).toBe('');
    expect(truncateSnippet(null)).toBe('');
  });
});

describe('formatCitationDate', () => {
  it('formats ISO dates', () => {
    expect(formatCitationDate('2026-06-22T14:00:00+00:00')).toBe('Jun 22, 2026');
  });

  it('returns empty string for invalid or missing dates', () => {
    expect(formatCitationDate('')).toBe('');
    expect(formatCitationDate(null)).toBe('');
    expect(formatCitationDate('not a date')).toBe('');
  });
});
