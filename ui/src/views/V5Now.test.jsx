import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
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
  it('renders three sections from mocked data', () => {
    renderWithRouter(<V5Now previewData={MOCKED_NOW_DATA} />);
    expect(screen.getByRole('heading', { name: /Needs you now/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Waiting on you/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Ambient/i })).toBeInTheDocument();
    expect(screen.getByText(/Send yesterday’s standup update/i)).toBeInTheDocument();
    expect(screen.getByText(/GTM brief/i)).toBeInTheDocument();
    expect(screen.getByText(/Q3 strategy doc is still taking shape/i)).toBeInTheDocument();
  });

  it('renders sentence-shaped rows with metadata and action buttons', () => {
    renderWithRouter(<V5Now previewData={MOCKED_NOW_DATA} />);
    expect(screen.getByText('Due in 32 min')).toBeInTheDocument();
    expect(screen.getByText('Hard deadline this morning')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Open$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Mark done/i })).toBeInTheDocument();
  });

  it('links the sentence to the item and the chip to the parent thread', () => {
    renderWithRouter(<V5Now previewData={MOCKED_NOW_DATA} />);

    const sentence = screen.getByText(/Send yesterday’s standup update/i);
    const chip = screen.getByText('Product Launch');

    expect(sentence.closest('a')).toHaveAttribute('href', '/tasks/task-standup');
    expect(chip.closest('a')).toHaveAttribute('href', '/projects/project-launch');
  });

  it('keeps open navigation distinct from thread navigation', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={['/now']}>
        <Routes>
          <Route path="/now" element={<V5Now previewData={MOCKED_NOW_DATA} />} />
          <Route path="/tasks/:id" element={<div>Task detail</div>} />
          <Route path="/projects/:id" element={<div>Project detail</div>} />
        </Routes>
      </MemoryRouter>,
    );

    await user.click(screen.getByRole('button', { name: /^Open$/i }));
    expect(await screen.findByText('Task detail')).toBeInTheDocument();
  });

  it('shows an empty hint when no items are present', () => {
    renderWithRouter(<V5Now previewData={{ needs_you_now: [], waiting_on_you: [], ambient: [] }} />);
    expect(screen.getByText(/No items in your Now view yet/i)).toBeInTheDocument();
  });
});
