import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import TopBar from './TopBar';

function renderWithRouter(ui, { initialEntries = ['/now'] } = {}) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      {ui}
    </MemoryRouter>,
  );
}

describe('TopBar', () => {
  it('renders brand, lenses, Ask, theme switcher, and trust chip', () => {
    renderWithRouter(<TopBar trustScore={87} onAsk={() => {}} />);

    expect(screen.getByRole('link', { name: /Engram home/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Now/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Threads/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Recall/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Ask Engram/i })).toBeInTheDocument();
    expect(screen.getByRole('group', { name: /Theme/i })).toBeInTheDocument();
    expect(screen.getByText('87%')).toBeInTheDocument();
  });

  it('marks the active lens based on the current route', () => {
    renderWithRouter(<TopBar trustScore={87} onAsk={() => {}} />, { initialEntries: ['/threads'] });

    expect(screen.getByRole('link', { name: /Threads/i })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: /Now/i })).not.toHaveAttribute('aria-current');
  });

  it('calls onAsk when the Ask button is clicked', () => {
    const onAsk = vi.fn();
    renderWithRouter(<TopBar trustScore={87} onAsk={onAsk} />);

    fireEvent.click(screen.getByRole('button', { name: /Ask Engram/i }));
    expect(onAsk).toHaveBeenCalledTimes(1);
  });

  it('changes document theme when a theme option is selected', () => {
    delete document.documentElement.dataset.theme;
    renderWithRouter(<TopBar trustScore={87} onAsk={() => {}} />);

    expect(document.documentElement.dataset.theme).toBe('light');

    fireEvent.click(screen.getByRole('button', { name: /Dark theme/i }));
    expect(document.documentElement.dataset.theme).toBe('dark');

    delete document.documentElement.dataset.theme;
  });

  it('renders count pills for supported lenses and hides unsupported ones', () => {
    renderWithRouter(
      <TopBar
        trustScore={87}
        onAsk={() => {}}
        onRecall={() => {}}
        onReview={() => {}}
        nowCount={3}
        threadsCount={7}
        suggestionsCount={5}
      />,
    );

    expect(screen.getByRole('link', { name: /Now/i })).toHaveTextContent('3');
    expect(screen.getByRole('link', { name: /Threads/i })).toHaveTextContent('7');
    expect(screen.getByRole('button', { name: /Recall/i })).not.toHaveTextContent(/\d/);
    expect(screen.getByRole('button', { name: /Review 5 pending suggestions/i })).toBeInTheDocument();
  });

  it('calls onReview when the review badge is clicked', () => {
    const onReview = vi.fn();
    renderWithRouter(
      <TopBar trustScore={87} onAsk={() => {}} onReview={onReview} suggestionsCount={2} />,
    );

    fireEvent.click(screen.getByRole('button', { name: /Review 2 pending suggestions/i }));
    expect(onReview).toHaveBeenCalledTimes(1);
  });
});
