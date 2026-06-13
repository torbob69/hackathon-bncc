import { useState, useEffect, useCallback } from 'react';
import AppShell from '../components/AppShell.jsx';
import {
  Money, StatusBadge, formatDate, formatDateTime,
  Spinner, EmptyState, PageHeader, Modal,
  Card, Alert, Tabs, FormGroup, Skeleton, getErrorMessage,
} from '../components/ui.jsx';
import {
  adminFarmersAPI, adminLoansAPI, adminFundsAPI, adminOversightAPI,
} from '../api/client.js';
import { toast } from '../hooks/useToast.jsx';

// ─── Icons ────────────────────────────────────────────────────────────────────
const HomeIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
    <polyline points="9 22 9 12 15 12 15 22"/>
  </svg>
);
const UsersIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
    <circle cx="9" cy="7" r="4"/>
    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
    <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
  </svg>
);
const CreditCardIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <rect x="1" y="4" width="22" height="16" rx="2" ry="2"/>
    <line x1="1" y1="10" x2="23" y2="10"/>
  </svg>
);
const WalletIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"/>
    <path d="M3 5v14a2 2 0 0 0 2 2h16v-5"/>
    <path d="M18 12a2 2 0 0 0 0 4h4v-4z"/>
  </svg>
);
const ClipboardIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>
    <rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>
  </svg>
);
const PlusIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="15" height="15">
    <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
  </svg>
);
const CheckIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="13" height="13">
    <polyline points="20 6 9 17 4 12"/>
  </svg>
);
const XIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="13" height="13">
    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
  </svg>
);
const AlertTriangleIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" width="13" height="13">
    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
    <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
  </svg>
);
const EyeIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="13" height="13">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
    <circle cx="12" cy="12" r="3"/>
  </svg>
);
const RefreshIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
    <polyline points="23 4 23 10 17 10"/>
    <polyline points="1 20 1 14 7 14"/>
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
  </svg>
);

// ─── Reason Modal (shared for reject / seize) ─────────────────────────────────
function ReasonModal({ open, onClose, title, placeholder, confirmLabel, confirmClass, onConfirm, loading }) {
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');

  const handleConfirm = () => {
    if (!reason.trim()) { setError('Harap isi alasan terlebih dahulu.'); return; }
    onConfirm(reason.trim());
  };

  useEffect(() => { if (!open) { setReason(''); setError(''); } }, [open]);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      footer={
        <>
          <button className="btn btn-secondary" onClick={onClose} disabled={loading}>Batal</button>
          <button className={`btn ${confirmClass || 'btn-danger'}`} onClick={handleConfirm} disabled={loading}>
            {loading && <Spinner />}
            {loading ? 'Memproses...' : confirmLabel}
          </button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {error && <Alert type="danger">{error}</Alert>}
        <FormGroup label="Alasan" required>
          <textarea
            rows={3}
            placeholder={placeholder || 'Masukkan alasan...'}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </FormGroup>
      </div>
    </Modal>
  );
}

// ─── Dashboard Tab ────────────────────────────────────────────────────────────
function DashboardTab({ onNavigate }) {
  const [stats, setStats] = useState(null);
  const [funds, setFunds] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      adminOversightAPI.dashboard().catch(() => ({ data: null })),
      adminFundsAPI.get().catch(() => ({ data: null })),
    ]).then(([statsRes, fundsRes]) => {
      setStats(statsRes.data);
      setFunds(fundsRes.data);
    }).finally(() => setLoading(false));
  }, []);

  const s = stats || {};
  const f = funds || {};

  return (
    <div className="section-gap-lg">
      <div className="stat-grid">
        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span className="stat-label">Petani Aktif</span>
            <div className="stat-icon" style={{ background: 'var(--success-bg)', color: 'var(--success)' }}><UsersIcon /></div>
          </div>
          {loading ? <Skeleton height={32} width="60px" /> : <div className="stat-value">{s.active_farmers ?? '—'}</div>}
          <div className="stat-sub">dari {s.total_farmers ?? '—'} total terdaftar</div>
        </div>

        <div className="stat-card" style={{ cursor: s.pending_farmers > 0 ? 'pointer' : 'default' }} onClick={() => s.pending_farmers > 0 && onNavigate('petani')}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span className="stat-label">Menunggu Aktivasi</span>
            <div className="stat-icon" style={{ background: 'var(--warning-bg)', color: 'var(--warning)' }}><UsersIcon /></div>
          </div>
          {loading ? <Skeleton height={32} width="60px" /> : (
            <div className="stat-value" style={{ color: (s.pending_farmers ?? 0) > 0 ? 'var(--warning)' : 'var(--ink)' }}>
              {s.pending_farmers ?? '—'}
            </div>
          )}
          <div className="stat-sub">{(s.pending_farmers ?? 0) > 0 ? 'Klik untuk tinjau' : 'Tidak ada pending'}</div>
        </div>

        <div className="stat-card" style={{ cursor: s.pending_loans > 0 ? 'pointer' : 'default' }} onClick={() => s.pending_loans > 0 && onNavigate('pinjaman')}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span className="stat-label">Pengajuan Pinjaman</span>
            <div className="stat-icon" style={{ background: 'var(--info-bg)', color: 'var(--info)' }}><CreditCardIcon /></div>
          </div>
          {loading ? <Skeleton height={32} width="60px" /> : (
            <div className="stat-value" style={{ color: (s.pending_loans ?? 0) > 0 ? 'var(--info)' : 'var(--ink)' }}>
              {s.pending_loans ?? '—'}
            </div>
          )}
          <div className="stat-sub">{s.active_loans ?? '—'} pinjaman aktif</div>
        </div>

        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span className="stat-label">NPL Rate</span>
            <div className="stat-icon" style={{ background: 'var(--danger-bg)', color: 'var(--danger)' }}><AlertTriangleIcon /></div>
          </div>
          {loading ? <Skeleton height={32} width="80px" /> : (
            <div className="stat-value" style={{ fontSize: '1.25rem', color: (s.npl_rate ?? 0) > 5 ? 'var(--danger)' : 'var(--ink)' }}>
              {s.npl_rate != null ? `${parseFloat(s.npl_rate).toFixed(2)}%` : '—'}
            </div>
          )}
          <div className="stat-sub">Non-performing loan</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div className="pool-card">
          <div className="pool-header">
            <div>
              <div className="pool-label">Margin Profit Pool</div>
              {loading ? <Skeleton height={28} width="160px" /> : (
                <div className="pool-amount"><Money value={f.marginal_profit_pool_balance ?? 0} /></div>
              )}
            </div>
            <div className="stat-icon" style={{ background: 'var(--success-bg)', color: 'var(--success)' }}><WalletIcon /></div>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--muted)', marginTop: 4 }}>
            Sumber: margin dagang koperasi · Digunakan: pembelian panen
          </div>
        </div>

        <div className="pool-card">
          <div className="pool-header">
            <div>
              <div className="pool-label">Loan Pool (APBN)</div>
              {loading ? <Skeleton height={28} width="160px" /> : (
                <div className="pool-amount"><Money value={f.loan_pool_balance ?? 0} /></div>
              )}
            </div>
            <div className="stat-icon" style={{ background: 'var(--primary-light)', color: 'var(--primary)' }}><WalletIcon /></div>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--muted)', marginTop: 4 }}>
            Sumber: dana APBN / hibah · Digunakan: pinjaman petani
          </div>
        </div>
      </div>

      {(s.pending_farmers > 0 || s.pending_loans > 0) && !loading && (
        <Alert type="warning">
          <strong>Perlu tindakan:</strong>{' '}
          {s.pending_farmers > 0 && `${s.pending_farmers} petani menunggu aktivasi`}
          {s.pending_farmers > 0 && s.pending_loans > 0 && ' · '}
          {s.pending_loans > 0 && `${s.pending_loans} pengajuan pinjaman menunggu persetujuan`}
        </Alert>
      )}
    </div>
  );
}

// ─── Create Farmer Modal ──────────────────────────────────────────────────────
function CreateFarmerModal({ open, onClose, onSuccess }) {
  const [form, setForm] = useState({ name: '', email: '', phone: '', nik: '', address: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const reset = () => { setForm({ name: '', email: '', phone: '', nik: '', address: '' }); setError(''); };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!form.name.trim() || !form.email.trim() || !form.phone.trim() || !form.nik.trim() || !form.address.trim()) {
      setError('Semua field wajib diisi.'); return;
    }
    if (!/^\d{16}$/.test(form.nik.trim())) {
      setError('NIK harus berupa 16 digit angka.'); return;
    }
    setLoading(true);
    try {
      const res = await adminFarmersAPI.create(form);
      toast.success(`Petani ${form.name} berhasil didaftarkan. Link aktivasi dikirim ke email.`);
      onSuccess(res.data);
      reset();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const set = (field) => (e) => setForm(f => ({ ...f, [field]: e.target.value }));

  return (
    <Modal
      open={open}
      onClose={() => { onClose(); reset(); }}
      title="Tambah Petani Baru"
      footer={
        <>
          <button className="btn btn-secondary" onClick={() => { onClose(); reset(); }} disabled={loading}>Batal</button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={loading}>
            {loading && <Spinner />}
            {loading ? 'Menyimpan...' : 'Daftarkan Petani'}
          </button>
        </>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {error && <Alert type="danger">{error}</Alert>}
        <Alert type="info">
          Petani akan menerima link aktivasi di email untuk mengatur password akun mereka.
        </Alert>
        <FormGroup label="Nama Lengkap" required>
          <input value={form.name} onChange={set('name')} placeholder="Budi Santoso" />
        </FormGroup>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <FormGroup label="Email" required hint="Untuk link aktivasi">
            <input type="email" value={form.email} onChange={set('email')} placeholder="budi@email.com" />
          </FormGroup>
          <FormGroup label="No. HP" required>
            <input value={form.phone} onChange={set('phone')} placeholder="0812..." />
          </FormGroup>
        </div>
        <FormGroup label="NIK" required hint="16 digit angka sesuai KTP">
          <input
            value={form.nik}
            onChange={set('nik')}
            maxLength="16"
            placeholder="3201234567890001"
            style={{ fontFamily: 'var(--font-mono)' }}
          />
        </FormGroup>
        <FormGroup label="Alamat" required>
          <textarea value={form.address} onChange={set('address')} rows={2} placeholder="Jl. Melati No. 5, Desa Sukamaju..." />
        </FormGroup>
      </div>
    </Modal>
  );
}

// ─── Farmers Tab ─────────────────────────────────────────────────────────────
const FARMER_FILTERS = [
  { value: 'all', label: 'Semua' },
  { value: 'pending', label: 'Menunggu' },
  { value: 'active', label: 'Aktif' },
];

function FarmersTab() {
  const [farmers, setFarmers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('pending');
  const [showCreate, setShowCreate] = useState(false);
  const [rejectTarget, setRejectTarget] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);

  const load = useCallback((f) => {
    setLoading(true);
    adminFarmersAPI.list(f === 'all' ? null : f)
      .then(r => setFarmers(r.data))
      .catch(err => toast.error(getErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(filter); }, [filter, load]);

  const handleApprove = async (farmer) => {
    setActionLoading(farmer.id);
    try {
      await adminFarmersAPI.approve(farmer.id);
      toast.success(`${farmer.name || `Petani #${farmer.id}`} berhasil diaktivasi.`);
      load(filter);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (reason) => {
    if (!rejectTarget) return;
    setActionLoading(rejectTarget.id);
    try {
      await adminFarmersAPI.reject(rejectTarget.id, reason);
      toast.success(`Pendaftaran petani ditolak.`);
      setRejectTarget(null);
      load(filter);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setActionLoading(null);
    }
  };

  const pendingCount = filter === 'pending' ? farmers.length : undefined;

  return (
    <div className="section-gap">
      <PageHeader
        title="Manajemen Petani"
        desc="Daftarkan petani baru dan kelola status keanggotaan."
        actions={
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
            <PlusIcon /> Tambah Petani
          </button>
        }
      />

      <CreateFarmerModal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onSuccess={(f) => { setShowCreate(false); load(filter); }}
      />

      <ReasonModal
        open={!!rejectTarget}
        onClose={() => setRejectTarget(null)}
        title={`Tolak Petani: ${rejectTarget?.name || ''}`}
        placeholder="Mis. NIK tidak valid, data tidak lengkap..."
        confirmLabel="Tolak Pendaftaran"
        confirmClass="btn-danger"
        onConfirm={handleReject}
        loading={actionLoading === rejectTarget?.id}
      />

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {FARMER_FILTERS.map(f => (
          <button
            key={f.value}
            className={`btn btn-sm ${filter === f.value ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[1, 2, 3].map(i => <Skeleton key={i} height={52} />)}
        </div>
      ) : farmers.length === 0 ? (
        <EmptyState
          icon={<UsersIcon />}
          title={filter === 'pending' ? 'Tidak ada petani pending' : 'Belum ada petani'}
          desc={filter === 'pending' ? 'Semua pendaftaran sudah ditindaklanjuti.' : 'Daftarkan petani pertama koperasi.'}
          action={filter !== 'pending' && (
            <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
              <PlusIcon /> Tambah Petani
            </button>
          )}
        />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Nama</th>
                <th>NIK</th>
                <th>Email / HP</th>
                <th>Status</th>
                <th>Terdaftar</th>
                <th>Aksi</th>
              </tr>
            </thead>
            <tbody>
              {farmers.map(f => (
                <tr key={f.id}>
                  <td className="td-primary">{f.name || f.user?.name || `Petani #${f.id}`}</td>
                  <td className="td-mono" style={{ fontSize: '0.8125rem' }}>{f.nik || '—'}</td>
                  <td>
                    <div style={{ fontSize: '0.8125rem', color: 'var(--ink-2)' }}>{f.email || f.user?.email || '—'}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>{f.phone || f.user?.phone || ''}</div>
                  </td>
                  <td><StatusBadge status={f.status} /></td>
                  <td className="td-muted td-mono">{formatDate(f.created_at)}</td>
                  <td>
                    {f.status === 'pending' ? (
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button
                          className="btn btn-success btn-xs"
                          onClick={() => handleApprove(f)}
                          disabled={actionLoading === f.id}
                          title="Aktifkan petani"
                        >
                          {actionLoading === f.id ? <Spinner /> : <CheckIcon />}
                          Aktifkan
                        </button>
                        <button
                          className="btn btn-danger btn-xs"
                          onClick={() => setRejectTarget(f)}
                          disabled={actionLoading === f.id}
                          title="Tolak pendaftaran"
                        >
                          <XIcon /> Tolak
                        </button>
                      </div>
                    ) : (
                      <span className="td-muted">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Loan Detail Modal (Admin view) ───────────────────────────────────────────
function AdminLoanDetailModal({ loanId, open, onClose, onAction }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [actionModal, setActionModal] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    if (!open || !loanId) return;
    setDetail(null);
    setLoading(true);
    adminLoansAPI.get(loanId)
      .then(r => setDetail(r.data))
      .catch(err => toast.error(getErrorMessage(err)))
      .finally(() => setLoading(false));
  }, [open, loanId]);

  const handleAction = async (type, reason) => {
    setActionLoading(true);
    try {
      if (type === 'approve') await adminLoansAPI.approve(loanId);
      else if (type === 'reject') await adminLoansAPI.reject(loanId, reason);
      else if (type === 'seize') await adminLoansAPI.seize(loanId, reason);
      const label = type === 'approve' ? 'disetujui' : type === 'reject' ? 'ditolak' : 'disita';
      toast.success(`Pinjaman berhasil ${label}.`);
      setActionModal(null);
      onAction?.();
      onClose();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setActionLoading(false);
    }
  };

  const loan = detail?.loan || detail;
  const installments = detail?.installments || [];

  return (
    <>
      <Modal
        open={open}
        onClose={onClose}
        title={loan ? `Detail Pinjaman #${loan.id}` : 'Detail Pinjaman'}
        footer={
          loan && (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {loan.status === 'pending' && (
                <>
                  <button className="btn btn-danger btn-sm" onClick={() => setActionModal('reject')}>
                    <XIcon /> Tolak
                  </button>
                  <button className="btn btn-success btn-sm" onClick={() => handleAction('approve')}>
                    {actionLoading ? <Spinner /> : <CheckIcon />}
                    Setujui &amp; Cairkan
                  </button>
                </>
              )}
              {(loan.status === 'active' || loan.status === 'past_due') && (
                <button className="btn btn-danger btn-sm" onClick={() => setActionModal('seize')}>
                  <AlertTriangleIcon /> Sita Agunan
                </button>
              )}
              <button className="btn btn-secondary btn-sm" onClick={onClose}>Tutup</button>
            </div>
          )
        }
      >
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}><Spinner large /></div>
        ) : loan ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, background: 'var(--surface-2)', borderRadius: 10, padding: 16 }}>
              {[
                ['Petani', loan.farmer_name || `#${loan.farmer_id}`],
                ['Status', <StatusBadge status={loan.status} />],
                ['Pokok', <Money value={loan.principal} />],
                ['Bunga/Tahun', `${loan.interest_rate}%`],
                ['Tenor', `${loan.installment_months} bulan`],
                ['Tujuan', <span style={{ textTransform: 'capitalize' }}>{loan.purpose}</span>],
                ['Skor Kredit', loan.credit_score ?? '—'],
                ['Tier Kredit', loan.credit_tier ?? '—'],
                ['Tanggal Pengajuan', formatDate(loan.created_at)],
                ...(loan.disbursed_at ? [['Tanggal Cair', formatDate(loan.disbursed_at)]] : []),
              ].map(([label, val]) => (
                <div key={label}>
                  <div style={{ fontSize: '0.6875rem', color: 'var(--muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{label}</div>
                  <div style={{ fontWeight: 600, color: 'var(--ink)', marginTop: 2, fontSize: '0.875rem' }}>{val}</div>
                </div>
              ))}
            </div>

            {installments.length > 0 && (
              <div>
                <div style={{ fontWeight: 700, color: 'var(--ink)', fontSize: '0.875rem', marginBottom: 10 }}>
                  Jadwal Angsuran ({installments.filter(i => i.status === 'paid').length}/{installments.length} lunas)
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 240, overflowY: 'auto' }}>
                  {installments.map((inst, idx) => (
                    <div
                      key={inst.id}
                      style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '8px 12px', borderRadius: 8, fontSize: '0.8125rem',
                        background: inst.status === 'paid' ? 'var(--success-bg)' : inst.status === 'past_due' ? 'var(--danger-bg)' : 'var(--surface-2)',
                        border: `1px solid ${inst.status === 'paid' ? 'var(--success-border)' : inst.status === 'past_due' ? 'var(--danger-border)' : 'var(--border)'}`,
                      }}
                    >
                      <span style={{ color: 'var(--ink-2)' }}>Angsuran ke-{idx + 1} · {formatDate(inst.due_date)}</span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Money value={inst.amount_due} />
                        <StatusBadge status={inst.status} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : null}
      </Modal>

      <ReasonModal
        open={actionModal === 'reject'}
        onClose={() => setActionModal(null)}
        title="Tolak Pengajuan Pinjaman"
        placeholder="Mis. Skor kredit tidak memenuhi minimum, stok tidak mencukupi..."
        confirmLabel="Tolak Pinjaman"
        confirmClass="btn-danger"
        onConfirm={(r) => handleAction('reject', r)}
        loading={actionLoading}
      />
      <ReasonModal
        open={actionModal === 'seize'}
        onClose={() => setActionModal(null)}
        title="Sita Agunan"
        placeholder="Mis. 3 bulan menunggak, sudah 2x peringatan..."
        confirmLabel="Konfirmasi Penyitaan"
        confirmClass="btn-danger"
        onConfirm={(r) => handleAction('seize', r)}
        loading={actionLoading}
      />
    </>
  );
}

// ─── Loans Tab ────────────────────────────────────────────────────────────────
const LOAN_FILTERS = [
  { value: 'pending', label: 'Menunggu' },
  { value: 'active', label: 'Aktif' },
  { value: 'past_due', label: 'Jatuh Tempo' },
  { value: 'all', label: 'Semua' },
  { value: 'paid', label: 'Lunas' },
  { value: 'rejected', label: 'Ditolak' },
];

function LoansTab() {
  const [loans, setLoans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('pending');
  const [selectedLoanId, setSelectedLoanId] = useState(null);
  const [showDetail, setShowDetail] = useState(false);

  const load = useCallback((f) => {
    setLoading(true);
    adminLoansAPI.list(f === 'all' ? null : f)
      .then(r => setLoans(r.data))
      .catch(err => toast.error(getErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(filter); }, [filter, load]);

  const openDetail = (id) => { setSelectedLoanId(id); setShowDetail(true); };

  const markPastDue = async () => {
    try {
      await adminLoansAPI.markPastDue();
      toast.success('Angsuran jatuh tempo berhasil diperbarui.');
      load(filter);
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  return (
    <div className="section-gap">
      <PageHeader
        title="Manajemen Pinjaman"
        desc="Tinjau pengajuan, setujui, tolak, atau sita agunan pinjaman petani."
        actions={
          <button className="btn btn-secondary btn-sm" onClick={markPastDue} title="Tandai angsuran yang sudah lewat jatuh tempo">
            <RefreshIcon /> Tandai Jatuh Tempo
          </button>
        }
      />

      <AdminLoanDetailModal
        loanId={selectedLoanId}
        open={showDetail}
        onClose={() => { setShowDetail(false); setSelectedLoanId(null); }}
        onAction={() => load(filter)}
      />

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {LOAN_FILTERS.map(f => (
          <button
            key={f.value}
            className={`btn btn-sm ${filter === f.value ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[1, 2, 3].map(i => <Skeleton key={i} height={52} />)}
        </div>
      ) : loans.length === 0 ? (
        <EmptyState
          icon={<CreditCardIcon />}
          title={filter === 'pending' ? 'Tidak ada pengajuan pinjaman' : 'Tidak ada pinjaman'}
          desc={filter === 'pending' ? 'Belum ada pengajuan yang perlu ditinjau.' : undefined}
        />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Petani</th>
                <th>Tujuan</th>
                <th>Pokok</th>
                <th>Tenor</th>
                <th>Skor / Tier</th>
                <th>Status</th>
                <th>Tanggal</th>
                <th>Aksi</th>
              </tr>
            </thead>
            <tbody>
              {loans.map(l => (
                <tr key={l.id}>
                  <td className="td-primary">{l.farmer_name || `Petani #${l.farmer_id}`}</td>
                  <td style={{ textTransform: 'capitalize' }}>{l.purpose}</td>
                  <td className="td-mono"><Money value={l.principal} /></td>
                  <td>{l.installment_months} bln</td>
                  <td className="td-mono">
                    {l.credit_score != null ? `${l.credit_score}` : '—'}
                    {l.credit_tier ? ` / ${l.credit_tier}` : ''}
                  </td>
                  <td><StatusBadge status={l.status} /></td>
                  <td className="td-muted td-mono">{formatDate(l.created_at)}</td>
                  <td>
                    <button className="btn btn-secondary btn-xs" onClick={() => openDetail(l.id)}>
                      <EyeIcon /> Detail
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Funds Tab ────────────────────────────────────────────────────────────────
function FundsTab() {
  const [funds, setFunds] = useState(null);
  const [loadingFunds, setLoadingFunds] = useState(true);
  const [ledger, setLedger] = useState([]);
  const [loadingLedger, setLoadingLedger] = useState(true);
  const [ledgerFilter, setLedgerFilter] = useState('');

  const [grantAmount, setGrantAmount] = useState('');
  const [grantNote, setGrantNote] = useState('');
  const [grantLoading, setGrantLoading] = useState(false);
  const [grantError, setGrantError] = useState('');

  const [dummyAmount, setDummyAmount] = useState('');
  const [dummyNote, setDummyNote] = useState('');
  const [dummyLoading, setDummyLoading] = useState(false);
  const [dummyError, setDummyError] = useState('');

  const loadFunds = useCallback(() => {
    setLoadingFunds(true);
    adminFundsAPI.get()
      .then(r => setFunds(r.data))
      .catch(err => toast.error(getErrorMessage(err)))
      .finally(() => setLoadingFunds(false));
  }, []);

  const loadLedger = useCallback(() => {
    setLoadingLedger(true);
    adminFundsAPI.ledger(ledgerFilter ? { type: ledgerFilter } : {})
      .then(r => setLedger(Array.isArray(r.data) ? r.data : r.data?.items || []))
      .catch(err => toast.error(getErrorMessage(err)))
      .finally(() => setLoadingLedger(false));
  }, [ledgerFilter]);

  useEffect(() => { loadFunds(); }, [loadFunds]);
  useEffect(() => { loadLedger(); }, [loadLedger]);

  const handleGrant = async (e) => {
    e.preventDefault();
    setGrantError('');
    const amt = parseFloat(grantAmount);
    if (!amt || amt <= 0) { setGrantError('Masukkan jumlah dana yang valid.'); return; }
    setGrantLoading(true);
    try {
      await adminFundsAPI.apbnGrant(amt, grantNote || 'Pengisian dana APBN');
      toast.success(`Dana APBN Rp ${amt.toLocaleString('id-ID')} berhasil ditambahkan ke Loan Pool.`);
      setGrantAmount('');
      setGrantNote('');
      loadFunds();
      loadLedger();
    } catch (err) {
      setGrantError(getErrorMessage(err));
    } finally {
      setGrantLoading(false);
    }
  };

  const handleDummy = async (e) => {
    e.preventDefault();
    setDummyError('');
    const amt = parseFloat(dummyAmount);
    if (!amt || amt <= 0) { setDummyError('Masukkan jumlah dana yang valid.'); return; }
    setDummyLoading(true);
    try {
      await adminFundsAPI.marginalDummy(amt, dummyNote || 'Injeksi Manual Testing');
      toast.success(`Dana Marginal Dummy Rp ${amt.toLocaleString('id-ID')} berhasil ditambahkan.`);
      setDummyAmount('');
      setDummyNote('');
      loadFunds();
      loadLedger();
    } catch (err) {
      setDummyError(getErrorMessage(err));
    } finally {
      setDummyLoading(false);
    }
  };

  const LEDGER_TYPE_LABELS = {
    sale_settlement: 'Penerimaan Penjualan',
    farmer_payment: 'Pembayaran Panen',
    platform_fee: 'Biaya Platform',
    apbn_grant: 'Dana APBN',
    loan_disbursement: 'Pencairan Pinjaman',
    loan_repayment: 'Angsuran Pinjaman',
    refund: 'Refund',
  };

  const LEDGER_FILTERS = [
    { value: '', label: 'Semua' },
    { value: 'apbn_grant', label: 'APBN Grant' },
    { value: 'farmer_payment', label: 'Pembayaran Panen' },
    { value: 'loan_disbursement', label: 'Pencairan Pinjaman' },
    { value: 'loan_repayment', label: 'Angsuran' },
    { value: 'sale_settlement', label: 'Penjualan' },
  ];

  return (
    <div className="section-gap">
      <PageHeader
        title="Manajemen Dana"
        desc="Kelola dua pool dana koperasi: Margin Profit dan Loan Pool (APBN)."
      />

      {/* Pool balances */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div className="pool-card">
          <div className="pool-header">
            <div>
              <div className="pool-label">Marginal Profit Pool</div>
              {loadingFunds ? <Skeleton height={28} width="160px" /> : (
                <div className="pool-amount"><Money value={funds?.marginal_profit_pool_balance ?? 0} /></div>
              )}
            </div>
            <div className="stat-icon" style={{ background: 'var(--success-bg)', color: 'var(--success)' }}><WalletIcon /></div>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--muted)', marginTop: 6 }}>
            Digunakan untuk pembelian hasil panen petani. Bersumber dari margin perdagangan koperasi.
          </div>
        </div>

        <div className="pool-card">
          <div className="pool-header">
            <div>
              <div className="pool-label">Loan Pool (APBN)</div>
              {loadingFunds ? <Skeleton height={28} width="160px" /> : (
                <div className="pool-amount"><Money value={funds?.loan_pool_balance ?? 0} /></div>
              )}
            </div>
            <div className="stat-icon" style={{ background: 'var(--primary-light)', color: 'var(--primary)' }}><WalletIcon /></div>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--muted)', marginTop: 6 }}>
            Digunakan khusus untuk pinjaman petani. Bersumber dari dana APBN / hibah pemerintah.
          </div>
        </div>
      </div>

      {/* APBN Grant form */}
      <Card title="Input Dana APBN ke Loan Pool">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Alert type="info">
            Dana APBN dikreditkan <strong>hanya ke Loan Pool</strong> dan digunakan untuk pinjaman petani sesuai regulasi KSP.
            Dana ini tidak dapat dicampur dengan Marginal Profit Pool.
          </Alert>
          {grantError && <Alert type="danger">{grantError}</Alert>}
          <form onSubmit={handleGrant} style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <FormGroup label="Jumlah Dana (Rp)" required style={{ flex: 1, minWidth: 200 }}>
              <input
                type="number"
                min="1"
                step="100000"
                placeholder="mis. 50.000.000"
                value={grantAmount}
                onChange={(e) => setGrantAmount(e.target.value)}
              />
            </FormGroup>
            <FormGroup label="Catatan" style={{ flex: 2, minWidth: 200 }}>
              <input
                placeholder="mis. Dana APBN Q2 2026 – SK No. 001"
                value={grantNote}
                onChange={(e) => setGrantNote(e.target.value)}
              />
            </FormGroup>
            <div style={{ paddingBottom: 1 }}>
              <button type="submit" className="btn btn-primary" disabled={grantLoading}>
                {grantLoading && <Spinner />}
                {grantLoading ? 'Memproses...' : 'Tambah Dana'}
              </button>
            </div>
          </form>
        </div>
      </Card>

      {/* Dummy Marginal form */}
      <Card title="Input Dana ke Marginal Pool (Untuk Testing)">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Alert type="warning">
            Dana Marginal secara operasional didapat dari keuntungan (settlement). Fitur top-up ini hanya ditujukan untuk <strong>testing/demonstrasi</strong> (menggunakan tipe transaksi Refund/Adjustment).
          </Alert>
          {dummyError && <Alert type="danger">{dummyError}</Alert>}
          <form onSubmit={handleDummy} style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <FormGroup label="Jumlah Dana (Rp)" required style={{ flex: 1, minWidth: 200 }}>
              <input
                type="number"
                min="1"
                step="100000"
                placeholder="mis. 10.000.000"
                value={dummyAmount}
                onChange={(e) => setDummyAmount(e.target.value)}
              />
            </FormGroup>
            <FormGroup label="Catatan" style={{ flex: 2, minWidth: 200 }}>
              <input
                placeholder="mis. Injeksi Dummy untuk Testing"
                value={dummyNote}
                onChange={(e) => setDummyNote(e.target.value)}
              />
            </FormGroup>
            <div style={{ paddingBottom: 1 }}>
              <button type="submit" className="btn btn-warning" disabled={dummyLoading}>
                {dummyLoading && <Spinner />}
                {dummyLoading ? 'Memproses...' : 'Injeksi Dana'}
              </button>
            </div>
          </form>
        </div>
      </Card>

      {/* Ledger entries */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
          <div style={{ fontWeight: 700, color: 'var(--ink)', fontSize: '0.9375rem' }}>Riwayat Transaksi</div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {LEDGER_FILTERS.map(f => (
              <button
                key={f.value}
                className={`btn btn-xs ${ledgerFilter === f.value ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setLedgerFilter(f.value)}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {loadingLedger ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[1, 2, 3, 4].map(i => <Skeleton key={i} height={44} />)}
          </div>
        ) : ledger.length === 0 ? (
          <EmptyState icon={<WalletIcon />} title="Belum ada transaksi" desc="Riwayat transaksi akan tampil di sini." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Tanggal</th>
                  <th>Jenis</th>
                  <th>Pool</th>
                  <th>Arah</th>
                  <th>Jumlah</th>
                  <th>Saldo Setelah</th>
                </tr>
              </thead>
              <tbody>
                {ledger.slice(0, 50).map(e => (
                  <tr key={e.id}>
                    <td className="td-muted td-mono">{formatDateTime(e.created_at)}</td>
                    <td>{LEDGER_TYPE_LABELS[e.type] || e.type}</td>
                    <td>
                      <span className={`badge ${e.pool === 'loan' ? 'badge-info' : 'badge-active'}`} style={{ fontSize: '0.6875rem' }}>
                        {e.pool === 'loan' ? 'Loan' : 'Margin'}
                      </span>
                    </td>
                    <td>
                      <span style={{ color: e.direction === 'credit' ? 'var(--success)' : 'var(--danger)', fontWeight: 600, fontSize: '0.8125rem' }}>
                        {e.direction === 'credit' ? '▲ Masuk' : '▼ Keluar'}
                      </span>
                    </td>
                    <td className="td-mono" style={{ fontWeight: 600, color: e.direction === 'credit' ? 'var(--success)' : 'var(--danger)' }}>
                      {e.direction === 'credit' ? '+' : '-'}<Money value={e.amount} />
                    </td>
                    <td className="td-mono td-muted">{e.balance_after != null ? <Money value={e.balance_after} /> : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Audit Log Tab ────────────────────────────────────────────────────────────
function AuditTab() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const PAGE_SIZE = 30;

  useEffect(() => {
    setLoading(true);
    adminOversightAPI.auditLog({ limit: PAGE_SIZE, offset: 0 })
      .then(r => {
        const items = Array.isArray(r.data) ? r.data : r.data?.items || [];
        setEntries(items);
        setHasMore(items.length === PAGE_SIZE);
        setPage(1);
      })
      .catch(err => toast.error(getErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const r = await adminOversightAPI.auditLog({ limit: PAGE_SIZE, offset: page * PAGE_SIZE });
      const items = Array.isArray(r.data) ? r.data : r.data?.items || [];
      setEntries(prev => [...prev, ...items]);
      setHasMore(items.length === PAGE_SIZE);
      setPage(p => p + 1);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setLoadingMore(false);
    }
  };

  const ACTION_COLORS = {
    create: 'var(--success)',
    update: 'var(--info)',
    delete: 'var(--danger)',
    approve: 'var(--success)',
    reject: 'var(--danger)',
    confirm: 'var(--success)',
    seize: 'var(--danger)',
  };

  return (
    <div className="section-gap">
      <PageHeader
        title="Audit Log"
        desc="Rekam jejak semua aksi sistem — append-only, tidak dapat diubah atau dihapus."
      />

      <Alert type="info" style={{ fontSize: '0.8125rem' }}>
        Tabel ini <strong>immutable</strong>: setiap aksi dicatat permanen dan tidak dapat diubah sebagai mekanisme anti-fraud.
      </Alert>

      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[1, 2, 3, 4, 5].map(i => <Skeleton key={i} height={44} />)}
        </div>
      ) : entries.length === 0 ? (
        <EmptyState icon={<ClipboardIcon />} title="Belum ada rekam jejak" desc="Aksi sistem akan tercatat di sini." />
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Waktu</th>
                  <th>Aktor</th>
                  <th>Aksi</th>
                  <th>Entitas</th>
                  <th>ID Entitas</th>
                  <th>IP</th>
                </tr>
              </thead>
              <tbody>
                {entries.map(e => (
                  <tr key={e.id}>
                    <td className="td-muted td-mono" style={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                      {formatDateTime(e.created_at)}
                    </td>
                    <td className="td-mono" style={{ fontSize: '0.8125rem' }}>
                      {e.actor_user_id ? `#${e.actor_user_id}` : <span className="td-muted">system</span>}
                    </td>
                    <td>
                      <span style={{
                        fontWeight: 700,
                        fontSize: '0.75rem',
                        color: ACTION_COLORS[e.action?.toLowerCase()] || 'var(--ink-2)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.04em',
                      }}>
                        {e.action}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.8125rem', color: 'var(--ink-2)' }}>{e.entity_type}</td>
                    <td className="td-mono" style={{ fontSize: '0.8125rem' }}>{e.entity_id}</td>
                    <td className="td-mono td-muted" style={{ fontSize: '0.75rem' }}>{e.ip || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {hasMore && (
            <div style={{ display: 'flex', justifyContent: 'center', marginTop: 8 }}>
              <button className="btn btn-secondary" onClick={loadMore} disabled={loadingMore}>
                {loadingMore ? <><Spinner /> Memuat...</> : 'Muat Lebih Banyak'}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────
const TABS = [
  { id: 'dashboard', label: 'Dashboard', icon: <HomeIcon /> },
  { id: 'petani', label: 'Petani', icon: <UsersIcon /> },
  { id: 'pinjaman', label: 'Pinjaman', icon: <CreditCardIcon /> },
  { id: 'dana', label: 'Dana', icon: <WalletIcon /> },
  { id: 'audit', label: 'Audit Log', icon: <ClipboardIcon /> },
];

export default function AdminDashboard({ user, onLogout }) {
  const [activeTab, setActiveTab] = useState('dashboard');

  const navItems = TABS.map(t => ({
    id: t.id,
    label: t.label,
    icon: t.icon,
    active: activeTab === t.id,
    onClick: () => setActiveTab(t.id),
  }));

  const TAB_TITLES = {
    dashboard: 'Dashboard',
    petani: 'Manajemen Petani',
    pinjaman: 'Manajemen Pinjaman',
    dana: 'Manajemen Dana',
    audit: 'Audit Log',
  };

  return (
    <AppShell
      user={user}
      onLogout={onLogout}
      navItems={navItems}
      topbarTitle={`Admin — ${TAB_TITLES[activeTab]}`}
    >
      <Tabs
        items={TABS.map(t => ({ id: t.id, label: t.label, icon: t.icon }))}
        active={activeTab}
        onChange={setActiveTab}
      />

      {activeTab === 'dashboard' && <DashboardTab onNavigate={setActiveTab} />}
      {activeTab === 'petani' && <FarmersTab />}
      {activeTab === 'pinjaman' && <LoansTab />}
      {activeTab === 'dana' && <FundsTab />}
      {activeTab === 'audit' && <AuditTab />}
    </AppShell>
  );
}
