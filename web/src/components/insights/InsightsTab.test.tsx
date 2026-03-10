import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { InsightsTab } from './InsightsTab';
import { mockEmail, mockEmail2 } from '../../test/fixtures';
import type { ClassifiedEmail } from '../../api/types';

// recharts ResponsiveContainer needs dimensions — stub it
vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div style={{ width: 500, height: 300 }}>{children}</div>
    ),
  };
});

describe('InsightsTab', () => {
  const onCategoryClick = vi.fn();

  it('renders empty state when no emails', () => {
    // Arrange & Act
    render(<InsightsTab emails={[]} isInboxScan={false} onCategoryClick={onCategoryClick} />);

    // Assert
    expect(screen.getByText('no emails to analyze')).toBeInTheDocument();
  });

  it('renders stat cards with correct values', () => {
    // Arrange
    const emails = [mockEmail, mockEmail2];

    // Act
    render(<InsightsTab emails={emails} isInboxScan={false} onCategoryClick={onCategoryClick} />);

    // Assert
    const totalCard = screen.getByText('total emails').closest('.stat-card');
    expect(totalCard).toHaveTextContent('2');
    expect(screen.getByText('categories')).toBeInTheDocument();
    expect(screen.getByText('senders')).toBeInTheDocument();
    expect(screen.getByText('avg confidence')).toBeInTheDocument();
    expect(screen.getByText('unsub opportunities')).toBeInTheDocument();
  });

  it('hides avg confidence for inbox_scan', () => {
    // Arrange
    const emails = [mockEmail];

    // Act
    render(<InsightsTab emails={emails} isInboxScan={true} onCategoryClick={onCategoryClick} />);

    // Assert
    expect(screen.queryByText('avg confidence')).not.toBeInTheDocument();
  });

  it('renders chart titles', () => {
    // Arrange
    const emails = [mockEmail, mockEmail2];

    // Act
    render(<InsightsTab emails={emails} isInboxScan={false} onCategoryClick={onCategoryClick} />);

    // Assert
    expect(screen.getByText('emails by category')).toBeInTheDocument();
    expect(screen.getByText('top 10 senders')).toBeInTheDocument();
  });

  it('renders confidence distribution for AI analyses', () => {
    // Arrange
    const emails = [mockEmail, mockEmail2];

    // Act
    render(<InsightsTab emails={emails} isInboxScan={false} onCategoryClick={onCategoryClick} />);

    // Assert
    expect(screen.getByText('confidence distribution')).toBeInTheDocument();
  });

  it('hides confidence distribution for inbox_scan', () => {
    // Arrange
    const emails = [mockEmail, mockEmail2];

    // Act
    render(<InsightsTab emails={emails} isInboxScan={true} onCategoryClick={onCategoryClick} />);

    // Assert
    expect(screen.queryByText('confidence distribution')).not.toBeInTheDocument();
  });

  it('renders action breakdown when actions exist', () => {
    // Arrange
    const emailWithAction: ClassifiedEmail = { ...mockEmail, action_taken: 'keep' };

    // Act
    render(<InsightsTab emails={[emailWithAction]} isInboxScan={false} onCategoryClick={onCategoryClick} />);

    // Assert
    expect(screen.getByText('action breakdown')).toBeInTheDocument();
  });

  it('hides action breakdown when no actions taken', () => {
    // Arrange
    const emails = [mockEmail, mockEmail2]; // both have action_taken: null

    // Act
    render(<InsightsTab emails={emails} isInboxScan={false} onCategoryClick={onCategoryClick} />);

    // Assert
    expect(screen.queryByText('action breakdown')).not.toBeInTheDocument();
  });

  it('computes correct unsub opportunities count', () => {
    // Arrange — mockEmail2 has has_unsubscribe: true, mockEmail has false
    const emails = [mockEmail, mockEmail2];

    // Act
    render(<InsightsTab emails={emails} isInboxScan={false} onCategoryClick={onCategoryClick} />);

    // Assert
    const unsubCard = screen.getByText('unsub opportunities').closest('.stat-card');
    expect(unsubCard).toHaveTextContent('1');
  });
});
