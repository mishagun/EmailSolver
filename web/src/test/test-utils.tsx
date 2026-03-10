import { render, type RenderOptions } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { ReactElement, ReactNode } from 'react';
import { AuthContext } from '../context/AuthContext';

interface AuthOverrides {
  authenticated?: boolean;
  email?: string | null;
  displayName?: string | null;
  loading?: boolean;
  login?: (token: string) => Promise<void>;
  logout?: () => Promise<void>;
}

interface WrapperOptions {
  route?: string;
  auth?: AuthOverrides;
}

function createWrapper({ route = '/', auth = {} }: WrapperOptions = {}) {
  const authValue = {
    authenticated: auth.authenticated ?? true,
    email: auth.email ?? 'test@example.com',
    displayName: auth.displayName ?? 'test user',
    loading: auth.loading ?? false,
    login: auth.login ?? (async () => {}),
    logout: auth.logout ?? (async () => {}),
  };

  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <AuthContext.Provider value={authValue}>
        <MemoryRouter initialEntries={[route]}>
          {children}
        </MemoryRouter>
      </AuthContext.Provider>
    );
  };
}

export function renderWithProviders(
  ui: ReactElement,
  options?: WrapperOptions & Omit<RenderOptions, 'wrapper'>,
) {
  const { route, auth, ...renderOptions } = options ?? {};
  return render(ui, { wrapper: createWrapper({ route, auth }), ...renderOptions });
}
