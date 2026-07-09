import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from './App';

vi.mock('./next/TodaySurface', () => ({ default: () => <main data-testid="v6-today">Today</main> }));
vi.mock('./legacy/LegacyApp', () => ({ default: () => <main data-testid="legacy-shell">Legacy</main> }));

describe('App router', () => {
  it('mounts NextApp at root paths', async () => {
    render(
      <MemoryRouter initialEntries={['/today']}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('v6-today')).toBeInTheDocument();
  });

  it('mounts LegacyApp under /legacy', async () => {
    render(
      <MemoryRouter initialEntries={['/legacy/now']}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('legacy-shell')).toBeInTheDocument();
  });
});
