import { Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export function Layout() {
  const { email, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="container">
      <header className="flex-between" style={{ padding: '16px 0', borderBottom: 'var(--border)' }}>
        <span style={{ fontWeight: 700, fontSize: 18 }}>emailsolver</span>
        <div className="flex gap-16" style={{ alignItems: 'center' }}>
          {email && <span className="muted">{email}</span>}
          <button onClick={handleLogout}>logout</button>
        </div>
      </header>
      <main className="page">
        <Outlet />
      </main>
      <footer className="flex-between muted" style={{ padding: '16px 0', borderTop: 'var(--border)', fontSize: 12 }}>
        <span>developed by mike feldman</span>
        <div className="flex gap-16">
          <a href="https://www.linkedin.com/in/mikhail-feldman/" target="_blank" rel="noopener noreferrer" style={{ color: 'inherit' }}>linkedin</a>
          <a href="https://github.com/mishagun" target="_blank" rel="noopener noreferrer" style={{ color: 'inherit' }}>github</a>
        </div>
      </footer>
    </div>
  );
}
