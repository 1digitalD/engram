import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MarkdownEditor from './MarkdownEditor';

vi.mock('../api/v4Client', () => ({
  v4API: { mentions: vi.fn().mockResolvedValue({ results: {} }) },
}));

async function typeInto(field, text) {
  field.focus();
  const user = userEvent.setup();
  await user.type(field, text, { skipClick: true });
}

describe('MarkdownEditor', () => {
  it('flows typed content to onChange as markdown', async () => {
    const onChange = vi.fn();
    render(<MarkdownEditor value="" onChange={onChange} ariaLabel="Test field" />);
    const field = screen.getByLabelText('Test field');

    await typeInto(field, 'Hello world');

    expect(onChange).toHaveBeenLastCalledWith('Hello world');
  });

  it('renders placeholder text via data-placeholder when empty', () => {
    render(
      <MarkdownEditor value="" onChange={() => {}} ariaLabel="Test field" placeholder="Write something specific" />,
    );
    const field = screen.getByLabelText('Test field');
    const placeholderNode = field.querySelector('[data-placeholder]');

    expect(placeholderNode).toHaveAttribute('data-placeholder', 'Write something specific');
  });

  it('renders mention markdown links unchanged as anchors', () => {
    render(
      <MarkdownEditor
        value="See [Platform](/projects/proj1) for details"
        onChange={() => {}}
        ariaLabel="Test field"
      />,
    );
    const field = screen.getByLabelText('Test field');
    const link = field.querySelector('a[href="/projects/proj1"]');

    expect(link).toHaveTextContent('Platform');
  });

  it('respects editable=false to prevent edits', () => {
    render(<MarkdownEditor value="Locked" onChange={() => {}} ariaLabel="Test field" editable={false} />);
    const field = screen.getByLabelText('Test field');

    expect(field).toHaveAttribute('contenteditable', 'false');
  });

  it('is editable by default', () => {
    render(<MarkdownEditor value="" onChange={() => {}} ariaLabel="Test field" />);
    const field = screen.getByLabelText('Test field');

    expect(field).toHaveAttribute('contenteditable', 'true');
  });
});
