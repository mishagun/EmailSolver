import { apiClient } from '../api/client';

const WEB_BASE = import.meta.env.VITE_WEB_BASE_URL || 'http://localhost:5173';

export function LoginPage() {
  const handleLogin = () => {
    window.location.href = apiClient.getLoginUrl(`${WEB_BASE}/callback`);
  };

  return (
    <div
      className="container"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        gap: 24,
      }}
    >
      <div className="animate-in stagger-1" style={{ fontWeight: 700, fontSize: 48, letterSpacing: -2 }}>
        tidyinbox
      </div>
      <div className="animate-in stagger-2 muted" style={{ fontSize: 16, marginBottom: 32 }}>
        ai-powered email classification and management
      </div>
      <button className="animate-in stagger-3 primary" onClick={handleLogin} style={{ padding: '12px 32px', fontSize: 16 }}>
        login with google
      </button>
    </div>
  );
}
