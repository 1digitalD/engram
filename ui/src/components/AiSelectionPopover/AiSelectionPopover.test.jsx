import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AiSelectionPopover, { AI_ACTIONS, callAiAction, useTextSelection } from './AiSelectionPopover';

describe('AiSelectionPopover', () => {
  const defaultProps = {
    visible: true,
    position: { x: 100, y: 200 },
    selectedText: 'Hello world',
    onAction: vi.fn(),
    onClose: vi.fn(),
    busy: false,
    result: null,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the popover when visible', () => {
    render(<AiSelectionPopover {...defaultProps} />);
    expect(screen.getByTestId('ai-selection-popover')).toBeInTheDocument();
  });

  it('does not render when not visible', () => {
    render(<AiSelectionPopover {...defaultProps} visible={false} />);
    expect(screen.queryByTestId('ai-selection-popover')).not.toBeInTheDocument();
  });

  it('does not render when selectedText is empty', () => {
    render(<AiSelectionPopover {...defaultProps} selectedText="" />);
    expect(screen.queryByTestId('ai-selection-popover')).not.toBeInTheDocument();
  });

  it('shows the selected text preview', () => {
    render(<AiSelectionPopover {...defaultProps} selectedText="This is a test selection" />);
    expect(screen.getByTestId('ai-selection-popover')).toHaveTextContent('This is a test selection');
  });

  it('truncates long selected text', () => {
    const longText = 'a'.repeat(100);
    render(<AiSelectionPopover {...defaultProps} selectedText={longText} />);
    expect(screen.getByTestId('ai-selection-popover')).toHaveTextContent('...');
  });

  it('renders all four AI action buttons', () => {
    render(<AiSelectionPopover {...defaultProps} />);
    AI_ACTIONS.forEach(action => {
      expect(screen.getByTestId(`ai-action-${action.id}`)).toBeInTheDocument();
    });
  });

  it('shows action labels', () => {
    render(<AiSelectionPopover {...defaultProps} />);
    expect(screen.getByText('Classify')).toBeInTheDocument();
    expect(screen.getByText('Extract Task')).toBeInTheDocument();
    expect(screen.getByText('Create Link')).toBeInTheDocument();
    expect(screen.getByText('Improve Writing')).toBeInTheDocument();
  });

  it('calls onAction with the action id when clicked', async () => {
    const user = userEvent.setup();
    render(<AiSelectionPopover {...defaultProps} />);

    await user.click(screen.getByTestId('ai-action-classify'));
    expect(defaultProps.onAction).toHaveBeenCalledWith('classify');

    await user.click(screen.getByTestId('ai-action-extract_task'));
    expect(defaultProps.onAction).toHaveBeenCalledWith('extract_task');

    await user.click(screen.getByTestId('ai-action-create_link'));
    expect(defaultProps.onAction).toHaveBeenCalledWith('create_link');

    await user.click(screen.getByTestId('ai-action-improve_writing'));
    expect(defaultProps.onAction).toHaveBeenCalledWith('improve_writing');
  });

  it('disables action buttons when busy', () => {
    render(<AiSelectionPopover {...defaultProps} busy={true} />);
    AI_ACTIONS.forEach(action => {
      expect(screen.getByTestId(`ai-action-${action.id}`)).toBeDisabled();
    });
  });

  it('shows result when provided', () => {
    render(<AiSelectionPopover {...defaultProps} result="Classification: Note" />);
    expect(screen.getByTestId('ai-selection-result')).toBeInTheDocument();
    expect(screen.getByTestId('ai-selection-result')).toHaveTextContent('Classification: Note');
  });

  it('does not show result when null', () => {
    render(<AiSelectionPopover {...defaultProps} result={null} />);
    expect(screen.queryByTestId('ai-selection-result')).not.toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', async () => {
    const user = userEvent.setup();
    render(<AiSelectionPopover {...defaultProps} />);

    await user.click(screen.getByTestId('ai-popover-close'));
    expect(defaultProps.onClose).toHaveBeenCalled();
  });

  it('calls onClose when clicking outside', async () => {
    render(
      <div>
        <AiSelectionPopover {...defaultProps} />
        <button data-testid="outside">Outside</button>
      </div>
    );

    await act(async () => {
      fireEvent.mouseDown(screen.getByTestId('outside'));
    });

    expect(defaultProps.onClose).toHaveBeenCalled();
  });

  it('positions the popover at the given coordinates', () => {
    render(<AiSelectionPopover {...defaultProps} position={{ x: 150, y: 300 }} />);
    const popover = screen.getByTestId('ai-selection-popover');
    expect(popover).toHaveStyle({ left: '150px', top: '300px' });
  });
});

describe('AI_ACTIONS', () => {
  it('contains exactly four actions', () => {
    expect(AI_ACTIONS).toHaveLength(4);
  });

  it('has the correct action ids', () => {
    const ids = AI_ACTIONS.map(a => a.id);
    expect(ids).toContain('classify');
    expect(ids).toContain('extract_task');
    expect(ids).toContain('create_link');
    expect(ids).toContain('improve_writing');
  });

  it('each action has label, icon, and description', () => {
    AI_ACTIONS.forEach(action => {
      expect(action).toHaveProperty('id');
      expect(action).toHaveProperty('label');
      expect(action).toHaveProperty('icon');
      expect(action).toHaveProperty('description');
    });
  });
});

describe('callAiAction', () => {
  it('returns a simulated result when no apiCall is provided', async () => {
    const result = await callAiAction('classify', 'Hello world');
    expect(result).toHaveProperty('action', 'classify');
    expect(result).toHaveProperty('text', 'Hello world');
    expect(result).toHaveProperty('result');
  });

  it('calls apiCall when provided', async () => {
    const mockApiCall = vi.fn().mockResolvedValue({ action: 'classify', result: 'done' });
    const result = await callAiAction('classify', 'test text', mockApiCall);
    expect(mockApiCall).toHaveBeenCalledWith('classify', 'test text');
    expect(result).toEqual({ action: 'classify', result: 'done' });
  });
});

describe('useTextSelection', () => {
  it('returns selection state with initial values', () => {
    const { result } = renderHookWithSelection();
    expect(result.current.visible).toBe(false);
    expect(result.current.text).toBe('');
    expect(result.current.position).toEqual({ x: 0, y: 0 });
  });

  it('provides a hide function', () => {
    const { result } = renderHookWithSelection();
    expect(typeof result.current.hide).toBe('function');
  });
});

function renderHookWithSelection() {
  let hookResult;
  const containerRef = { current: document.createElement('div') };

  function TestComponent() {
    hookResult = useTextSelection(containerRef);
    return null;
  }

  render(<TestComponent />);
  return { result: { current: hookResult } };
}
