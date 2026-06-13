// Shared utility components for KOPERALINK

// ─── Money display ─────────────────────────────────────────────────────────
export function Money({ value, colored = false, prefix = 'Rp' }) {
  const num = parseFloat(value) || 0;
  const formatted = new Intl.NumberFormat('id-ID', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(num);
  const cls = colored
    ? num >= 0 ? 'money money-green' : 'money money-red'
    : 'money';
  return <span className={cls}>{prefix} {formatted}</span>;
}

// ─── Status Badge ──────────────────────────────────────────────────────────
const STATUS_MAP = {
  pending:    { label: 'Pending',    cls: 'badge-pending' },
  confirmed:  { label: 'Dikonfirmasi', cls: 'badge-confirmed' },
  active:     { label: 'Aktif',      cls: 'badge-active' },
  rejected:   { label: 'Ditolak',   cls: 'badge-rejected' },
  cancelled:  { label: 'Dibatalkan', cls: 'badge-cancelled' },
  paid:       { label: 'Lunas',      cls: 'badge-paid' },
  fulfilled:  { label: 'Terpenuhi', cls: 'badge-fulfilled' },
  past_due:   { label: 'Terlambat', cls: 'badge-past_due' },
  seized:     { label: 'Disita',     cls: 'badge-seized' },
  revoked:    { label: 'Dicabut',    cls: 'badge-revoked' },
  pending_activation: { label: 'Menunggu Aktivasi', cls: 'badge-pending' },
};

export function StatusBadge({ status }) {
  const info = STATUS_MAP[status] || { label: status, cls: 'badge-default' };
  return <span className={`badge ${info.cls}`}>{info.label}</span>;
}

// ─── Date/time formatting ─────────────────────────────────────────────────
export function formatDate(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('id-ID', {
    day: '2-digit', month: 'short', year: 'numeric',
  });
}

export function formatDateTime(dateStr) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleString('id-ID', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

// ─── Weight display ───────────────────────────────────────────────────────
export function Weight({ value }) {
  const kg = parseFloat(value) || 0;
  return <span>{kg.toLocaleString('id-ID', { maximumFractionDigits: 3 })} kg</span>;
}

// ─── Spinner ─────────────────────────────────────────────────────────────
export function Spinner({ large = false }) {
  return <div className={`spinner ${large ? 'spinner-lg' : ''}`} aria-label="Loading" />;
}

// ─── Empty state ─────────────────────────────────────────────────────────
export function EmptyState({ icon, title, desc, action }) {
  return (
    <div className="empty-state">
      {icon && (
        <div className="empty-state-icon">
          {icon}
        </div>
      )}
      <h3>{title || 'Tidak ada data'}</h3>
      {desc && <p>{desc}</p>}
      {action}
    </div>
  );
}

// ─── Page header ─────────────────────────────────────────────────────────
export function PageHeader({ title, desc, actions }) {
  return (
    <div className="page-header">
      <div className="page-header-left">
        <div className="page-title">{title}</div>
        {desc && <div className="page-desc">{desc}</div>}
      </div>
      {actions && <div className="page-header-actions">{actions}</div>}
    </div>
  );
}

// ─── Modal ─────────────────────────────────────────────────────────────────
export function Modal({ open, onClose, title, children, footer }) {
  if (!open) return null;
  return (
    <div
      className="modal-backdrop"
      onClick={(e) => e.target === e.currentTarget && onClose?.()}
    >
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-header">
          <span className="modal-title">{title}</span>
          <button className="btn btn-ghost btn-icon btn-sm" onClick={onClose} aria-label="Close">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
}

// ─── Card ─────────────────────────────────────────────────────────────────
export function Card({ title, actions, children, footer, className = '' }) {
  return (
    <div className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-header">
          {title && <span className="card-title">{title}</span>}
          {actions}
        </div>
      )}
      <div className="card-body">{children}</div>
      {footer && <div className="card-footer">{footer}</div>}
    </div>
  );
}

// ─── Alert ──────────────────────────────────────────────────────────────
export function Alert({ type = 'info', children }) {
  const icons = {
    info: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>,
    success: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>,
    warning: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>,
    danger: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>,
  };
  return (
    <div className={`alert alert-${type}`}>
      {icons[type]}
      <span>{children}</span>
    </div>
  );
}

// ─── Tabs ───────────────────────────────────────────────────────────────
export function Tabs({ items, active, onChange }) {
  return (
    <div className="tabs" role="tablist">
      {items.map((item) => (
        <button
          key={item.id}
          role="tab"
          aria-selected={active === item.id}
          className={`tab-item ${active === item.id ? 'active' : ''}`}
          onClick={() => onChange(item.id)}
        >
          {item.icon && item.icon}
          {item.label}
          {item.count != null && (
            <span className={`badge ${item.count > 0 ? 'badge-primary' : 'badge-default'}`}
              style={{ fontSize: '0.6875rem', padding: '1px 6px' }}>
              {item.count}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

// ─── Form group ───────────────────────────────────────────────────────────
export function FormGroup({ label, error, hint, children, required }) {
  return (
    <div className="form-group">
      {label && (
        <label>
          {label}
          {required && <span style={{ color: 'var(--danger)', marginLeft: 2 }}>*</span>}
        </label>
      )}
      {children}
      {hint && <span className="form-hint">{hint}</span>}
      {error && <span className="form-error">{error}</span>}
    </div>
  );
}

// ─── Skeleton ─────────────────────────────────────────────────────────────
export function Skeleton({ width, height = 20, className = '' }) {
  return (
    <div
      className={`skeleton ${className}`}
      style={{ width: width || '100%', height }}
      aria-hidden="true"
    />
  );
}

// ─── Error message extraction ─────────────────────────────────────────────
export function getErrorMessage(err) {
  const detail = err?.response?.data?.detail;
  // FastAPI 422 validation errors return detail as an array of {loc, msg, type} objects.
  // Rendering an object directly in JSX crashes React with "Objects are not valid as a React child".
  if (Array.isArray(detail)) {
    return detail.map((d) => d?.msg || JSON.stringify(d)).join('; ');
  }
  return detail || err?.message || 'Terjadi kesalahan. Silakan coba lagi.';
}
