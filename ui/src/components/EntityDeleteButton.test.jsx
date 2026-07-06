import {
  describe, expect, it, vi,
} from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { v4API } from '../api/v4Client';
import EntityDeleteButton from './EntityDeleteButton';

vi.mock('../api/v4Client', () => ({
  v4API: {
    entities: {
      delete: vi.fn(),
    },
  },
  friendlyApiError: (err, fallback) => err?.message || fallback || 'Something went wrong.',
}));

describe('EntityDeleteButton', () => {
  it('deletes an entity and notifies the parent', async () => {
    v4API.entities.delete.mockResolvedValue({});
    const onDeleted = vi.fn();

    render(
      <EntityDeleteButton
        entity={{ id: 'resource-1', type: 'resource', title: 'PRD draft' }}
        onDeleted={onDeleted}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /Delete PRD draft/i }));

    await waitFor(() => {
      expect(v4API.entities.delete).toHaveBeenCalledWith('resource-1');
      expect(onDeleted).toHaveBeenCalled();
    });
  });

  it('reports delete failures', async () => {
    v4API.entities.delete.mockRejectedValue(new Error('Delete failed'));
    const onError = vi.fn();

    render(
      <EntityDeleteButton
        entity={{ id: 'resource-1', type: 'resource', title: 'PRD draft' }}
        onError={onError}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /Delete PRD draft/i }));

    await waitFor(() => {
      expect(onError).toHaveBeenCalledWith('Delete failed');
    });
  });
});
