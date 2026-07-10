import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';

import CaptureComposer, { CAPTURE_PLACEHOLDER } from './CaptureComposer';

vi.mock('../api/v4Client', () => ({
  v4API: {
    mentions: vi.fn().mockResolvedValue({ results: {} }),
  },
}));

async function typeCapture(text) {
  const field = screen.getByLabelText('Capture text');
  field.focus();
  const user = userEvent.setup();
  await user.type(field, text, { skipClick: true });
}

describe('CaptureComposer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('keeps a quick inline field and opens the expanded composer from +', async () => {
    const onOpenChange = vi.fn();
    render(
      <CaptureComposer
        open={false}
        onOpenChange={onOpenChange}
        quickValue=""
        onQuickChange={vi.fn()}
        onQuickSubmit={vi.fn()}
        value=""
        onChange={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByLabelText('Quick capture')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Open expanded capture' }));
    expect(onOpenChange).toHaveBeenCalledWith(true);
  });

  it('submits quick capture from the inline field', async () => {
    const onQuickSubmit = vi.fn();

    function Harness() {
      const [quickValue, setQuickValue] = useState('');
      return (
        <CaptureComposer
          open={false}
          onOpenChange={vi.fn()}
          quickValue={quickValue}
          onQuickChange={setQuickValue}
          onQuickSubmit={onQuickSubmit}
          value=""
          onChange={vi.fn()}
          onSubmit={vi.fn()}
        />
      );
    }

    render(<Harness />);
    await userEvent.type(screen.getByLabelText('Quick capture'), 'Call Maria back');
    await userEvent.keyboard('{Enter}');

    await waitFor(() => expect(onQuickSubmit).toHaveBeenCalledTimes(1));
  });

  it('carries quick text into the expanded composer when + is clicked', async () => {
    const onChange = vi.fn();
    const onQuickChange = vi.fn();

    render(
      <CaptureComposer
        open={false}
        onOpenChange={vi.fn()}
        quickValue="Apollo sync notes"
        onQuickChange={onQuickChange}
        onQuickSubmit={vi.fn()}
        value=""
        onChange={onChange}
        onSubmit={vi.fn()}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Open expanded capture' }));
    expect(onChange).toHaveBeenCalledWith('Apollo sync notes');
    expect(onQuickChange).toHaveBeenCalledWith('');
  });

  it('shows meeting-note placeholder copy in the expanded editor', () => {
    render(
      <CaptureComposer
        open
        onOpenChange={vi.fn()}
        quickValue=""
        onQuickChange={vi.fn()}
        onQuickSubmit={vi.fn()}
        value=""
        onChange={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    const field = screen.getByLabelText('Capture text');
    expect(field.querySelector('[data-placeholder]')).toHaveAttribute('data-placeholder', CAPTURE_PLACEHOLDER);
    expect(screen.getByRole('dialog', { name: 'Capture' })).toBeInTheDocument();
  });

  it('submits long pasted content from the composer', async () => {
    const onSubmit = vi.fn();

    function Harness() {
      const [value, setValue] = useState('');
      return (
        <CaptureComposer
          open
          onOpenChange={vi.fn()}
          quickValue=""
          onQuickChange={vi.fn()}
          onQuickSubmit={vi.fn()}
          value={value}
          onChange={setValue}
          onSubmit={onSubmit}
        />
      );
    }

    render(<Harness />);

    await typeCapture('Apollo sync\n- agreed on 2-yr term\n- legal review Friday');
    await userEvent.click(screen.getByRole('button', { name: 'Capture' }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
  });
});
