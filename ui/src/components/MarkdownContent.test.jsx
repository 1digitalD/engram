import { describe, it, expect, vi } from 'vitest';

vi.mock('./MarkdownContent', () => ({
  default: ({ content }) => content || null,
}));

import MarkdownContent from './MarkdownContent';

describe('MarkdownContent mock', () => {
  it('uses the mock', () => {
    expect(typeof MarkdownContent).toBe('function');
    expect(MarkdownContent.toString()).not.toContain('ReactMarkdown');
  });
});
