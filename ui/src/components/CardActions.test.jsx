import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { v4API } from '../api/v4Client';
import CardActions from './CardActions';

vi.mock('../api/v4Client', () => ({
  v4API: {
    entities: {
      update: vi.fn(),
      delete: vi.fn(),
    },
  },
}));

describe('CardActions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    v4API.entities.update.mockResolvedValue({});
    v4API.entities.delete.mockResolvedValue({});
  });

  it('archives an entity and notifies the parent', async () => {
    const onChanged = vi.fn();
    render(
      <CardActions
        entity={{ id: 't1', title: 'Ship it' }}
        onChanged={onChanged}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /Archive Ship it/i }));

    await waitFor(() => {
      expect(v4API.entities.update).toHaveBeenCalledWith('t1', { lifecycle: 'archived' });
      expect(onChanged).toHaveBeenCalledWith({ kind: 'archived', id: 't1' });
    });
  });

  it('deletes an entity and notifies the parent', async () => {
    const onChanged = vi.fn();
    render(
      <CardActions
        entity={{ id: 't1', title: 'Ship it' }}
        onChanged={onChanged}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /Delete Ship it/i }));

    await waitFor(() => {
      expect(v4API.entities.delete).toHaveBeenCalledWith('t1');
      expect(onChanged).toHaveBeenCalledWith({ kind: 'deleted', id: 't1' });
    });
  });
});
