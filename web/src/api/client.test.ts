import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ApiError, apiClient } from './client';

describe('EmailSolverClient', () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    mockFetch.mockReset();
    vi.stubGlobal('fetch', mockFetch);
    apiClient.clearToken();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('getLoginUrl', () => {
    it('constructs login url with redirect', () => {
      // Arrange
      const redirectUrl = 'http://localhost:5173/callback';

      // Act
      const url = apiClient.getLoginUrl(redirectUrl);

      // Assert
      expect(url).toContain('/api/v1/auth/login');
      expect(url).toContain('redirect_url=' + encodeURIComponent(redirectUrl));
    });
  });

  describe('setToken / clearToken', () => {
    it('includes authorization header after setToken', async () => {
      // Arrange
      apiClient.setToken('test-jwt');
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ authenticated: true, email: 'a@b.com', display_name: null }),
      });

      // Act
      await apiClient.getAuthStatus();

      // Assert
      const headers = mockFetch.mock.calls[0][1].headers;
      expect(headers['Authorization']).toBe('Bearer test-jwt');
    });

    it('omits authorization header after clearToken', async () => {
      // Arrange
      apiClient.setToken('test-jwt');
      apiClient.clearToken();
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ authenticated: true, email: 'a@b.com', display_name: null }),
      });

      // Act
      await apiClient.getAuthStatus();

      // Assert
      const headers = mockFetch.mock.calls[0][1].headers;
      expect(headers['Authorization']).toBeUndefined();
    });
  });

  describe('request error handling', () => {
    it('throws ApiError with detail from JSON response', async () => {
      // Arrange
      apiClient.setToken('token');
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        json: async () => ({ detail: 'invalid token' }),
      });

      // Act & Assert
      await expect(apiClient.getAuthStatus()).rejects.toThrow(ApiError);
    });

    it('throws ApiError with statusText when JSON parse fails', async () => {
      // Arrange
      apiClient.setToken('token');
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        json: async () => { throw new Error('not json'); },
      });

      // Act & Assert
      await expect(apiClient.getAuthStatus()).rejects.toMatchObject({
        statusCode: 500,
        detail: 'Internal Server Error',
      });
    });
  });

  describe('getAuthStatus', () => {
    it('calls GET /api/v1/auth/status', async () => {
      // Arrange
      apiClient.setToken('token');
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ authenticated: true, email: 'user@test.com', display_name: 'test' }),
      });

      // Act
      const result = await apiClient.getAuthStatus();

      // Assert
      expect(mockFetch).toHaveBeenCalledOnce();
      expect(mockFetch.mock.calls[0][0]).toContain('/api/v1/auth/status');
      expect(result.email).toBe('user@test.com');
    });
  });

  describe('createAnalysis', () => {
    it('sends POST with request body', async () => {
      // Arrange
      apiClient.setToken('token');
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: 1, status: 'pending', query: 'is:unread',
          total_emails: null, processed_emails: null, error_message: null,
          created_at: '2026-01-01T00:00:00Z', completed_at: null,
          summary: null, classified_emails: null,
        }),
      });

      // Act
      const result = await apiClient.createAnalysis({
        query: 'is:unread',
        max_emails: 50,
      });

      // Assert
      expect(mockFetch.mock.calls[0][1].method).toBe('POST');
      expect(mockFetch.mock.calls[0][1].body).toBe(JSON.stringify({ query: 'is:unread', max_emails: 50 }));
      expect(result.id).toBe(1);
    });
  });

  describe('applyActions', () => {
    it('sends POST to correct analysis path', async () => {
      // Arrange
      apiClient.setToken('token');
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: 'ok' }),
      });

      // Act
      await apiClient.applyActions(42, { action: 'keep', email_ids: [1, 2] });

      // Assert
      expect(mockFetch.mock.calls[0][0]).toContain('/api/v1/analysis/42/apply');
      expect(mockFetch.mock.calls[0][1].body).toBe(JSON.stringify({ action: 'keep', email_ids: [1, 2] }));
    });
  });

  describe('getSenderGroups', () => {
    it('includes category as query param when provided', async () => {
      // Arrange
      apiClient.setToken('token');
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ([]),
      });

      // Act
      await apiClient.getSenderGroups(1, 'newsletters');

      // Assert
      expect(mockFetch.mock.calls[0][0]).toContain('category=newsletters');
    });

    it('omits query params when no category', async () => {
      // Arrange
      apiClient.setToken('token');
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ([]),
      });

      // Act
      await apiClient.getSenderGroups(1);

      // Assert
      expect(mockFetch.mock.calls[0][0]).not.toContain('?');
    });
  });

  describe('deleteAnalysis', () => {
    it('sends DELETE to correct path', async () => {
      // Arrange
      apiClient.setToken('token');
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: 'deleted' }),
      });

      // Act
      await apiClient.deleteAnalysis(5);

      // Assert
      expect(mockFetch.mock.calls[0][0]).toContain('/api/v1/analysis/5');
      expect(mockFetch.mock.calls[0][1].method).toBe('DELETE');
    });
  });
});
