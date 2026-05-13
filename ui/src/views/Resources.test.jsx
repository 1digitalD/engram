import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Resources from './Resources';
import useStore from '../stores/useStore';

vi.mock('../stores/useStore');

describe('Resources', () => {
  it('links each resource card to its detail route', () => {
    vi.mocked(useStore).mockReturnValue({
      resources: [{
        id: 'r1',
        title: 'Design Notes',
        resource_type: 'ARTICLE',
        author: 'Ada',
        is_read: true,
        rating: 4,
      }],
    });

    render(
      <MemoryRouter>
        <Resources />
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: /Design Notes/i })).toHaveAttribute('href', '/resources/r1');
  });
});
