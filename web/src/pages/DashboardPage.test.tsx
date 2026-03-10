import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DashboardPage } from './DashboardPage';
import { renderWithProviders } from '../test/test-utils';
import { mockAnalysis } from '../test/fixtures';

const mockFetch = vi.fn();
const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', mockFetch);
    mockFetch.mockReset();
    mockNavigate.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function mockApiResponses() {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ unread_count: 42, total_count: 500 }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ analyses: [mockAnalysis], total: 1 }),
      });
  }

  it('shows loading state initially', () => {
    // Arrange
    mockFetch.mockReturnValue(new Promise(() => {}));

    // Act
    renderWithProviders(<DashboardPage />);

    // Assert
    expect(screen.getByText('loading...')).toBeInTheDocument();
  });

  it('displays email stats', async () => {
    // Arrange
    mockApiResponses();

    // Act
    renderWithProviders(<DashboardPage />);

    // Assert
    await waitFor(() => {
      expect(screen.getByText('unread: 42')).toBeInTheDocument();
    });
    expect(screen.getByText('total: 500')).toBeInTheDocument();
  });

  it('displays analyses in table', async () => {
    // Arrange
    mockApiResponses();

    // Act
    renderWithProviders(<DashboardPage />);

    // Assert
    await waitFor(() => {
      expect(screen.getByText('#1')).toBeInTheDocument();
    });
    expect(screen.getByText('is:unread')).toBeInTheDocument();
  });

  it('shows empty state when no analyses', async () => {
    // Arrange
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ unread_count: 0, total_count: 0 }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ analyses: [], total: 0 }),
      });

    // Act
    renderWithProviders(<DashboardPage />);

    // Assert
    await waitFor(() => {
      expect(screen.getByText('no analyses yet')).toBeInTheDocument();
    });
  });

  it('navigates to analysis on row click', async () => {
    // Arrange
    const user = userEvent.setup();
    mockApiResponses();
    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('#1')).toBeInTheDocument();
    });

    // Act
    await user.click(screen.getByText('#1'));

    // Assert
    expect(mockNavigate).toHaveBeenCalledWith('/analysis/1');
  });

  it('creates analysis and navigates on submit', async () => {
    // Arrange
    const user = userEvent.setup();
    mockApiResponses();
    renderWithProviders(<DashboardPage />);

    await waitFor(() => {
      expect(screen.getByText('start ai analysis')).toBeInTheDocument();
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: 5, analysis_type: 'ai', status: 'pending', query: 'is:unread',
        total_emails: null, processed_emails: null, error_message: null,
        created_at: '2026-01-01T00:00:00Z', completed_at: null,
        summary: null, classified_emails: null,
      }),
    });

    // Act
    await user.click(screen.getByText('start ai analysis'));

    // Assert
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/analysis/5');
    });
  });
});
