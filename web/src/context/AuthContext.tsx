import { createContext, useCallback, useEffect, useState, type ReactNode } from 'react';
import { apiClient, ApiError } from '../api/client';

interface AuthState {
  authenticated: boolean;
  email: string | null;
  displayName: string | null;
  loading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (token: string) => Promise<void>;
  logout: () => Promise<void>;
}

const TOKEN_KEY = 'emailsolver_token';

export const AuthContext = createContext<AuthContextValue>({
  authenticated: false,
  email: null,
  displayName: null,
  loading: true,
  login: async () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    authenticated: false,
    email: null,
    displayName: null,
    loading: true,
  });

  const validate = useCallback(async (token: string) => {
    apiClient.setToken(token);
    try {
      const status = await apiClient.getAuthStatus();
      setState({
        authenticated: true,
        email: status.email,
        displayName: status.display_name,
        loading: false,
      });
    } catch (err) {
      apiClient.clearToken();
      localStorage.removeItem(TOKEN_KEY);
      setState({ authenticated: false, email: null, displayName: null, loading: false });
      if (err instanceof ApiError && err.statusCode === 401) {
        return;
      }
      throw err;
    }
  }, []);

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
      validate(token).catch(() => {});
    } else {
      setState(prev => ({ ...prev, loading: false }));
    }
  }, [validate]);

  const login = useCallback(async (token: string) => {
    localStorage.setItem(TOKEN_KEY, token);
    await validate(token);
  }, [validate]);

  const logout = useCallback(async () => {
    try {
      await apiClient.logout();
    } catch {
      // ignore logout errors
    }
    apiClient.clearToken();
    localStorage.removeItem(TOKEN_KEY);
    setState({ authenticated: false, email: null, displayName: null, loading: false });
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
