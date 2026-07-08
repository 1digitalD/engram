import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import {
  EntryAttachAffordance,
  GroupCommitmentComposer,
  TaskAffordances,
} from './TypedAffordances';

const PEOPLE = [
  { id: 'person-operator', title: 'Operator' },
  { id: 'person-sam', title: 'Sam' },
];

const SPACES = [
  { id: 'space-apollo', title: 'Apollo' },
  { id: 'space-orbit', title: 'Orbit' },
];

const ITEM = {
  id: 'task-1',
  title: 'Close contract',
  status: 'open',
  due_at: '2026-07-07T12:00:00Z',
  owner: { id: 'person-operator', title: 'Operator' },
  space: { id: 'space-apollo', title: 'Apollo' },
};

describe('TaskAffordances', () => {
  it('submits status, due, move, owner, update, and done actions', () => {
    const onStatusChange = vi.fn();
    const onDueChange = vi.fn();
    const onMoveSpace = vi.fn();
    const onHandOwner = vi.fn();
    const onLogUpdate = vi.fn();
    const onMarkDone = vi.fn();

    render(
      <TaskAffordances
        item={ITEM}
        people={PEOPLE}
        spaces={SPACES}
        onStatusChange={onStatusChange}
        onDueChange={onDueChange}
        onMoveSpace={onMoveSpace}
        onHandOwner={onHandOwner}
        onLogUpdate={onLogUpdate}
        onMarkDone={onMarkDone}
      />,
    );

    fireEvent.change(screen.getByLabelText('Close contract status'), {
      target: { value: 'blocked' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Set status' }));
    expect(onStatusChange).toHaveBeenCalledWith('task-1', 'blocked');

    fireEvent.change(screen.getByLabelText('Close contract due date'), {
      target: { value: '2026-07-20' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Set due date' }));
    expect(onDueChange).toHaveBeenCalledWith('task-1', '2026-07-20');

    fireEvent.change(screen.getByLabelText('Close contract move to space'), {
      target: { value: 'space-orbit' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Move to space' }));
    expect(onMoveSpace).toHaveBeenCalledWith('task-1', 'space-orbit');

    fireEvent.change(screen.getByLabelText('Close contract hand to owner'), {
      target: { value: 'person-sam' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Hand to owner' }));
    expect(onHandOwner).toHaveBeenCalledWith('task-1', 'person-sam');

    fireEvent.change(screen.getByLabelText('Close contract log update'), {
      target: { value: 'Sent the revised draft.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Log update' }));
    expect(onLogUpdate).toHaveBeenCalledWith('task-1', 'Sent the revised draft.');

    fireEvent.click(screen.getByRole('button', { name: 'Mark done' }));
    expect(onMarkDone).toHaveBeenCalledWith('task-1');
  });
});

describe('GroupCommitmentComposer', () => {
  it('submits a new commitment title for the bucket', () => {
    const onSubmit = vi.fn();
    render(<GroupCommitmentComposer label="Apollo" onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('Add commitment for Apollo'), {
      target: { value: 'Ship final copy' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add commitment' }));

    expect(onSubmit).toHaveBeenCalledWith('Ship final copy');
  });
});

describe('EntryAttachAffordance', () => {
  it('attaches the entry to the selected target', () => {
    const onAttach = vi.fn();
    render(
      <EntryAttachAffordance
        entryTitle="Morning standup"
        targets={[...PEOPLE, ...SPACES]}
        onAttach={onAttach}
      />,
    );

    fireEvent.change(screen.getByLabelText('Attach Morning standup'), {
      target: { value: 'space-apollo' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Attach entry' }));

    expect(onAttach).toHaveBeenCalledWith('space-apollo');
  });
});
