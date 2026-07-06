import {
  describe, expect, it, vi,
} from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import InlineTitleEditor from './InlineTitleEditor';

describe('InlineTitleEditor', () => {
  it('renders the title as a heading', () => {
    render(
      <InlineTitleEditor title="Write docs" onSave={vi.fn()} />,
    );

    expect(screen.getByRole('heading', { level: 1, name: 'Write docs' })).toBeInTheDocument();
  });

  it('shows empty label when title is missing', () => {
    render(
      <InlineTitleEditor title="" onSave={vi.fn()} emptyLabel="(no title)" />,
    );

    expect(screen.getByRole('heading', { level: 1, name: '(no title)' })).toBeInTheDocument();
  });

  it('enters edit mode on click and saves on Enter', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <InlineTitleEditor title="Write docs" onSave={onSave} />,
    );

    await userEvent.click(screen.getByRole('button', { name: /Title: Write docs/i }));

    const input = screen.getByLabelText('Title');
    expect(input).toHaveValue('Write docs');

    await userEvent.clear(input);
    await userEvent.type(input, 'Updated docs');
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith('Updated docs');
    });
  });

  it('cancels on Escape without saving', async () => {
    const onSave = vi.fn();
    render(
      <InlineTitleEditor title="Write docs" onSave={onSave} />,
    );

    await userEvent.click(screen.getByRole('button', { name: /Title: Write docs/i }));
    const input = screen.getByLabelText('Title');
    await userEvent.clear(input);
    await userEvent.type(input, 'Discarded');
    fireEvent.keyDown(input, { key: 'Escape' });

    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByRole('heading', { level: 1, name: 'Write docs' })).toBeInTheDocument();
  });

  it('reverts when save fails', async () => {
    const onSave = vi.fn().mockRejectedValue(new Error('Save failed'));
    render(
      <InlineTitleEditor title="Write docs" onSave={onSave} />,
    );

    await userEvent.click(screen.getByRole('button', { name: /Title: Write docs/i }));
    const input = screen.getByLabelText('Title');
    await userEvent.clear(input);
    await userEvent.type(input, 'Broken save');
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith('Broken save');
    });
    expect(screen.getByRole('heading', { level: 1, name: 'Write docs' })).toBeInTheDocument();
  });
});
