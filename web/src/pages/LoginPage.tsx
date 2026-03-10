import { apiClient } from '../api/client';

const WEB_BASE = import.meta.env.VITE_WEB_BASE_URL || 'http://localhost:5173';

const features = [
  { label: 'scan', description: 'reads your inbox and extracts sender, subject, and metadata' },
  { label: 'classify', description: 'ai sorts emails into categories — promotions, newsletters, social, receipts, and more' },
  { label: 'act', description: 'bulk mark as read, move to category, mark spam, or unsubscribe — one click' },
  { label: 'undo', description: 'every action is reversible with full action history' },
];

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
        padding: '0 16px',
        gap: 24,
      }}
    >
      <div className="animate-in stagger-1" style={{ fontWeight: 700, fontSize: 48, letterSpacing: -2 }}>
        tidyinbox
      </div>
      <div className="animate-in stagger-2 muted" style={{ fontSize: 16 }}>
        ai-powered email classification and management
      </div>

      <div
        className="animate-in stagger-3"
        style={{
          display: 'grid',
          gridTemplateColumns: 'auto 1fr',
          gap: '8px 16px',
          maxWidth: 480,
          width: '100%',
          margin: '16px 0',
          fontSize: 14,
        }}
      >
        {features.map((f) => (
          <div key={f.label} style={{ display: 'contents' }}>
            <span style={{ fontWeight: 700 }}>{f.label}</span>
            <span className="muted">{f.description}</span>
          </div>
        ))}
      </div>

      <button className="animate-in stagger-4 primary" onClick={handleLogin} style={{ padding: '12px 32px', fontSize: 16 }}>
        login with google
      </button>

      <div className="animate-in stagger-5 muted" style={{ marginTop: 64, fontSize: 12, display: 'flex', gap: 32 }}>
        <span>mike feldman</span>
        <a href="https://www.linkedin.com/in/mikhail-feldman/" target="_blank" rel="noopener noreferrer" style={{ color: 'inherit' }}>linkedin</a>
        <a href="https://github.com/mishagun" target="_blank" rel="noopener noreferrer" style={{ color: 'inherit' }}>github</a>
      </div>
    </div>
  );
}
