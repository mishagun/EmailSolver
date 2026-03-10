import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HoverActions } from './HoverActions';

describe('HoverActions', () => {
  it('renders all five action buttons without undo', () => {
    // Arrange & Act
    render(<HoverActions onAction={vi.fn()} />);

    // Assert
    expect(screen.getByText('k')).toBeInTheDocument();
    expect(screen.getByText('m')).toBeInTheDocument();
    expect(screen.getByText('v')).toBeInTheDocument();
    expect(screen.getByText('s')).toBeInTheDocument();
    expect(screen.getByText('u')).toBeInTheDocument();
    expect(screen.queryByText('undo')).not.toBeInTheDocument();
  });

  it('calls onAction with correct action type when clicked', async () => {
    // Arrange
    const user = userEvent.setup();
    const onAction = vi.fn();
    render(<HoverActions onAction={onAction} />);

    // Act
    await user.click(screen.getByText('s'));

    // Assert
    expect(onAction).toHaveBeenCalledWith('mark_spam');
  });

  it('stops event propagation on click', async () => {
    // Arrange
    const user = userEvent.setup();
    const parentClick = vi.fn();
    const onAction = vi.fn();
    render(
      <div onClick={parentClick}>
        <HoverActions onAction={onAction} />
      </div>
    );

    // Act
    await user.click(screen.getByText('k'));

    // Assert
    expect(onAction).toHaveBeenCalledWith('keep');
    expect(parentClick).not.toHaveBeenCalled();
  });

  it('has tooltips on all buttons', () => {
    // Arrange & Act
    render(<HoverActions onAction={vi.fn()} />);

    // Assert
    expect(screen.getByTitle('keep — mark as reviewed')).toBeInTheDocument();
    expect(screen.getByTitle('spam — move to spam')).toBeInTheDocument();
  });
});
