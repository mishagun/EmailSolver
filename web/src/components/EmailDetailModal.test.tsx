import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { EmailDetailModal } from './EmailDetailModal';
import { mockEmail, mockEmail2 } from '../test/fixtures';

describe('EmailDetailModal', () => {
  it('renders email details', () => {
    // Arrange & Act
    render(<EmailDetailModal email={mockEmail} onClose={vi.fn()} onAction={vi.fn()} />);

    // Assert
    expect(screen.getByText('test@example.com')).toBeInTheDocument();
    expect(screen.getByText('example.com')).toBeInTheDocument();
    expect(screen.getByText('test email subject')).toBeInTheDocument();
    expect(screen.getByText('primary')).toBeInTheDocument();
    expect(screen.getByText('person')).toBeInTheDocument();
    expect(screen.getByText('95%')).toBeInTheDocument();
  });

  it('shows importance as stars', () => {
    // Arrange & Act
    render(<EmailDetailModal email={mockEmail} onClose={vi.fn()} onAction={vi.fn()} />);

    // Assert
    expect(screen.getByText('★★★☆☆')).toBeInTheDocument();
  });

  it('shows unsubscribe status', () => {
    // Arrange & Act
    render(<EmailDetailModal email={mockEmail2} onClose={vi.fn()} onAction={vi.fn()} />);

    // Assert
    expect(screen.getByText('yes')).toBeInTheDocument();
  });

  it('calls onClose when close button clicked', async () => {
    // Arrange
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<EmailDetailModal email={mockEmail} onClose={onClose} onAction={vi.fn()} />);

    // Act
    await user.click(screen.getByText('×'));

    // Assert
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('calls onClose when overlay clicked', async () => {
    // Arrange
    const user = userEvent.setup();
    const onClose = vi.fn();
    const { container } = render(<EmailDetailModal email={mockEmail} onClose={onClose} onAction={vi.fn()} />);

    // Act
    await user.click(container.querySelector('.overlay')!);

    // Assert
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('does not call onClose when modal body clicked', async () => {
    // Arrange
    const user = userEvent.setup();
    const onClose = vi.fn();
    const { container } = render(<EmailDetailModal email={mockEmail} onClose={onClose} onAction={vi.fn()} />);

    // Act
    await user.click(container.querySelector('.modal')!);

    // Assert
    expect(onClose).not.toHaveBeenCalled();
  });

  it('calls onAction when action button clicked', async () => {
    // Arrange
    const user = userEvent.setup();
    const onAction = vi.fn();
    render(<EmailDetailModal email={mockEmail} onClose={vi.fn()} onAction={onAction} />);

    // Act
    await user.click(screen.getByText('spam'));

    // Assert
    expect(onAction).toHaveBeenCalledWith('mark_spam', mockEmail.id);
  });

  it('calls onClose on Escape key', async () => {
    // Arrange
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<EmailDetailModal email={mockEmail} onClose={onClose} onAction={vi.fn()} />);

    // Act
    await user.keyboard('{Escape}');

    // Assert
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('shows snippet when present', () => {
    // Arrange & Act
    render(<EmailDetailModal email={mockEmail} onClose={vi.fn()} onAction={vi.fn()} />);

    // Assert
    expect(screen.getByText('this is a test email snippet')).toBeInTheDocument();
  });

  it('shows action_taken as colored badge when present', () => {
    // Arrange
    const emailWithAction = { ...mockEmail, action_taken: 'move_to_category' };

    // Act
    const { container } = render(<EmailDetailModal email={emailWithAction} onClose={vi.fn()} onAction={vi.fn()} />);

    // Assert
    const fields = container.querySelectorAll('.field');
    const actionField = Array.from(fields).find(f =>
      f.querySelector('.field-label')?.textContent === 'action taken'
    );
    const badge = actionField?.querySelector('.badge-moved');
    expect(badge).toBeInTheDocument();
    expect(badge?.textContent).toBe('moved');
  });

  it('shows "none" as muted text when no action taken', () => {
    // Arrange & Act
    const { container } = render(<EmailDetailModal email={mockEmail} onClose={vi.fn()} onAction={vi.fn()} />);

    // Assert
    const fields = container.querySelectorAll('.field');
    const actionField = Array.from(fields).find(f =>
      f.querySelector('.field-label')?.textContent === 'action taken'
    );
    const muted = actionField?.querySelector('.muted');
    expect(muted).toBeInTheDocument();
    expect(muted?.textContent).toBe('none');
  });
});
