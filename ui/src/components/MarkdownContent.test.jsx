import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render } from '@testing-library/react';

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
