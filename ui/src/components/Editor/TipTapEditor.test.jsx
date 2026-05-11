import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TipTapEditor, { createTaskFromSelection } from './TipTapEditor';
import useStore from '../../stores/useStore';

vi.mock('../../stores/useStore');

const mockStore = {
  createTask: vi.fn(),
  addToast: vi.fn(),
  tags: [],
};

const renderEditor = (props = {}) => {
  vi.mocked(useStore).mockReturnValue({ ...mockStore });
  return render(
    <TipTapEditor
      initialContent="<p>Hello world</p>"
      onSave={vi.fn()}
      placeholder="Start writing..."
      noteId="test-note-1"
      {...props}
    />
  );
};

describe('TipTapEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the editor container', async () => {
    renderEditor();
    await waitFor(() => {
      expect(screen.getByTestId('tiptap-editor')).toBeInTheDocument();
    });
  });

  it('renders the toolbar', async () => {
    renderEditor();
    await waitFor(() => {
      expect(screen.getByTestId('editor-toolbar')).toBeInTheDocument();
    });
  });

  it('renders formatting buttons in toolbar', async () => {
    renderEditor();
    await waitFor(() => {
      expect(screen.getByTestId('btn-bold')).toBeInTheDocument();
      expect(screen.getByTestId('btn-italic')).toBeInTheDocument();
      expect(screen.getByTestId('btn-h1')).toBeInTheDocument();
      expect(screen.getByTestId('btn-h2')).toBeInTheDocument();
    });
  });

  it('renders list buttons in toolbar', async () => {
    renderEditor();
    await waitFor(() => {
      expect(screen.getByTestId('btn-bullet-list')).toBeInTheDocument();
      expect(screen.getByTestId('btn-ordered-list')).toBeInTheDocument();
      expect(screen.getByTestId('btn-task-list')).toBeInTheDocument();
      expect(screen.getByTestId('btn-quote')).toBeInTheDocument();
      expect(screen.getByTestId('btn-code')).toBeInTheDocument();
    });
  });

  it('renders AI assistant button in toolbar', async () => {
    renderEditor();
    await waitFor(() => {
      expect(screen.getByTestId('btn-ai-assistant')).toBeInTheDocument();
    });
  });

  it('renders preview toggle button', async () => {
    renderEditor();
    await waitFor(() => {
      expect(screen.getByTestId('btn-preview')).toBeInTheDocument();
    });
  });

  it('renders save button', async () => {
    renderEditor();
    await waitFor(() => {
      expect(screen.getByTestId('btn-save')).toBeInTheDocument();
    });
  });

  it('shows character count in footer', async () => {
    renderEditor();
    await waitFor(() => {
      expect(screen.getByText(/characters/)).toBeInTheDocument();
    });
  });

  it('renders editor content area', async () => {
    renderEditor();
    await waitFor(() => {
      expect(screen.getByTestId('editor-wrapper')).toBeInTheDocument();
    });
  });

  it('opens AI panel when AI button is clicked', async () => {
    const user = userEvent.setup();
    renderEditor();

    await waitFor(() => {
      expect(screen.getByTestId('btn-ai-assistant')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('btn-ai-assistant'));

    await waitFor(() => {
      expect(screen.getByTestId('ai-panel')).toBeInTheDocument();
    });
  });

  it('closes AI panel when close button is clicked', async () => {
    const user = userEvent.setup();
    renderEditor();

    await waitFor(() => {
      expect(screen.getByTestId('btn-ai-assistant')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('btn-ai-assistant'));
    await waitFor(() => {
      expect(screen.getByTestId('ai-panel')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('ai-panel').querySelector('[aria-label="Close AI panel"]'));

    await waitFor(() => {
      expect(screen.queryByTestId('ai-panel')).not.toBeInTheDocument();
    });
  });

  it('shows AI prompt textarea in AI panel', async () => {
    const user = userEvent.setup();
    renderEditor();

    await user.click(screen.getByTestId('btn-ai-assistant'));

    await waitFor(() => {
      expect(screen.getByTestId('ai-prompt')).toBeInTheDocument();
    });
  });

  it('toggles preview mode when preview button is clicked', async () => {
    const user = userEvent.setup();
    renderEditor();

    await waitFor(() => {
      expect(screen.getByTestId('editor-wrapper')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('btn-preview'));

    await waitFor(() => {
      expect(screen.getByTestId('editor-preview')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('editor-wrapper')).not.toBeInTheDocument();
  });

  it('calls onSave when save button is clicked', async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    renderEditor({ onSave });

    await waitFor(() => {
      expect(screen.getByTestId('btn-save')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('btn-save'));

    expect(onSave).toHaveBeenCalled();
    const callArgs = onSave.mock.calls[0][0];
    expect(callArgs).toHaveProperty('html');
    expect(callArgs).toHaveProperty('text');
    expect(callArgs.noteId).toBe('test-note-1');
  });

  it('renders with initial content', async () => {
    renderEditor({ initialContent: '<p>Test content</p>' });
    await waitFor(() => {
      expect(screen.getByTestId('tiptap-editor')).toBeInTheDocument();
    });
  });
});

describe('createTaskFromSelection', () => {
  it('creates a task from selected text', () => {
    const mockEditor = {
      state: {
        selection: { from: 0, to: 11 },
        doc: {
          textBetween: (from, to) => 'Hello world'.slice(from, to),
        },
      },
    };
    const createTaskFn = vi.fn();

    createTaskFromSelection(mockEditor, createTaskFn, 'note-1');

    expect(createTaskFn).toHaveBeenCalledWith({
      title: 'Hello world',
      note_id: 'note-1',
    });
  });

  it('does nothing when no text is selected', () => {
    const mockEditor = {
      state: {
        selection: { from: 0, to: 0 },
        doc: {
          textBetween: () => '',
        },
      },
    };
    const createTaskFn = vi.fn();

    createTaskFromSelection(mockEditor, createTaskFn, 'note-1');

    expect(createTaskFn).not.toHaveBeenCalled();
  });

  it('does nothing when editor is null', () => {
    const createTaskFn = vi.fn();
    createTaskFromSelection(null, createTaskFn, 'note-1');
    expect(createTaskFn).not.toHaveBeenCalled();
  });
});
