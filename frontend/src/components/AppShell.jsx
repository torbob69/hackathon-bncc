import { useState, useEffect } from 'react';
import { notificationsAPI } from '../api/client';
import { formatDateTime } from './ui';

const ROLE_LABELS = {
  farmer: 'Petani',
  manager: 'Manajer',
  admin: 'Admin',
  distributor: 'Distributor',
  financing_partner: 'Mitra Keuangan',
  platform_admin: 'Platform Admin',
};

const ROLE_COLORS = {
  farmer:            'var(--role-farmer)',
  manager:           'var(--role-manager)',
  admin:             'var(--role-admin)',
  distributor:       'var(--role-distributor)',
  financing_partner: 'var(--role-financing)',
  platform_admin:    'var(--role-platform)',
};

function initials(name) {
  if (!name) return '?';
  return name.split(' ').slice(0, 2).map((w) => w[0]).join('').toUpperCase();
}

function BellIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

function LogoutIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" width="15" height="15">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

function MenuIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="20" height="20">
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  );
}

function NotifPanel({ onClose }) {
  const [notifs, setNotifs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    notificationsAPI.list()
      .then((r) => setNotifs(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const markAll = async () => {
    await notificationsAPI.markAllRead().catch(() => {});
    setNotifs((prev) => prev.map((n) => ({ ...n, is_read: true })));
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 'var(--topbar-h)',
        right: 16,
        width: 340,
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        boxShadow: 'var(--shadow-lg)',
        zIndex: 'var(--z-dropdown)',
        overflow: 'hidden',
        animation: 'slide-up 150ms ease-out',
      }}
    >
      <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontWeight: 700, fontSize: '0.9375rem', color: 'var(--ink)' }}>Notifikasi</span>
        <button className="btn btn-ghost btn-xs" onClick={markAll}>Tandai semua</button>
      </div>
      <div style={{ maxHeight: 360, overflowY: 'auto' }}>
        {loading ? (
          <div style={{ padding: 24, textAlign: 'center' }}><div className="spinner" style={{ margin: '0 auto' }} /></div>
        ) : notifs.length === 0 ? (
          <div style={{ padding: '32px 16px', textAlign: 'center', color: 'var(--muted)', fontSize: '0.875rem' }}>Tidak ada notifikasi</div>
        ) : (
          notifs.map((n) => (
            <div
              key={n.id}
              style={{
                padding: '12px 16px',
                borderBottom: '1px solid var(--border-subtle)',
                background: n.is_read ? 'transparent' : 'var(--primary-subtle)',
              }}
            >
              <div style={{ fontSize: '0.875rem', color: 'var(--ink)', fontWeight: n.is_read ? 400 : 600 }}>{n.message}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--muted)', marginTop: 3, fontFamily: 'var(--font-mono)' }}>{formatDateTime(n.created_at)}</div>
            </div>
          ))
        )}
      </div>
      <div style={{ padding: '10px 16px', borderTop: '1px solid var(--border)' }}>
        <button className="btn btn-ghost btn-sm" style={{ width: '100%', justifyContent: 'center' }} onClick={onClose}>Tutup</button>
      </div>
    </div>
  );
}

export default function AppShell({ user, onLogout, navItems, topbarTitle, children }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showNotif, setShowNotif] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const roleColor = ROLE_COLORS[user?.role] || 'var(--primary)';

  useEffect(() => {
    const fetchCount = () => {
      notificationsAPI.unreadCount()
        .then((r) => setUnreadCount(r.data.unread || 0))
        .catch(() => {});
    };
    fetchCount();
    const interval = setInterval(fetchCount, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="app-shell">
      {/* Overlay for mobile */}
      {sidebarOpen && (
        <div
          style={{ position: 'fixed', inset: 0, background: 'oklch(0 0 0 / 0.3)', zIndex: 'calc(var(--z-modal) - 1)' }}
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <nav className={`sidebar ${sidebarOpen ? 'open' : ''}`} aria-label="Sidebar navigation">
        <div className="sidebar-logo">
          <div className="sidebar-logo-mark">KL</div>
          <div>
            <div className="sidebar-logo-name">KOPERALINK</div>
            <div className="sidebar-logo-sub">Platform Koperasi Tani</div>
          </div>
        </div>

        <div className="sidebar-nav">
          {navItems.map((item) =>
            item.type === 'section' ? (
              <div key={item.label} className="nav-section-label">{item.label}</div>
            ) : (
              <button
                key={item.id}
                id={`nav-${item.id}`}
                className={`nav-item ${item.active ? 'active' : ''}`}
                onClick={() => { item.onClick?.(); setSidebarOpen(false); }}
                aria-current={item.active ? 'page' : undefined}
              >
                <span className="nav-icon">{item.icon}</span>
                <span style={{ flex: 1 }}>{item.label}</span>
                {item.badge > 0 && <span className="nav-badge">{item.badge}</span>}
              </button>
            )
          )}
        </div>

        <div className="sidebar-footer">
          <div className="user-card" onClick={onLogout} role="button" tabIndex={0} title="Logout"
            onKeyDown={(e) => e.key === 'Enter' && onLogout()}>
            <div className="user-avatar" style={{ background: roleColor }}>
              {initials(user?.name)}
            </div>
            <div className="user-info">
              <div className="user-name">{user?.name || '—'}</div>
              <div className="user-role">{ROLE_LABELS[user?.role] || user?.role}</div>
            </div>
            <LogoutIcon />
          </div>
        </div>
      </nav>

      {/* Main content */}
      <div className="main-content">
        <header className="topbar" role="banner">
          <button
            className="btn btn-ghost btn-icon"
            style={{ display: 'none' }}
            id="sidebar-toggle"
            aria-label="Toggle sidebar"
            onClick={() => setSidebarOpen((v) => !v)}
          >
            <MenuIcon />
          </button>
          <span className="topbar-title">{topbarTitle}</span>
          <div className="topbar-actions">
            <div style={{ position: 'relative' }}>
              <button
                className="notif-bell"
                id="notif-bell-btn"
                aria-label={`Notifikasi${unreadCount > 0 ? `, ${unreadCount} belum dibaca` : ''}`}
                onClick={() => setShowNotif((v) => !v)}
              >
                <BellIcon />
                {unreadCount > 0 && <span className="notif-dot" aria-hidden="true" />}
              </button>
              {showNotif && <NotifPanel onClose={() => setShowNotif(false)} />}
            </div>
          </div>
        </header>

        <main className="page-body" id="main-content">
          {children}
        </main>
      </div>

      <style>{`
        @media (max-width: 768px) {
          #sidebar-toggle { display: flex !important; }
        }
      `}</style>
    </div>
  );
}
