import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import { CallbackPage } from './CallbackPage';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('CallbackPage', () => {
  const defaultAuth = {
    authenticated: false,
    email: null,
    displayName: null,
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
  };

  it('shows error when no token in URL', async () => {
    // Arrange & Act
    render(
      <AuthContext.Provider value={defaultAuth}>
        <MemoryRouter initialEntries={['/callback']}>
          <Routes>
            <Route path="/callback" element={<CallbackPage />} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    );

    // Assert
    await waitFor(() => {
      expect(screen.getByText('no token received from authentication')).toBeInTheDocument();
    });
  });

  it('calls login and navigates on valid token', async () => {
    // Arrange
    const login = vi.fn().mockResolvedValue(undefined);

    render(
      <AuthContext.Provider value={{ ...defaultAuth, login }}>
        <MemoryRouter initialEntries={['/callback?token=abc123']}>
          <Routes>
            <Route path="/callback" element={<CallbackPage />} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    );

    // Assert
    await waitFor(() => {
      expect(login).toHaveBeenCalledWith('abc123');
    });
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard', { replace: true });
    });
  });

  it('shows error when login fails', async () => {
    // Arrange
    const login = vi.fn().mockRejectedValue(new Error('bad token'));

    render(
      <AuthContext.Provider value={{ ...defaultAuth, login }}>
        <MemoryRouter initialEntries={['/callback?token=bad']}>
          <Routes>
            <Route path="/callback" element={<CallbackPage />} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    );

    // Assert
    await waitFor(() => {
      expect(screen.getByText('failed to validate token')).toBeInTheDocument();
    });
  });
});
