import { useState, useEffect } from 'react';
import AppShell from '../components/AppShell.jsx';
import {
  Money, StatusBadge, PageHeader, EmptyState, Spinner, Modal,
  FormGroup, Card, Alert, Tabs, formatDate, getErrorMessage,
} from '../components/ui.jsx';
import { koperasiAPI, platformAPI } from '../api/client.js';
import { toast } from '../hooks/useToast.jsx';

// ─── Icons ────────────────────────────────────────────────────────────────────
const GlobalIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/>
    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
  </svg>
);
const HomeIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
    <polyline points="9 22 9 12 15 12 15 22"/>
  </svg>
);
const PlusIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="15" height="15">
    <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
  </svg>
);
const EditIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" width="13" height="13">
    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
  </svg>
);
const MapPinIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" width="13" height="13">
    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
  </svg>
);
const UsersIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" width="13" height="13">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
    <circle cx="9" cy="7" r="4"/>
    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
  </svg>
);
const CheckIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="20" height="20">
    <polyline points="20 6 9 17 4 12"/>
  </svg>
);

// ─── Wizard Progress Bar ─────────────────────────────────────────────────────
const WIZARD_STEPS = [
  { id: 0, label: 'Koperasi' },
  { id: 1, label: 'Admin' },
  { id: 2, label: 'Manajer' },
  { id: 3, label: 'Selesai' },
];

function WizardStepper({ step }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0, marginBottom: 24 }}>
      {WIZARD_STEPS.map((s, idx) => (
        <div key={s.id} style={{ display: 'flex', alignItems: 'center', flex: idx < WIZARD_STEPS.length - 1 ? 1 : 'none' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
            <div style={{
              width: 28, height: 28, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '0.75rem', fontWeight: 700, flexShrink: 0,
              background: step > s.id ? 'var(--success)' : step === s.id ? 'var(--primary)' : 'var(--surface-2)',
              color: step >= s.id ? '#fff' : 'var(--muted)',
              border: step < s.id ? '1.5px solid var(--border)' : 'none',
              transition: 'all 200ms',
            }}>
              {step > s.id ? <CheckIcon /> : s.id + 1}
            </div>
            <span style={{
              fontSize: '0.6875rem', fontWeight: 600, whiteSpace: 'nowrap',
              color: step === s.id ? 'var(--primary)' : step > s.id ? 'var(--success)' : 'var(--muted)',
            }}>
              {s.label}
            </span>
          </div>
          {idx < WIZARD_STEPS.length - 1 && (
            <div style={{
              flex: 1, height: 2, marginBottom: 18, marginLeft: 4, marginRight: 4,
              background: step > s.id ? 'var(--success)' : 'var(--border)',
              transition: 'background 200ms',
            }} />
          )}
        </div>
      ))}
    </div>
  );
}

// ─── Staff Form (reused in wizard + manage modal) ─────────────────────────────
function StaffForm({ role, koperasiId, onSuccess, onSkip }) {
  const [form, setForm] = useState({ name: '', phone: '', email: '', password: '', confirm: '' });
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const set = (f) => (e) => { setForm(v => ({ ...v, [f]: e.target.value })); setError(''); };
  const roleLabel = role === 'admin' ? 'Admin' : 'Manajer';

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) { setError('Nama wajib diisi.'); return; }
    if (!form.phone.trim()) { setError('Nomor HP wajib diisi.'); return; }
    if (form.password.length < 8) { setError('Kata sandi minimal 8 karakter.'); return; }
    if (form.password !== form.confirm) { setError('Konfirmasi kata sandi tidak cocok.'); return; }
    setLoading(true);
    try {
      const res = await platformAPI.createStaff(koperasiId, {
        name: form.name.trim(),
        phone: form.phone.trim(),
        email: form.email.trim() || undefined,
        password: form.password,
        role,
      });
      toast.success(`${roleLabel} ${res.data.name} berhasil ditambahkan.`);
      onSuccess(res.data);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{
        padding: '10px 14px', borderRadius: 8,
        background: role === 'admin' ? 'oklch(0.48 0.18 240 / 0.07)' : 'oklch(0.55 0.18 290 / 0.07)',
        border: `1px solid ${role === 'admin' ? 'oklch(0.48 0.18 240 / 0.2)' : 'oklch(0.55 0.18 290 / 0.2)'}`,
        fontSize: '0.8125rem', color: 'var(--ink-2)',
      }}>
        <strong>{roleLabel}</strong> dapat mengelola {role === 'admin' ? 'petani, pinjaman, dan dana koperasi' : 'intake panen dan stok komoditas'}.
      </div>

      {error && <Alert type="danger">{error}</Alert>}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="form-group" style={{ gridColumn: '1 / -1' }}>
          <label>Nama Lengkap <span style={{ color: 'var(--danger)' }}>*</span></label>
          <input placeholder={`Nama ${roleLabel}`} value={form.name} onChange={set('name')} autoFocus />
        </div>
        <div className="form-group">
          <label>No. HP <span style={{ color: 'var(--danger)' }}>*</span></label>
          <input type="tel" placeholder="0812..." value={form.phone} onChange={set('phone')} />
        </div>
        <div className="form-group">
          <label>Email <span style={{ color: 'var(--muted)', fontWeight: 400 }}>(opsional)</span></label>
          <input type="email" placeholder="opsional" value={form.email} onChange={set('email')} />
        </div>
        <div className="form-group">
          <label>Kata Sandi <span style={{ color: 'var(--danger)' }}>*</span></label>
          <input
            type={showPass ? 'text' : 'password'}
            placeholder="min. 8 karakter"
            value={form.password}
            onChange={set('password')}
            autoComplete="new-password"
          />
        </div>
        <div className="form-group">
          <label>Konfirmasi Sandi <span style={{ color: 'var(--danger)' }}>*</span></label>
          <input
            type={showPass ? 'text' : 'password'}
            placeholder="ulangi sandi"
            value={form.confirm}
            onChange={set('confirm')}
            autoComplete="new-password"
          />
          {form.confirm && (
            <div style={{ fontSize: '0.75rem', marginTop: 3, color: form.password === form.confirm ? 'var(--success)' : 'var(--danger)', fontWeight: 500 }}>
              {form.password === form.confirm ? '✓ Cocok' : '✗ Tidak cocok'}
            </div>
          )}
        </div>
        <label style={{ gridColumn: '1 / -1', display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: '0.8125rem', color: 'var(--ink-2)', userSelect: 'none' }}>
          <input type="checkbox" checked={showPass} onChange={e => setShowPass(e.target.checked)} />
          Tampilkan kata sandi
        </label>
      </div>

      <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
        {onSkip && (
          <button type="button" className="btn btn-secondary" style={{ flex: 1 }} onClick={onSkip} disabled={loading}>
            Lewati
          </button>
        )}
        <button type="submit" className="btn btn-primary" style={{ flex: 2, justifyContent: 'center' }} disabled={loading}>
          {loading ? <><div className="spinner" />Menambahkan...</> : `Tambah ${roleLabel}`}
        </button>
      </div>
    </form>
  );
}

// ─── Koperasi Create Wizard ───────────────────────────────────────────────────
function KoperasiCreateWizard({ onClose, onSuccess }) {
  const [step, setStep] = useState(0);
  const [koperasi, setKoperasi] = useState(null);

  // Step 0 state
  const [form, setForm] = useState({ name: '', type: 'KUD', address: '', region: '', xendit_account_id: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const set = (f) => (e) => setForm(v => ({ ...v, [f]: e.target.value }));

  const handleCreateKoperasi = async (e) => {
    e.preventDefault();
    if (!form.name.trim() || !form.address.trim() || !form.region.trim()) {
      setError('Harap isi semua field wajib.'); return;
    }
    setLoading(true); setError('');
    try {
      const res = await koperasiAPI.create(form);
      setKoperasi(res.data);
      setStep(1);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleDone = () => {
    onSuccess(koperasi);
  };

  const stepTitles = [
    'Tambah Koperasi Baru',
    `Tambah Admin — ${koperasi?.name || ''}`,
    `Tambah Manajer — ${koperasi?.name || ''}`,
    'Koperasi Berhasil Dibuat',
  ];

  return (
    <Modal open onClose={step === 3 ? handleDone : onClose} title={stepTitles[step]}>
      <WizardStepper step={step} />

      {step === 0 && (
        <form onSubmit={handleCreateKoperasi} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {error && <Alert type="danger">{error}</Alert>}
          <FormGroup label="Nama Koperasi" required>
            <input placeholder="Koperasi Melati Jaya" value={form.name} onChange={set('name')} autoFocus required />
          </FormGroup>
          <FormGroup label="Tipe Koperasi" required>
            <select value={form.type} onChange={set('type')}>
              <option value="KUD">KUD</option>
              <option value="KSP">KSP</option>
              <option value="Koperasi Pertanian">Koperasi Pertanian</option>
            </select>
          </FormGroup>
          <FormGroup label="Alamat" required>
            <textarea placeholder="Jl. Petani No. 1..." value={form.address} onChange={set('address')} rows={2} required />
          </FormGroup>
          <FormGroup label="Wilayah / Kota" required>
            <input placeholder="Jakarta Selatan" value={form.region} onChange={set('region')} required />
          </FormGroup>
          <FormGroup label="Xendit Account ID" hint="Opsional — untuk pembayaran split">
            <input placeholder="xendit_acc_..." value={form.xendit_account_id} onChange={set('xendit_account_id')} />
          </FormGroup>
          <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
            <button type="button" className="btn btn-secondary" style={{ flex: 1 }} onClick={onClose} disabled={loading}>Batal</button>
            <button type="submit" className="btn btn-primary" style={{ flex: 2, justifyContent: 'center' }} disabled={loading}>
              {loading ? <><div className="spinner" />Membuat...</> : 'Buat Koperasi →'}
            </button>
          </div>
        </form>
      )}

      {step === 1 && koperasi && (
        <StaffForm
          role="admin"
          koperasiId={koperasi.id}
          onSuccess={() => setStep(2)}
          onSkip={() => setStep(2)}
        />
      )}

      {step === 2 && koperasi && (
        <StaffForm
          role="manager"
          koperasiId={koperasi.id}
          onSuccess={() => setStep(3)}
          onSkip={() => setStep(3)}
        />
      )}

      {step === 3 && koperasi && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20, textAlign: 'center', padding: '8px 0' }}>
          <div style={{
            width: 64, height: 64, borderRadius: '50%',
            background: 'var(--success-bg)', border: '2px solid var(--success-border)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--success)',
          }}>
            <CheckIcon />
          </div>
          <div>
            <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--ink)', letterSpacing: '-0.02em', marginBottom: 6 }}>
              {koperasi.name} berhasil dibuat!
            </div>
            <div style={{ fontSize: '0.9rem', color: 'var(--ink-2)', lineHeight: 1.6 }}>
              Koperasi telah terdaftar di platform. Admin dan manajer dapat langsung masuk menggunakan nomor HP yang didaftarkan.
            </div>
          </div>
          <div style={{
            background: 'var(--surface-2)', border: '1px solid var(--border)',
            borderRadius: 10, padding: '12px 20px', width: '100%', textAlign: 'left',
          }}>
            <div style={{ fontSize: '0.6875rem', fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>Detail Koperasi</div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--ink-2)', display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Nama</span><strong style={{ color: 'var(--ink)' }}>{koperasi.name}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Tipe</span><span>{koperasi.type}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Wilayah</span><span>{koperasi.region}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>ID Platform</span>
                <span style={{ fontFamily: 'var(--font-mono)' }}>#{koperasi.id}</span>
              </div>
            </div>
          </div>
          <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center', padding: '11px 16px' }} onClick={handleDone}>
            Selesai
          </button>
        </div>
      )}
    </Modal>
  );
}

// ─── Edit Koperasi Modal ─────────────────────────────────────────────────────
function KoperasiEditModal({ koperasi, onClose, onSuccess }) {
  const [form, setForm] = useState({
    name: koperasi.name, type: koperasi.type,
    address: koperasi.address, region: koperasi.region,
    xendit_account_id: koperasi.xendit_account_id || '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const set = (f) => (e) => setForm(v => ({ ...v, [f]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim() || !form.address.trim() || !form.region.trim()) {
      setError('Harap isi semua field wajib.'); return;
    }
    setLoading(true); setError('');
    try {
      const res = await koperasiAPI.update(koperasi.id, form);
      toast.success(`Koperasi ${res.data.name} berhasil diperbarui!`);
      onSuccess(res.data);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal open onClose={onClose} title={`Edit Koperasi: ${koperasi.name}`}
      footer={
        <>
          <button className="btn btn-secondary" onClick={onClose} disabled={loading}>Batal</button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={loading}>
            {loading ? <><div className="spinner" />Menyimpan...</> : 'Simpan Perubahan'}
          </button>
        </>
      }
    >
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {error && <Alert type="danger">{error}</Alert>}
        <FormGroup label="Nama Koperasi" required>
          <input placeholder="Koperasi Melati Jaya" value={form.name} onChange={set('name')} required />
        </FormGroup>
        <FormGroup label="Tipe Koperasi" required>
          <select value={form.type} onChange={set('type')}>
            <option value="KUD">KUD</option>
            <option value="KSP">KSP</option>
            <option value="Koperasi Pertanian">Koperasi Pertanian</option>
          </select>
        </FormGroup>
        <FormGroup label="Alamat" required>
          <textarea placeholder="Jl. Petani No. 1..." value={form.address} onChange={set('address')} rows={2} required />
        </FormGroup>
        <FormGroup label="Wilayah / Kota" required>
          <input placeholder="Jakarta Selatan" value={form.region} onChange={set('region')} required />
        </FormGroup>
        <FormGroup label="Xendit Account ID" hint="Opsional — untuk pembayaran split">
          <input placeholder="xendit_acc_..." value={form.xendit_account_id} onChange={set('xendit_account_id')} />
        </FormGroup>
      </form>
    </Modal>
  );
}

// ─── Staff Management Modal ───────────────────────────────────────────────────
function StaffModal({ koperasi, onClose }) {
  const [staff, setStaff] = useState([]);
  const [loading, setLoading] = useState(true);
  const [addingRole, setAddingRole] = useState(null); // 'admin' | 'manager' | null

  useEffect(() => {
    platformAPI.listStaff(koperasi.id)
      .then(r => setStaff(r.data))
      .catch(err => toast.error(getErrorMessage(err)))
      .finally(() => setLoading(false));
  }, [koperasi.id]);

  const admins = staff.filter(u => u.role === 'admin');
  const managers = staff.filter(u => u.role === 'manager');

  const handleStaffAdded = (newUser) => {
    setStaff(prev => [...prev, newUser]);
    setAddingRole(null);
  };

  const StaffRow = ({ user }) => (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '10px 14px', borderRadius: 8,
      background: 'var(--surface-2)', border: '1px solid var(--border)',
    }}>
      <div>
        <div style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--ink)' }}>{user.name}</div>
        <div style={{ fontSize: '0.75rem', color: 'var(--muted)', marginTop: 2 }}>
          {user.phone}{user.email ? ` · ${user.email}` : ''}
        </div>
      </div>
      <span className={`badge badge-${user.role === 'admin' ? 'info' : 'warning'}`}>
        {user.role === 'admin' ? 'Admin' : 'Manajer'}
      </span>
    </div>
  );

  return (
    <Modal open onClose={onClose} title={`Kelola Staff — ${koperasi.name}`}>
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}><Spinner /></div>
      ) : addingRole ? (
        <>
          <button className="login-back" onClick={() => setAddingRole(null)} style={{ marginBottom: 16 }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: 16, height: 16 }}>
              <polyline points="15 18 9 12 15 6"/>
            </svg>
            Kembali ke daftar staff
          </button>
          <StaffForm
            role={addingRole}
            koperasiId={koperasi.id}
            onSuccess={handleStaffAdded}
            onSkip={null}
          />
        </>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Admin section */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <div style={{ fontWeight: 700, fontSize: '0.875rem', color: 'var(--ink)' }}>
                Admin ({admins.length})
              </div>
              <button className="btn btn-secondary btn-xs" onClick={() => setAddingRole('admin')}>
                <PlusIcon /> Tambah Admin
              </button>
            </div>
            {admins.length === 0 ? (
              <div style={{ padding: '12px 14px', borderRadius: 8, background: 'var(--danger-bg)', border: '1px solid var(--danger-border)', fontSize: '0.8125rem', color: 'var(--danger)' }}>
                Belum ada admin. Tambahkan admin agar koperasi dapat dikelola.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {admins.map(u => <StaffRow key={u.id} user={u} />)}
              </div>
            )}
          </div>

          {/* Manager section */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <div style={{ fontWeight: 700, fontSize: '0.875rem', color: 'var(--ink)' }}>
                Manajer ({managers.length})
              </div>
              <button className="btn btn-secondary btn-xs" onClick={() => setAddingRole('manager')}>
                <PlusIcon /> Tambah Manajer
              </button>
            </div>
            {managers.length === 0 ? (
              <div style={{ padding: '12px 14px', borderRadius: 8, background: 'var(--warning-bg)', border: '1px solid var(--warning-border)', fontSize: '0.8125rem', color: 'var(--warning)' }}>
                Belum ada manajer. Tambahkan manajer untuk mengelola intake dan stok.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {managers.map(u => <StaffRow key={u.id} user={u} />)}
              </div>
            )}
          </div>
        </div>
      )}
    </Modal>
  );
}

// ─── Koperasi Card ────────────────────────────────────────────────────────────
function KoperasiCard({ koperasi, onEdit, onManageStaff }) {
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 14,
      overflow: 'hidden',
      boxShadow: 'var(--shadow-xs)',
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 20px',
        background: 'linear-gradient(135deg, var(--primary-subtle) 0%, var(--surface-2) 100%)',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: 12,
      }}>
        <div>
          <div style={{ fontWeight: 800, color: 'var(--ink)', fontSize: '1rem', letterSpacing: '-0.01em' }}>
            {koperasi.name}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--muted)', marginTop: 3, display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{
              background: 'var(--primary-light)', color: 'var(--primary-text)',
              borderRadius: 4, padding: '1px 7px', fontSize: '0.6875rem', fontWeight: 700,
            }}>
              {koperasi.type}
            </span>
            <MapPinIcon />
            {koperasi.region}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
          <span className="badge badge-active">Aktif</span>
          <button className="btn btn-secondary btn-xs" onClick={() => onManageStaff(koperasi)} title="Kelola staff">
            <UsersIcon /> Staff
          </button>
          <button className="btn btn-secondary btn-xs" onClick={() => onEdit(koperasi)} title="Edit koperasi">
            <EditIcon /> Edit
          </button>
        </div>
      </div>

      {/* Body */}
      <div style={{ padding: '12px 20px 16px', display: 'flex', gap: 24, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Alamat</div>
          <div style={{ fontSize: '0.8125rem', color: 'var(--ink-2)', marginTop: 2 }}>{koperasi.address}</div>
        </div>
        <div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>ID Platform</div>
          <div style={{ fontSize: '0.8125rem', color: 'var(--ink-2)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>#{koperasi.id}</div>
        </div>
        <div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Terdaftar</div>
          <div style={{ fontSize: '0.8125rem', color: 'var(--ink-2)', marginTop: 2 }}>{formatDate(koperasi.created_at)}</div>
        </div>
        {koperasi.xendit_account_id && (
          <div>
            <div style={{ fontSize: '0.6875rem', color: 'var(--muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Xendit Account</div>
            <div style={{ fontSize: '0.8125rem', color: 'var(--ink-2)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>{koperasi.xendit_account_id}</div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Overview Tab ─────────────────────────────────────────────────────────────
function OverviewTab({ koperasiList }) {
  const total = koperasiList.length;
  const byType = koperasiList.reduce((acc, k) => { acc[k.type] = (acc[k.type] || 0) + 1; return acc; }, {});
  const byRegion = [...new Set(koperasiList.map(k => k.region))];

  return (
    <div className="section-gap-lg">
      <div className="stat-grid">
        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span className="stat-label">Total Koperasi</span>
            <div className="stat-icon" style={{ background: 'var(--primary-light)', color: 'var(--primary)' }}><GlobalIcon /></div>
          </div>
          <div className="stat-value">{total}</div>
          <div className="stat-sub">terdaftar di platform</div>
        </div>
        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span className="stat-label">Wilayah Tercakup</span>
            <div className="stat-icon" style={{ background: 'var(--info-bg)', color: 'var(--info)' }}><MapPinIcon /></div>
          </div>
          <div className="stat-value">{byRegion.length}</div>
          <div className="stat-sub">kota / kabupaten</div>
        </div>
        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span className="stat-label">KUD</span>
            <div className="stat-icon" style={{ background: 'var(--success-bg)', color: 'var(--success)' }}><HomeIcon /></div>
          </div>
          <div className="stat-value">{byType['KUD'] || 0}</div>
          <div className="stat-sub">koperasi unit desa</div>
        </div>
        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span className="stat-label">KSP / Pertanian</span>
            <div className="stat-icon" style={{ background: 'var(--warning-bg)', color: 'var(--warning)' }}><GlobalIcon /></div>
          </div>
          <div className="stat-value">{(byType['KSP'] || 0) + (byType['Koperasi Pertanian'] || 0)}</div>
          <div className="stat-sub">KSP + Koperasi Pertanian</div>
        </div>
      </div>

      {byRegion.length > 0 && (
        <Card title="Sebaran Wilayah">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {byRegion.map(r => (
              <div key={r} style={{
                background: 'var(--surface-2)', border: '1px solid var(--border)',
                borderRadius: 8, padding: '6px 14px', fontSize: '0.875rem',
                color: 'var(--ink-2)', fontWeight: 500, display: 'flex', alignItems: 'center', gap: 6,
              }}>
                <span style={{ color: 'var(--primary)', fontSize: '0.75rem' }}>●</span>
                {r}
                <span style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>
                  ({koperasiList.filter(k => k.region === r).length})
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {total === 0 && (
        <Alert type="info">Belum ada koperasi. Tambahkan koperasi pertama untuk memulai platform.</Alert>
      )}
    </div>
  );
}

// ─── Koperasi List Tab ────────────────────────────────────────────────────────
function KoperasiTab({ koperasiList, loading, onAdd, onEdit, onManageStaff }) {
  return (
    <div className="section-gap">
      <PageHeader
        title="Daftar Koperasi"
        desc={`${koperasiList.length} koperasi terdaftar di platform`}
        actions={
          <button className="btn btn-primary" onClick={onAdd}>
            <PlusIcon /> Tambah Koperasi
          </button>
        }
      />

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 80 }}><Spinner large /></div>
      ) : koperasiList.length === 0 ? (
        <EmptyState
          icon={<GlobalIcon />}
          title="Belum ada koperasi"
          desc="Tambahkan koperasi pertama ke platform untuk memulai."
          action={<button className="btn btn-primary" onClick={onAdd}><PlusIcon /> Tambah Koperasi</button>}
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {koperasiList.map(k => (
            <KoperasiCard key={k.id} koperasi={k} onEdit={onEdit} onManageStaff={onManageStaff} />
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────
export default function PlatformDashboard({ user, onLogout }) {
  const [activeTab, setActiveTab] = useState('overview');
  const [koperasiList, setKoperasiList] = useState([]);
  const [loading, setLoading] = useState(true);

  // Modal state
  const [showWizard, setShowWizard] = useState(false);
  const [editTarget, setEditTarget] = useState(null);
  const [staffTarget, setStaffTarget] = useState(null);

  const loadKoperasi = () => {
    setLoading(true);
    koperasiAPI.list()
      .then(r => setKoperasiList(r.data))
      .catch(err => toast.error(getErrorMessage(err)))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadKoperasi(); }, []);

  const handleWizardSuccess = (newKoperasi) => {
    setKoperasiList(prev => [newKoperasi, ...prev]);
    setShowWizard(false);
  };

  const handleEditSuccess = (updated) => {
    setKoperasiList(prev => prev.map(k => k.id === updated.id ? updated : k));
    setEditTarget(null);
  };

  const TABS_CFG = [
    { id: 'overview', label: 'Gambaran Umum', icon: <HomeIcon /> },
    { id: 'koperasi', label: 'Daftar Koperasi', icon: <GlobalIcon /> },
  ];

  const navItems = TABS_CFG.map(t => ({
    id: t.id, label: t.label, icon: t.icon,
    active: activeTab === t.id,
    onClick: () => setActiveTab(t.id),
  }));

  return (
    <AppShell user={user} onLogout={onLogout} navItems={navItems} topbarTitle="Platform Admin">
      <Tabs items={TABS_CFG} active={activeTab} onChange={setActiveTab} />

      {activeTab === 'overview' && <OverviewTab koperasiList={koperasiList} />}

      {activeTab === 'koperasi' && (
        <KoperasiTab
          koperasiList={koperasiList}
          loading={loading}
          onAdd={() => setShowWizard(true)}
          onEdit={setEditTarget}
          onManageStaff={setStaffTarget}
        />
      )}

      {showWizard && (
        <KoperasiCreateWizard
          onClose={() => setShowWizard(false)}
          onSuccess={handleWizardSuccess}
        />
      )}

      {editTarget && (
        <KoperasiEditModal
          koperasi={editTarget}
          onClose={() => setEditTarget(null)}
          onSuccess={handleEditSuccess}
        />
      )}

      {staffTarget && (
        <StaffModal
          koperasi={staffTarget}
          onClose={() => setStaffTarget(null)}
        />
      )}
    </AppShell>
  );
}
