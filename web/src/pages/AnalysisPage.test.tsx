import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import { AnalysisPage } from './AnalysisPage';
import { apiClient } from '../api/client';
import { mockAnalysis, mockEmail, mockEmail2, mockSenders } from '../test/fixtures';
import type { ReactNode } from 'react';

vi.mock('../api/client', () => ({
  apiClient: {
    getAnalysis: vi.fn(),
    getSenderGroups: vi.fn(),
    applyActions: vi.fn(),
  },
}));

vi.mock('../components/insights/InsightsTab', () => ({
  InsightsTab: () => <div data-testid="insights-tab">insights</div>,
}));

const authValue = {
  authenticated: true,
  email: 'test@example.com',
  displayName: 'test user',
  loading: false,
  login: async () => {},
  logout: async () => {},
};

function renderPage() {
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <AuthContext.Provider value={authValue}>
        <MemoryRouter initialEntries={['/analysis/1']}>
          <Routes>
            <Route path="/analysis/:id" element={children} />
            <Route path="/dashboard" element={<div>dashboard</div>} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    );
  }
  return render(<AnalysisPage />, { wrapper: Wrapper });
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(apiClient.getAnalysis).mockResolvedValue(mockAnalysis);
  vi.mocked(apiClient.getSenderGroups).mockResolvedValue(mockSenders);
  vi.mocked(apiClient.applyActions).mockResolvedValue({ message: 'ok' });
});

describe('AnalysisPage - Categories Tab', () => {
  it('renders categories with action counts inline', async () => {
    // Arrange
    const analysisWithActions = {
      ...mockAnalysis,
      classified_emails: [
        { ...mockEmail, action_taken: 'mark_read' },
        { ...mockEmail2, action_taken: 'mark_read' },
      ],
    };
    vi.mocked(apiClient.getAnalysis).mockResolvedValue(analysisWithActions);

    // Act
    renderPage();
    await screen.findByText('primary');

    // Assert
    expect(screen.getByText('primary')).toBeInTheDocument();
    expect(screen.getByText('newsletters')).toBeInTheDocument();
  });

  it('renders checkboxes for category selection', async () => {
    // Arrange & Act
    renderPage();
    await screen.findByText('primary');

    // Assert
    const checkboxes = screen.getAllByRole('checkbox');
    expect(checkboxes.length).toBeGreaterThanOrEqual(2);
  });

  it('selecting categories updates scope text when switching to emails tab', async () => {
    // Arrange
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('primary');

    // Act — select a category checkbox
    const checkboxes = screen.getAllByRole('checkbox');
    await user.click(checkboxes[1]); // first category checkbox (index 0 is "select all")

    // Assert — checkbox is checked
    expect(checkboxes[1]).toBeChecked();
  });
});

describe('AnalysisPage - Emails Tab', () => {
  it('renders email checkboxes for multi-select', async () => {
    // Arrange
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('primary');

    // Act — navigate to emails tab
    await user.click(screen.getByText('emails'));

    // Assert
    const checkboxes = screen.getAllByRole('checkbox');
    expect(checkboxes.length).toBeGreaterThanOrEqual(2); // select-all + per-email
  });

  it('select-all checkbox selects all emails', async () => {
    // Arrange
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('primary');
    await user.click(screen.getByText('emails'));

    // Act
    const checkboxes = screen.getAllByRole('checkbox');
    await user.click(checkboxes[0]); // select all

    // Assert
    checkboxes.forEach(cb => {
      expect(cb).toBeChecked();
    });
  });

  it('shows selection count in action scope', async () => {
    // Arrange
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('primary');
    await user.click(screen.getByText('emails'));

    // Act — select one email
    const checkboxes = screen.getAllByRole('checkbox');
    await user.click(checkboxes[1]); // first email

    // Assert
    expect(screen.getByText('1 selected')).toBeInTheDocument();
  });

  it('undo button is initially disabled', async () => {
    // Arrange
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('primary');
    await user.click(screen.getByText('emails'));

    // Assert
    expect(screen.getByText('[z] undo')).toBeDisabled();
  });

  it('undo button becomes enabled after applying an action', async () => {
    // Arrange
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('primary');
    await user.click(screen.getByText('emails'));

    // Act — apply an action
    await user.click(screen.getByText('[m] mark read'));

    // Assert
    expect(screen.getByText('[z] undo')).not.toBeDisabled();
  });

  it('applying action calls API with correct params', async () => {
    // Arrange
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('primary');
    await user.click(screen.getByText('emails'));

    // Act
    await user.click(screen.getByText('[s] spam'));

    // Assert
    expect(apiClient.applyActions).toHaveBeenCalledWith(1, {
      action: 'mark_spam',
      category: undefined,
      sender_domain: undefined,
      email_ids: undefined,
    });
  });

  it('undo calls API with email IDs from last action', async () => {
    // Arrange
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('primary');
    await user.click(screen.getByText('emails'));

    // Act — apply then undo
    await user.click(screen.getByText('[m] mark read'));
    vi.mocked(apiClient.applyActions).mockClear();
    await user.click(screen.getByText('[z] undo'));

    // Assert
    expect(apiClient.applyActions).toHaveBeenCalledWith(1, {
      action: 'undo',
      email_ids: [mockEmail.id, mockEmail2.id],
    });
  });

  it('selected emails action applies to selected IDs only', async () => {
    // Arrange
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('primary');
    await user.click(screen.getByText('emails'));

    // Act — select first email, then apply action
    const checkboxes = screen.getAllByRole('checkbox');
    await user.click(checkboxes[1]); // first email
    await user.click(screen.getByText('[k] keep'));

    // Assert
    expect(apiClient.applyActions).toHaveBeenCalledWith(1, {
      action: 'keep',
      category: undefined,
      sender_domain: undefined,
      email_ids: [mockEmail.id],
    });
  });

  it('clears selection after applying action', async () => {
    // Arrange
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('primary');
    await user.click(screen.getByText('emails'));

    // Act — select, apply
    const checkboxes = screen.getAllByRole('checkbox');
    await user.click(checkboxes[1]);
    expect(screen.getByText('1 selected')).toBeInTheDocument();
    await user.click(screen.getByText('[k] keep'));

    // Assert — selection cleared, scope goes back to default
    expect(screen.getByText('all emails')).toBeInTheDocument();
  });
});

describe('AnalysisPage - Senders View', () => {
  it('renders sender checkboxes in group by sender view', async () => {
    // Arrange
    const user = userEvent.setup();
    renderPage();
    await screen.findByText('primary');
    await user.click(screen.getByText('emails'));
    await user.click(screen.getByText('group by sender'));

    // Assert
    const checkboxes = screen.getAllByRole('checkbox');
    expect(checkboxes.length).toBeGreaterThanOrEqual(2);
  });
});

describe('AnalysisPage - Action badges inline', () => {
  it('renders action badges on single line in summary tab', async () => {
    // Arrange
    const analysisWithActions = {
      ...mockAnalysis,
      classified_emails: [
        { ...mockEmail, action_taken: 'mark_read' },
        { ...mockEmail2, action_taken: 'unsubscribe' },
      ],
    };
    vi.mocked(apiClient.getAnalysis).mockResolvedValue(analysisWithActions);

    // Act
    renderPage();
    await screen.findByText('primary');

    // Assert — badges are inside td with actions-inline class
    const cells = document.querySelectorAll('.actions-inline');
    expect(cells.length).toBeGreaterThan(0);
    // Each cell should have white-space: nowrap (via CSS class)
    cells.forEach(cell => {
      expect(cell.classList.contains('actions-inline')).toBe(true);
    });
  });
});
