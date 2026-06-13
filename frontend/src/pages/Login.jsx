import { useState } from 'react';
import { authAPI } from '../api/client.js';
import { getErrorMessage } from '../components/ui';

// ─── Helpers ──────────────────────────────────────────────────────────────────
const looksLikeEmail = (s) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s.trim());
const looksLikePhone = (s) => /^[0-9+\-()\s]{6,}$/.test(s.trim());

function identifierHint(val) {
  if (!val) return null;
  if (looksLikeEmail(val)) return { label: 'Email terdeteksi', color: 'var(--success)' };
  if (looksLikePhone(val)) return { label: 'Nomor HP terdeteksi', color: 'var(--info)' };
  return null;
}

// ─── Eye icon toggle ──────────────────────────────────────────────────────────
function EyeToggle({ show, onToggle }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={show ? 'Sembunyikan kata sandi' : 'Tampilkan kata sandi'}
      style={{
        position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
        background: 'none', border: 'none', cursor: 'pointer',
        color: 'var(--muted)', padding: 4, display: 'flex', lineHeight: 0,
      }}
    >
      {show ? (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" width="16" height="16">
          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
          <line x1="1" y1="1" x2="23" y2="23"/>
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" width="16" height="16">
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
          <circle cx="12" cy="12" r="3"/>
        </svg>
      )}
    </button>
  );
}

// ─── Login form ───────────────────────────────────────────────────────────────
function LoginForm({ onLogin, onGoRegister }) {
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const hint = identifierHint(identifier);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!identifier.trim() || !password) {
      setError('Masukkan email / nomor HP dan kata sandi.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      await onLogin(identifier.trim(), password);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="login-form-title">Selamat datang</div>
      <div className="login-form-sub">Masuk menggunakan email atau nomor HP Anda</div>

      <form onSubmit={handleSubmit} id="login-form" style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 8 }}>
        <div className="form-group">
          <label htmlFor="login-identifier">Email atau Nomor HP</label>
          <input
            id="login-identifier"
            type="text"
            placeholder="email@domain.com atau 08123..."
            value={identifier}
            onChange={(e) => { setIdentifier(e.target.value); setError(''); }}
            autoComplete="username"
            autoFocus
          />
          {hint && (
            <div style={{ fontSize: '0.75rem', color: hint.color, marginTop: 4, fontWeight: 500 }}>
              ✓ {hint.label}
            </div>
          )}
        </div>

        <div className="form-group">
          <label htmlFor="login-password">Kata Sandi</label>
          <div style={{ position: 'relative' }}>
            <input
              id="login-password"
              type={showPass ? 'text' : 'password'}
              placeholder="••••••••"
              value={password}
              onChange={(e) => { setPassword(e.target.value); setError(''); }}
              autoComplete="current-password"
              style={{ paddingRight: 40 }}
            />
            <EyeToggle show={showPass} onToggle={() => setShowPass(v => !v)} />
          </div>
        </div>

        {error && (
          <div className="alert alert-danger" style={{ padding: '10px 14px' }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: 15, height: 15, flexShrink: 0, marginTop: 1 }}>
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span>{error}</span>
          </div>
        )}

        <button
          type="submit"
          id="login-submit-btn"
          className="btn btn-primary"
          style={{ width: '100%', justifyContent: 'center', padding: '11px 16px', fontSize: '0.9375rem', marginTop: 4 }}
          disabled={loading}
        >
          {loading ? <><div className="spinner" />Memproses...</> : 'Masuk'}
        </button>
      </form>

      <div style={{ position: 'relative', margin: '22px 0 18px', display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
        <span style={{ fontSize: '0.75rem', color: 'var(--muted)', fontWeight: 500, whiteSpace: 'nowrap' }}>atau</span>
        <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
      </div>

      <button
        className="btn btn-secondary"
        style={{ width: '100%', justifyContent: 'center', padding: '10px 16px' }}
        onClick={onGoRegister}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" width="16" height="16" style={{ flexShrink: 0 }}>
          <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>
          <circle cx="9" cy="7" r="4"/>
          <line x1="19" y1="8" x2="19" y2="14"/><line x1="22" y1="11" x2="16" y2="11"/>
        </svg>
        Daftar sebagai Distributor
      </button>

      <div style={{ textAlign: 'center', fontSize: '0.75rem', color: 'var(--muted)', marginTop: 14 }}>
        Punya kode aktivasi?{' '}
        <a href="/activate" style={{ color: 'var(--primary)', fontWeight: 600 }}>
          Aktivasi akun
        </a>
      </div>
    </>
  );
}

// ─── Register form (distributor only) ────────────────────────────────────────
function RegisterForm({ onBack, onSuccess }) {
  const [form, setForm] = useState({
    name: '', email: '', phone: '', company_name: '', address: '', password: '', confirm: '',
  });
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const set = (field) => (e) => { setForm(f => ({ ...f, [field]: e.target.value })); setError(''); };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!form.name.trim()) { setError('Nama lengkap wajib diisi.'); return; }
    if (!form.phone.trim()) { setError('Nomor HP wajib diisi.'); return; }
    if (!form.company_name.trim()) { setError('Nama perusahaan wajib diisi.'); return; }
    if (form.password.length < 8) { setError('Kata sandi minimal 8 karakter.'); return; }
    if (form.password !== form.confirm) { setError('Konfirmasi kata sandi tidak cocok.'); return; }

    setLoading(true);
    try {
      await authAPI.signupDistributor({
        name: form.name.trim(),
        phone: form.phone.trim(),
        email: form.email.trim() || undefined,
        company_name: form.company_name.trim(),
        address: form.address.trim() || undefined,
        password: form.password,
      });
      onSuccess({ phone: form.phone.trim(), email: form.email.trim() });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <button className="login-back" onClick={onBack}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="15 18 9 12 15 6"/>
        </svg>
        Kembali ke Login
      </button>

      <div className="login-form-title" style={{ marginTop: 4 }}>Daftar Distributor</div>
      <div className="login-form-sub">Buat akun untuk mengakses marketplace B2B koperasi</div>

      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
          background: 'oklch(0.48 0.18 240 / 0.08)',
          border: '1px solid oklch(0.48 0.18 240 / 0.25)',
          borderRadius: 8, marginTop: 8, marginBottom: 4,
        }}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="oklch(0.48 0.18 240)" strokeWidth="1.8" width="16" height="16" style={{ flexShrink: 0 }}>
          <rect x="1" y="3" width="15" height="13" rx="2"/>
          <polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/>
          <circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>
        </svg>
        <span style={{ fontSize: '0.8125rem', color: 'var(--ink-2)' }}>
          Khusus untuk <strong>pembeli/distributor</strong> komoditas pertanian.
        </span>
      </div>

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 10 }}>
        {error && (
          <div className="alert alert-danger" style={{ padding: '10px 14px' }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: 15, height: 15, flexShrink: 0, marginTop: 1 }}>
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span>{error}</span>
          </div>
        )}

        <div className="form-group">
          <label htmlFor="reg-name">Nama Lengkap <span style={{ color: 'var(--danger)' }}>*</span></label>
          <input id="reg-name" placeholder="Budi Santoso" value={form.name} onChange={set('name')} autoFocus />
        </div>

        <div className="form-group">
          <label htmlFor="reg-company">Nama Perusahaan <span style={{ color: 'var(--danger)' }}>*</span></label>
          <input id="reg-company" placeholder="PT. Distributor Nusantara" value={form.company_name} onChange={set('company_name')} />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div className="form-group">
            <label htmlFor="reg-phone">No. HP <span style={{ color: 'var(--danger)' }}>*</span></label>
            <input id="reg-phone" type="tel" placeholder="08123456789" value={form.phone} onChange={set('phone')} />
          </div>
          <div className="form-group">
            <label htmlFor="reg-email">Email</label>
            <input id="reg-email" type="email" placeholder="opsional" value={form.email} onChange={set('email')} />
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="reg-password">
            Kata Sandi <span style={{ color: 'var(--danger)' }}>*</span>
            <span style={{ fontSize: '0.6875rem', color: 'var(--muted)', fontWeight: 400, marginLeft: 6 }}>min. 8 karakter</span>
          </label>
          <div style={{ position: 'relative' }}>
            <input
              id="reg-password"
              type={showPass ? 'text' : 'password'}
              placeholder="••••••••"
              value={form.password}
              onChange={set('password')}
              autoComplete="new-password"
              style={{ paddingRight: 40 }}
            />
            <EyeToggle show={showPass} onToggle={() => setShowPass(v => !v)} />
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="reg-confirm">Konfirmasi Kata Sandi <span style={{ color: 'var(--danger)' }}>*</span></label>
          <input
            id="reg-confirm"
            type={showPass ? 'text' : 'password'}
            placeholder="••••••••"
            value={form.confirm}
            onChange={set('confirm')}
            autoComplete="new-password"
          />
          {form.confirm && form.password && (
            <div style={{
              fontSize: '0.75rem', marginTop: 4, fontWeight: 500,
              color: form.password === form.confirm ? 'var(--success)' : 'var(--danger)',
            }}>
              {form.password === form.confirm ? '✓ Kata sandi cocok' : '✗ Kata sandi tidak cocok'}
            </div>
          )}
        </div>

        <button
          type="submit"
          id="register-submit-btn"
          className="btn btn-primary"
          style={{ width: '100%', justifyContent: 'center', padding: '11px 16px', fontSize: '0.9375rem', marginTop: 4 }}
          disabled={loading}
        >
          {loading ? <><div className="spinner" />Mendaftarkan...</> : 'Buat Akun'}
        </button>
      </form>
    </>
  );
}

// ─── Success screen ───────────────────────────────────────────────────────────
function SuccessView({ credentials, onGoLogin }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20, textAlign: 'center', padding: '8px 0' }}>
      <div style={{
        width: 72, height: 72, borderRadius: '50%',
        background: 'var(--success-bg)', border: '2px solid var(--success-border)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <svg viewBox="0 0 24 24" fill="none" stroke="var(--success)" strokeWidth="2.5" width="36" height="36">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
      </div>

      <div>
        <div style={{ fontSize: '1.375rem', fontWeight: 800, color: 'var(--ink)', letterSpacing: '-0.02em', marginBottom: 8 }}>
          Pendaftaran Berhasil!
        </div>
        <div style={{ fontSize: '0.9375rem', color: 'var(--ink-2)', lineHeight: 1.6, maxWidth: '30ch', margin: '0 auto' }}>
          Akun distributor Anda telah dibuat. Silakan masuk menggunakan{' '}
          <strong>{credentials?.email ? 'email' : 'nomor HP'}</strong> dan kata sandi yang baru saja Anda buat.
        </div>
      </div>

      {credentials && (
        <div style={{
          background: 'var(--surface-2)', border: '1px solid var(--border)',
          borderRadius: 10, padding: '12px 20px', width: '100%',
          fontSize: '0.8125rem', color: 'var(--ink-2)',
        }}>
          <div style={{ fontWeight: 600, color: 'var(--muted)', fontSize: '0.6875rem', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
            Gunakan untuk login
          </div>
          {credentials.phone && (
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>No. HP</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--ink)' }}>
                {credentials.phone}
              </span>
            </div>
          )}
          {credentials.email && (
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
              <span>Email</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--ink)' }}>
                {credentials.email}
              </span>
            </div>
          )}
        </div>
      )}

      <button
        className="btn btn-primary"
        style={{ width: '100%', justifyContent: 'center', padding: '11px 16px', fontSize: '0.9375rem' }}
        onClick={onGoLogin}
        id="go-login-btn"
      >
        Masuk Sekarang
      </button>
    </div>
  );
}

// ─── Left panel ───────────────────────────────────────────────────────────────
function LeftPanel() {
  return (
    <div className="login-left">
      <div className="login-left-brand">
        <div className="login-left-mark">KL</div>
        <span className="login-left-name">KOPERALINK</span>
      </div>

      <div className="login-left-hero">
        <h1>Platform Digital Koperasi Tani Indonesia</h1>
        <p>
          Menggantikan pencatatan Excel yang rentan kesalahan dengan sistem pencatatan digital yang aman, transparan, dan terintegrasi.
        </p>
      </div>

      <div className="login-left-stats">
        <div className="login-left-stat">
          <div className="login-left-stat-val">PIHPS</div>
          <div className="login-left-stat-label">Harga acuan anti-manipulasi</div>
        </div>
        <div className="login-left-stat">
          <div className="login-left-stat-val">B2B</div>
          <div className="login-left-stat-label">Marketplace multi-koperasi</div>
        </div>
        <div className="login-left-stat">
          <div className="login-left-stat-val">KSP</div>
          <div className="login-left-stat-label">Pinjaman anggota berbasis data</div>
        </div>
        <div className="login-left-stat">
          <div className="login-left-stat-val">Audit</div>
          <div className="login-left-stat-label">Jejak audit anti-fraud</div>
        </div>
      </div>
    </div>
  );
}

// ─── Main export ──────────────────────────────────────────────────────────────
export default function LoginPage({ onLogin }) {
  const [mode, setMode] = useState('login'); // 'login' | 'register' | 'success'
  const [successCreds, setSuccessCreds] = useState(null);

  const handleSuccess = (creds) => {
    setSuccessCreds(creds);
    setMode('success');
  };

  const goLogin = () => setMode('login');

  return (
    <div className="login-page">
      <LeftPanel />

      <div className="login-right">
        <div className="login-form-wrap">
          {mode === 'login' && (
            <LoginForm
              onLogin={onLogin}
              onGoRegister={() => setMode('register')}
            />
          )}
          {mode === 'register' && (
            <RegisterForm
              onBack={goLogin}
              onSuccess={handleSuccess}
            />
          )}
          {mode === 'success' && (
            <SuccessView
              credentials={successCreds}
              onGoLogin={goLogin}
            />
          )}
        </div>
      </div>
    </div>
  );
}
