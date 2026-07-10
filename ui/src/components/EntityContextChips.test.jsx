import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import EntityContextChips from './EntityContextChips';

describe('EntityContextChips', () => {
  it('renders all project, area, and people chips', () => {
    render(
      <MemoryRouter>
        <EntityContextChips
          projects={[{ id: 'p1', title: 'Memory Lookup' }]}
          areas={[{ id: 'a1', title: 'Execution' }]}
          people={[
            { id: 'person-1', title: 'Priya' },
            { id: 'person-2', title: 'Akash' },
          ]}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: /Memory Lookup/i })).toHaveAttribute('href', '/projects/p1');
    expect(screen.getByRole('link', { name: /Execution/i })).toHaveAttribute('href', '/areas/a1');
    expect(screen.getByRole('link', { name: /Priya/i })).toHaveAttribute('href', '/people/person-1');
    expect(screen.getByRole('link', { name: /Akash/i })).toHaveAttribute('href', '/people/person-2');
  });
});
