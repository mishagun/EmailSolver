import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { AuthProvider } from './context/AuthContext';
import { useAuth } from './hooks/useAuth';
import { AnalysisPage } from './pages/AnalysisPage';
import { CallbackPage } from './pages/CallbackPage';
import { DashboardPage } from './pages/DashboardPage';
import { LoginPage } from './pages/LoginPage';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { authenticated, loading } = useAuth();

  if (loading) {
    return <div className="empty-state">loading...</div>;
  }

  if (!authenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/callback" element={<CallbackPage />} />
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/analysis/:id" element={<AnalysisPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
