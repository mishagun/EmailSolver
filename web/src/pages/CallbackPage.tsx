import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export function CallbackPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { login } = useAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = searchParams.get('token');
    if (!token) {
      setError('no token received from authentication');
      return;
    }
    login(token)
      .then(() => navigate('/dashboard', { replace: true }))
      .catch(() => setError('failed to validate token'));
  }, [searchParams, login, navigate]);

  return (
    <div
      className="container"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
      }}
    >
      {error ? (
        <div style={{ textAlign: 'center' }}>
          <div className="error-text mb-16">{error}</div>
          <button onClick={() => navigate('/login')}>back to login</button>
        </div>
      ) : (
        <span className="muted">authenticating...</span>
      )}
    </div>
  );
}
