import { Component } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "./index.css";
import { useAuth } from "./hooks/useAuth";
import { ToastProvider } from "./hooks/useToast.jsx";

import LoginPage from "./pages/Login";
import ActivatePage from "./pages/Activate";
import FarmerDashboard from "./pages/Farmer";
import ManagerDashboard from "./pages/Manager";
import AdminDashboard from "./pages/Admin";
import FinancingDashboard from "./pages/Financing";
import PlatformDashboard from "./pages/Platform";
import DistributorDashboard from "./pages/Distributor";

import RequireRole from "./guards/RequireRole";

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) {
    return { error };
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 32, fontFamily: 'monospace', background: '#fff1f0', minHeight: '100dvh' }}>
          <div style={{ fontWeight: 700, fontSize: '1.125rem', color: '#cf1322', marginBottom: 12 }}>
            Terjadi kesalahan rendering
          </div>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.8125rem', color: '#555', background: '#fff', padding: 16, borderRadius: 8, border: '1px solid #ffa39e' }}>
            {this.state.error?.message}
            {'\n\n'}
            {this.state.error?.stack}
          </pre>
          <button
            style={{ marginTop: 16, padding: '8px 20px', background: '#1677ff', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontWeight: 600 }}
            onClick={() => this.setState({ error: null })}
          >
            Coba lagi
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function LoadingScreen() {
  return (
    <div style={{
      display: 'flex',
      height: '100dvh',
      alignItems: 'center',
      justifyContent: 'center',
      flexDirection: 'column',
      gap: 16,
      background: 'var(--bg)',
    }}>
      <div style={{
        width: 48,
        height: 48,
        background: 'var(--primary)',
        borderRadius: 12,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontWeight: 900,
        fontSize: '1.25rem',
        color: 'white',
        letterSpacing: '-0.03em',
      }}>
        KL
      </div>
      <div className="spinner spinner-lg" aria-label="Memuat..." />
    </div>
  );
}

function AppContent() {
  const { user, loading, login, logout } = useAuth();

  if (loading) return <LoadingScreen />;

  const getDashboardPath = (role) => {
    if (role === 'distributor') return '/marketplace';
    if (role === 'platform_admin') return '/app/platform';
    if (role === 'financing_partner') return '/app/financing';
    return `/app/${role}`;
  };

  return (
    <Routes>
      {/* Public routes */}
      <Route
        path="/"
        element={user ? <Navigate to={getDashboardPath(user.role)} replace /> : <LoginPage onLogin={login} />}
      />
      <Route path="/activate" element={<ActivatePage />} />

      {/* Farmer */}
      <Route
        path="/app/farmer/*"
        element={
          <RequireRole user={user} allowedRoles={['farmer']}>
            <FarmerDashboard user={user} onLogout={logout} />
          </RequireRole>
        }
      />

      {/* Manager */}
      <Route
        path="/app/manager/*"
        element={
          <RequireRole user={user} allowedRoles={['manager']}>
            <ManagerDashboard user={user} onLogout={logout} />
          </RequireRole>
        }
      />

      {/* Admin */}
      <Route
        path="/app/admin/*"
        element={
          <RequireRole user={user} allowedRoles={['admin']}>
            <AdminDashboard user={user} onLogout={logout} />
          </RequireRole>
        }
      />

      {/* Financing Partner */}
      <Route
        path="/app/financing/*"
        element={
          <RequireRole user={user} allowedRoles={['financing_partner']}>
            <FinancingDashboard user={user} onLogout={logout} />
          </RequireRole>
        }
      />

      {/* Platform Admin */}
      <Route
        path="/app/platform/*"
        element={
          <RequireRole user={user} allowedRoles={['platform_admin']}>
            <PlatformDashboard user={user} onLogout={logout} />
          </RequireRole>
        }
      />

      {/* Distributor / Marketplace */}
      <Route
        path="/marketplace/*"
        element={
          <RequireRole user={user} allowedRoles={['distributor']}>
            <DistributorDashboard user={user} onLogout={logout} />
          </RequireRole>
        }
      />

      {/* Catch-all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <ToastProvider>
          <ErrorBoundary>
            <AppContent />
          </ErrorBoundary>
        </ToastProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
