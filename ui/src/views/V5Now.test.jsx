import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import V5Now from './V5Now';
import { MOCKED_NOW_DATA } from './V5Now.fixtures';

function renderWithRouter(ui) {
  return render(
    <MemoryRouter initialEntries={['/now']}>
      {ui}
    </MemoryRouter>,
  );
}

describe('V5Now', () => {
  it('renders the three sections with mocked data', () => {
    renderWithRouter(<V5Now previewData={MOCKED_NOW_DATA} />);

    expect(screen.getByRole('heading', { name: /Needs you now/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Waiting on you/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Ambient/i })).toBeInTheDocument();

    expect(screen.getByText(/Send yesterday’s standup update/i)).toBeInTheDocument();
    expect(screen.getByText(/Akash is waiting on the GTM brief/i)).toBeInTheDocument();
    expect(screen.getByText(/Q3 strategy doc is still taking shape/i)).toBeInTheDocument();
  });

  it('renders sentence-shaped rows with metadata and action buttons', () => {
    renderWithRouter(<V5Now previewData={MOCKED_NOW_DATA} />);

    expect(screen.getByText('Due in 32 min')).toBeInTheDocument();
    expect(screen.getByText('Hard deadline this morning')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Open$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Mark done/i })).toBeInTheDocument();
  });

  it('renders a thread chip linking to the entity', () => {
    renderWithRouter(<V5Now previewData={MOCKED_NOW_DATA} />);

    const chip = screen.getByText('Product Launch');
    expect(chip).toBeInTheDocument();
    expect(chip.closest('a')).toHaveAttribute('href', '/projects/project-launch');
  });

  it('shows an empty hint when no items are present', () => {
    renderWithRouter(<V5Now previewData={{ needs_you_now: [], waiting_on_you: [], ambient: [] }} />);

    expect(screen.getByText(/No items in your Now view yet/i)).toBeInTheDocument();
  });
});
