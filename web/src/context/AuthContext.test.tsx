import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import { AuthProvider } from './AuthContext';
import { useAuth } from '../hooks/useAuth';

const mockFetch = vi.fn();

function TestConsumer() {
  const { authenticated, email, loading, logout } = useAuth();
  return (
    <div>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="auth">{String(authenticated)}</span>
      <span data-testid="email">{email ?? 'none'}</span>
      <button onClick={logout}>logout</button>
    </div>
  );
}

describe('AuthContext', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', mockFetch);
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('starts unauthenticated when no token in localStorage', async () => {
    // Arrange & Act
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    // Assert
    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('false');
    });
    expect(screen.getByTestId('auth').textContent).toBe('false');
    expect(screen.getByTestId('email').textContent).toBe('none');
  });

  it('validates token from localStorage on mount', async () => {
    // Arrange
    localStorage.setItem('tidyinbox_token', 'stored-jwt');
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ authenticated: true, email: 'user@test.com', display_name: 'user' }),
    });

    // Act
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    // Assert
    await waitFor(() => {
      expect(screen.getByTestId('auth').textContent).toBe('true');
    });
    expect(screen.getByTestId('email').textContent).toBe('user@test.com');
  });

  it('clears state on 401 from stored token', async () => {
    // Arrange
    localStorage.setItem('tidyinbox_token', 'expired-jwt');
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
      json: async () => ({ detail: 'invalid token' }),
    });

    // Act
    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    // Assert
    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('false');
    });
    expect(screen.getByTestId('auth').textContent).toBe('false');
    expect(localStorage.getItem('tidyinbox_token')).toBeNull();
  });

  it('clears state on logout', async () => {
    // Arrange
    localStorage.setItem('tidyinbox_token', 'valid-jwt');
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ authenticated: true, email: 'user@test.com', display_name: 'user' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: 'logged out' }),
      });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth').textContent).toBe('true');
    });

    // Act
    await act(async () => {
      screen.getByText('logout').click();
    });

    // Assert
    await waitFor(() => {
      expect(screen.getByTestId('auth').textContent).toBe('false');
    });
    expect(localStorage.getItem('tidyinbox_token')).toBeNull();
  });
});
