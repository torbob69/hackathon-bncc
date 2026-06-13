import { useState, useEffect } from 'react';
import { authAPI } from '../api/client.js';
import { getErrorMessage } from '../components/ui.jsx';

export default function ActivatePage() {
  const [token, setToken] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const t = params.get('token');
    if (t) setToken(t);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!token.trim()) { setError('Token aktivasi tidak ditemukan.'); return; }
    if (password.length < 8) { setError('Kata sandi minimal 8 karakter.'); return; }
    if (password !== confirm) { setError('Kata sandi tidak cocok.'); return; }
    setLoading(true);
    setError('');
    try {
      await authAPI.activate(token.trim(), password);
      setDone(true);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg)', padding: 24 }}>
      <div style={{ width: '100%', maxWidth: 400, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 16, padding: 32, boxShadow: 'var(--shadow-md)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
          <div style={{ width: 40, height: 40, background: 'var(--primary)', borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 900, fontSize: '1.125rem', color: 'white', letterSpacing: '-0.03em' }}>KL</div>
          <div>
            <div style={{ fontWeight: 800, fontSize: '1rem', color: 'var(--ink)', letterSpacing: '-0.02em' }}>KOPERALINK</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>Aktivasi Akun</div>
          </div>
        </div>

        {done ? (
          <div style={{ textAlign: 'center', padding: '16px 0' }}>
            <div style={{ width: 56, height: 56, background: 'var(--success-bg)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px', color: 'var(--success)' }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="28" height="28">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
            <h2 style={{ marginBottom: 8, color: 'var(--ink)' }}>Akun Berhasil Diaktifkan!</h2>
            <p style={{ color: 'var(--muted)', marginBottom: 24 }}>Kata sandi Anda telah disetel. Silakan login dengan akun baru Anda.</p>
            <a href="/" className="btn btn-primary" style={{ display: 'inline-flex', justifyContent: 'center', width: '100%' }}>
              Masuk Sekarang
            </a>
          </div>
        ) : (
          <>
            <h2 style={{ marginBottom: 6 }}>Setel Kata Sandi</h2>
            <p style={{ color: 'var(--muted)', marginBottom: 24, fontSize: '0.875rem' }}>
              Buat kata sandi untuk mengaktifkan akun KOPERALINK Anda.
            </p>

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {!token && (
                <div className="form-group">
                  <label htmlFor="activate-token">Token Aktivasi</label>
                  <input id="activate-token" value={token} onChange={(e) => setToken(e.target.value)} placeholder="Token dari SMS/WA" required />
                </div>
              )}
              <div className="form-group">
                <label htmlFor="activate-password">Kata Sandi Baru <span style={{ color: 'var(--danger)' }}>*</span></label>
                <input id="activate-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Minimal 8 karakter" autoComplete="new-password" required />
              </div>
              <div className="form-group">
                <label htmlFor="activate-confirm">Konfirmasi Kata Sandi <span style={{ color: 'var(--danger)' }}>*</span></label>
                <input id="activate-confirm" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="Ulangi kata sandi" autoComplete="new-password" required />
              </div>

              {error && (
                <div className="alert alert-danger" style={{ padding: '10px 14px' }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: 15, height: 15, flexShrink: 0 }}><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                  <span>{error}</span>
                </div>
              )}

              <button id="activate-submit-btn" type="submit" className="btn btn-primary" disabled={loading} style={{ width: '100%', justifyContent: 'center', padding: '11px 16px' }}>
                {loading ? <><div className="spinner" />Memproses...</> : 'Aktifkan Akun'}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
