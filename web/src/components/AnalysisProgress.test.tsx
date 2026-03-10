import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AnalysisProgress } from './AnalysisProgress';

describe('AnalysisProgress', () => {
  it('renders progress text with counts and percentage', () => {
    // Arrange & Act
    render(<AnalysisProgress processed={25} total={50} />);

    // Assert
    expect(screen.getByText('25 / 50 (50%)')).toBeInTheDocument();
  });

  it('shows 0% when total is 0', () => {
    // Arrange & Act
    render(<AnalysisProgress processed={0} total={0} />);

    // Assert
    expect(screen.getByText('0 / 0 (0%)')).toBeInTheDocument();
  });

  it('renders progress fill bar with correct width', () => {
    // Arrange & Act
    const { container } = render(<AnalysisProgress processed={75} total={100} />);

    // Assert
    const fill = container.querySelector('.progress-fill') as HTMLElement;
    expect(fill.style.width).toBe('75%');
  });
});
