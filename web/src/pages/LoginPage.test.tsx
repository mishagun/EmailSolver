import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LoginPage } from './LoginPage';
import { MemoryRouter } from 'react-router-dom';

describe('LoginPage', () => {
  it('renders app name and subtitle', () => {
    // Arrange & Act
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    // Assert
    expect(screen.getByText('emailsolver')).toBeInTheDocument();
    expect(screen.getByText('ai-powered email classification and management')).toBeInTheDocument();
  });

  it('renders login button', () => {
    // Arrange & Act
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    // Assert
    expect(screen.getByText('login with google')).toBeInTheDocument();
  });

  it('redirects to api login url on click', async () => {
    // Arrange
    const user = userEvent.setup();
    const mockAssign = vi.fn();
    Object.defineProperty(window, 'location', {
      value: { href: '', set href(v: string) { mockAssign(v); } },
      writable: true,
      configurable: true,
    });

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    // Act
    await user.click(screen.getByText('login with google'));

    // Assert
    expect(mockAssign).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/auth/login')
    );
  });
});
