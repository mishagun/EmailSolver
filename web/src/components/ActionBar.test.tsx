import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ActionBar } from './ActionBar';

describe('ActionBar', () => {
  it('renders all action buttons including undo', () => {
    // Arrange & Act
    render(<ActionBar scope="3 selected" onAction={vi.fn()} />);

    // Assert
    expect(screen.getByText('[k] keep')).toBeInTheDocument();
    expect(screen.getByText('[m] mark read')).toBeInTheDocument();
    expect(screen.getByText('[v] move')).toBeInTheDocument();
    expect(screen.getByText('[s] spam')).toBeInTheDocument();
    expect(screen.getByText('[u] unsub')).toBeInTheDocument();
    expect(screen.getByText('[z] undo')).toBeInTheDocument();
  });

  it('displays scope text', () => {
    // Arrange & Act
    render(<ActionBar scope="category: newsletters" onAction={vi.fn()} />);

    // Assert
    expect(screen.getByText('category: newsletters')).toBeInTheDocument();
  });

  it('calls onAction with correct action type when button clicked', async () => {
    // Arrange
    const user = userEvent.setup();
    const onAction = vi.fn();
    render(<ActionBar scope="all" onAction={onAction} />);

    // Act
    await user.click(screen.getByText('[s] spam'));

    // Assert
    expect(onAction).toHaveBeenCalledWith('mark_spam');
  });

  it('disables buttons when disabled prop is true', () => {
    // Arrange & Act
    render(<ActionBar scope="all" onAction={vi.fn()} disabled={true} />);

    // Assert
    const buttons = screen.getAllByRole('button');
    buttons.forEach(btn => {
      expect(btn).toBeDisabled();
    });
  });

  it('undo button is disabled when canUndo is false', () => {
    // Arrange & Act
    render(<ActionBar scope="all" onAction={vi.fn()} canUndo={false} />);

    // Assert
    const undoBtn = screen.getByText('[z] undo');
    expect(undoBtn).toBeDisabled();
  });

  it('undo button is enabled when canUndo is true', () => {
    // Arrange & Act
    render(<ActionBar scope="all" onAction={vi.fn()} canUndo={true} />);

    // Assert
    const undoBtn = screen.getByText('[z] undo');
    expect(undoBtn).not.toBeDisabled();
  });

  it('calls onAction with undo when undo button clicked', async () => {
    // Arrange
    const user = userEvent.setup();
    const onAction = vi.fn();
    render(<ActionBar scope="all" onAction={onAction} canUndo={true} />);

    // Act
    await user.click(screen.getByText('[z] undo'));

    // Assert
    expect(onAction).toHaveBeenCalledWith('undo');
  });

  it('shows tooltips on action buttons', () => {
    // Arrange & Act
    render(<ActionBar scope="all" onAction={vi.fn()} />);

    // Assert
    expect(screen.getByTitle('move to spam, remove from inbox')).toBeInTheDocument();
    expect(screen.getByTitle('undo last action')).toBeInTheDocument();
  });
});
