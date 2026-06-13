import { useState, useEffect, useCallback } from 'react';
import AppShell from '../components/AppShell.jsx';
import {
  Money, StatusBadge, formatDate, formatDateTime,
  Weight, Spinner, EmptyState, PageHeader, Modal,
  Card, Alert, Tabs, FormGroup, Skeleton, getErrorMessage,
} from '../components/ui.jsx';
import { intakesAPI, loansAPI, commoditiesAPI } from '../api/client.js';
import { toast } from '../hooks/useToast.jsx';

// ─── Icons ───────────────────────────────────────────────────────────────────

function HomeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  );
}

function PackageIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <line x1="16.5" y1="9.4" x2="7.5" y2="4.21" />
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
      <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
      <line x1="12" y1="22.08" x2="12" y2="12" />
    </svg>
  );
}

function CreditCardIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
      <line x1="1" y1="10" x2="23" y2="10" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function RefreshIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="23 4 23 10 17 10" />
      <polyline points="1 20 1 14 7 14" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
    </svg>
  );
}

function QrIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="3" y="3" width="5" height="5" />
      <rect x="16" y="3" width="5" height="5" />
      <rect x="3" y="16" width="5" height="5" />
      <path d="M21 16h-3a2 2 0 0 0-2 2v3" />
      <line x1="21" y1="21" x2="21" y2="21" />
      <path d="M3 11h3" />
      <path d="M12 3v3" />
      <path d="M12 8v2" />
      <path d="M12 14v3" />
      <path d="M16 11h5" />
    </svg>
  );
}

function EyeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

// ─── Credit Tier Badge ────────────────────────────────────────────────────────

function CreditTierBadge({ tier }) {
  if (!tier) return <span className="badge badge-default">—</span>;
  return <span className={`credit-tier ${tier}`}>{tier}</span>;
}

// ─── QR Token Display ─────────────────────────────────────────────────────────

function QRBox({ token }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(token).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="qr-box" style={{ maxWidth: 300, margin: '0 auto' }}>
      {/* Simulated QR pattern derived from token */}
      <div
        style={{
          width: 160,
          height: 160,
          background: 'white',
          borderRadius: 8,
          display: 'grid',
          gridTemplateColumns: 'repeat(8, 1fr)',
          gap: 2,
          padding: 10,
          border: '1px solid var(--border)',
        }}
      >
        {Array.from({ length: 64 }, (_, i) => {
          const seed = (token.charCodeAt(i % token.length) * (i + 7)) % 11;
          const on = seed < 6;
          return (
            <div
              key={i}
              style={{
                background: on ? '#111' : 'transparent',
                borderRadius: 1,
              }}
            />
          );
        })}
      </div>

      <div style={{ textAlign: 'center', width: '100%' }}>
        <div
          style={{
            fontSize: '0.6875rem',
            color: 'var(--muted)',
            marginBottom: 6,
            fontWeight: 600,
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
          }}
        >
          Token QR
        </div>
        <div
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.8125rem',
            color: 'var(--ink)',
            background: 'var(--surface-2)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            padding: '6px 10px',
            wordBreak: 'break-all',
            letterSpacing: '0.04em',
          }}
        >
          {token}
        </div>
        <button
          className="btn btn-secondary btn-sm"
          style={{ marginTop: 10, width: '100%', justifyContent: 'center' }}
          onClick={handleCopy}
        >
          {copied ? '✓ Disalin!' : 'Salin Token'}
        </button>
        <p
          style={{
            fontSize: '0.75rem',
            color: 'var(--muted)',
            marginTop: 8,
            maxWidth: '28ch',
            margin: '8px auto 0',
          }}
        >
          Tunjukkan token ini ke petugas gudang untuk verifikasi setoran.
        </p>
      </div>
    </div>
  );
}

// ─── Dashboard Tab ────────────────────────────────────────────────────────────

function DashboardTab({ intakes, loans, loadingIntakes, loadingLoans }) {
  const pendingIntakes = intakes.filter((i) => i.status === 'pending').length;
  const confirmedIntakes = intakes.filter((i) => i.status === 'confirmed').length;
  const activeLoans = loans.filter((l) => l.status === 'active').length;

  const latestLoanWithScore = loans.find(
    (l) => l.credit_score != null || l.credit_tier != null
  );
  const creditTier = latestLoanWithScore?.credit_tier ?? null;
  const creditScore = latestLoanWithScore?.credit_score ?? null;

  const totalEstimated = intakes.reduce(
    (sum, i) => sum + parseFloat(i.estimated_value || 0),
    0
  );
  const totalPaid = intakes.reduce(
    (sum, i) => sum + parseFloat(i.total_paid || 0),
    0
  );

  return (
    <div className="section-gap-lg">
      {/* ── Stat Cards ── */}
      <div className="stat-grid">
        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span className="stat-label">Setoran Menunggu</span>
            <div className="stat-icon" style={{ background: 'var(--warning-bg)', color: 'var(--warning)' }}>
              <PackageIcon />
            </div>
          </div>
          {loadingIntakes ? (
            <Skeleton height={32} width="60px" />
          ) : (
            <div className="stat-value">{pendingIntakes}</div>
          )}
          <div className="stat-sub">{confirmedIntakes} dikonfirmasi</div>
        </div>

        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span className="stat-label">Pinjaman Aktif</span>
            <div className="stat-icon" style={{ background: 'var(--info-bg)', color: 'var(--info)' }}>
              <CreditCardIcon />
            </div>
          </div>
          {loadingLoans ? (
            <Skeleton height={32} width="60px" />
          ) : (
            <div className="stat-value">{activeLoans}</div>
          )}
          <div className="stat-sub">dari {loans.length} total</div>
        </div>

        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span className="stat-label">Estimasi Nilai Panen</span>
            <div className="stat-icon" style={{ background: 'var(--success-bg)', color: 'var(--success)' }}>
              <HomeIcon />
            </div>
          </div>
          {loadingIntakes ? (
            <Skeleton height={32} width="130px" />
          ) : (
            <div className="stat-value" style={{ fontSize: '1.25rem' }}>
              <Money value={totalEstimated} />
            </div>
          )}
          <div className="stat-sub">
            Dibayar: <Money value={totalPaid} />
          </div>
        </div>

        <div className="stat-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span className="stat-label">Tier Kredit</span>
            <div className="stat-icon" style={{ background: 'var(--primary-light)', color: 'var(--primary)' }}>
              <CreditCardIcon />
            </div>
          </div>
          {loadingLoans ? (
            <Skeleton height={32} width="60px" />
          ) : creditTier ? (
            <div style={{ marginTop: 4 }}>
              <CreditTierBadge tier={creditTier} />
            </div>
          ) : (
            <div className="stat-value" style={{ color: 'var(--muted)' }}>—</div>
          )}
          <div className="stat-sub">
            {creditScore != null ? `Skor: ${creditScore}` : 'Belum ada riwayat'}
          </div>
        </div>
      </div>

      {/* ── Recent Intakes ── */}
      <Card title="Setoran Terbaru">
        {loadingIntakes ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[1, 2, 3].map((i) => <Skeleton key={i} height={20} />)}
          </div>
        ) : intakes.length === 0 ? (
          <EmptyState
            icon={<PackageIcon />}
            title="Belum ada setoran"
            desc="Buat setoran panen pertama Anda di tab Setoran Panen."
          />
        ) : (
          <div className="table-wrap" style={{ border: 'none', boxShadow: 'none', borderRadius: 8 }}>
            <table>
              <thead>
                <tr>
                  <th>Tanggal</th>
                  <th>Komoditas</th>
                  <th>Berat</th>
                  <th>Estimasi Nilai</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {intakes.slice(0, 5).map((intake) => (
                  <tr key={intake.id}>
                    <td className="td-muted td-mono">{formatDate(intake.created_at)}</td>
                    <td className="td-primary">
                      {intake.commodity_name || `Komoditas #${intake.commodity_id}`}
                    </td>
                    <td><Weight value={intake.weight_kg} /></td>
                    <td>
                      {intake.estimated_value
                        ? <Money value={intake.estimated_value} />
                        : <span className="td-muted">—</span>}
                    </td>
                    <td><StatusBadge status={intake.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* ── Recent Loans ── */}
      <Card title="Pinjaman Terbaru">
        {loadingLoans ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[1, 2].map((i) => <Skeleton key={i} height={20} />)}
          </div>
        ) : loans.length === 0 ? (
          <EmptyState
            icon={<CreditCardIcon />}
            title="Belum ada pinjaman"
            desc="Ajukan pinjaman di tab Pinjaman."
          />
        ) : (
          <div className="table-wrap" style={{ border: 'none', boxShadow: 'none', borderRadius: 8 }}>
            <table>
              <thead>
                <tr>
                  <th>Tanggal</th>
                  <th>Tujuan</th>
                  <th>Pokok</th>
                  <th>Tenor</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {loans.slice(0, 5).map((loan) => (
                  <tr key={loan.id}>
                    <td className="td-muted td-mono">{formatDate(loan.created_at)}</td>
                    <td className="td-primary" style={{ textTransform: 'capitalize' }}>{loan.purpose}</td>
                    <td><Money value={loan.principal} /></td>
                    <td>{loan.installment_months} bulan</td>
                    <td><StatusBadge status={loan.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

// ─── Setoran Panen Tab ────────────────────────────────────────────────────────

function IntakesTab({ intakes, loading, onRefresh }) {
  const [showForm, setShowForm] = useState(false);
  const [commodities, setCommodities] = useState([]);
  const [loadingCommodities, setLoadingCommodities] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  const [commodityId, setCommodityId] = useState('');
  const [weightKg, setWeightKg] = useState('');

  const [qrIntake, setQrIntake] = useState(null);

  useEffect(() => {
    if (!showForm) return;
    setLoadingCommodities(true);
    commoditiesAPI
      .list()
      .then((r) => setCommodities(Array.isArray(r.data) ? r.data : []))
      .catch(() => toast.error('Gagal memuat daftar komoditas.'))
      .finally(() => setLoadingCommodities(false));
  }, [showForm]);

  const selectedCommodity = commodities.find(
    (c) => String(c.id) === String(commodityId)
  );
  const estimatedValue =
    selectedCommodity && weightKg > 0
      ? parseFloat(selectedCommodity.pihps_price) * parseFloat(weightKg)
      : null;

  const resetForm = () => {
    setCommodityId('');
    setWeightKg('');
    setFormError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');

    if (!commodityId) {
      setFormError('Pilih komoditas terlebih dahulu.');
      return;
    }
    const w = parseFloat(weightKg);
    if (!w || w <= 0) {
      setFormError('Berat harus lebih dari 0 kg.');
      return;
    }

    setSubmitting(true);
    try {
      await intakesAPI.create({ commodity_id: Number(commodityId), weight_kg: w });
      toast.success('Setoran panen berhasil dibuat!');
      setShowForm(false);
      resetForm();
      onRefresh();
    } catch (err) {
      setFormError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="section-gap">
      <PageHeader
        title="Setoran Panen"
        desc="Daftarkan hasil panen Anda dan pantau status konfirmasi dari petugas."
        actions={
          <button className="btn btn-primary" onClick={() => setShowForm(true)}>
            <PlusIcon />
            Buat Setoran
          </button>
        }
      />

      {/* ── Create Intake Modal ── */}
      <Modal
        open={showForm}
        onClose={() => { setShowForm(false); resetForm(); }}
        title="Buat Setoran Panen"
        footer={
          <>
            <button
              className="btn btn-secondary"
              onClick={() => { setShowForm(false); resetForm(); }}
              disabled={submitting}
            >
              Batal
            </button>
            <button
              className="btn btn-primary"
              onClick={handleSubmit}
              disabled={submitting || loadingCommodities}
            >
              {submitting && <Spinner />}
              {submitting ? 'Menyimpan...' : 'Buat Setoran'}
            </button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          {formError && <Alert type="danger">{formError}</Alert>}

          <FormGroup label="Komoditas" required>
            {loadingCommodities ? (
              <Skeleton height={40} />
            ) : (
              <select
                value={commodityId}
                onChange={(e) => setCommodityId(e.target.value)}
              >
                <option value="">— Pilih komoditas —</option>
                {commodities.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} — Rp {Number(c.pihps_price).toLocaleString('id-ID')}/{c.unit}
                  </option>
                ))}
              </select>
            )}
          </FormGroup>

          <FormGroup
            label="Berat (kg)"
            required
            hint={
              estimatedValue != null
                ? `Estimasi nilai: Rp ${Math.round(estimatedValue).toLocaleString('id-ID')}`
                : 'Isi berat untuk melihat estimasi nilai berdasarkan harga PIHPS.'
            }
          >
            <input
              type="number"
              min="0.001"
              step="0.001"
              placeholder="mis. 150.5"
              value={weightKg}
              onChange={(e) => setWeightKg(e.target.value)}
            />
          </FormGroup>

          {selectedCommodity && (
            <div
              style={{
                background: 'var(--info-bg)',
                border: '1px solid var(--info-border)',
                borderRadius: 8,
                padding: '10px 14px',
                fontSize: '0.8125rem',
                color: 'var(--info)',
              }}
            >
              <strong>{selectedCommodity.name}</strong> — Harga PIHPS:{' '}
              <strong>
                Rp {Number(selectedCommodity.pihps_price).toLocaleString('id-ID')}/
                {selectedCommodity.unit}
              </strong>
              {selectedCommodity.current_stock_kg != null && (
                <>
                  {' '}·{' '}Stok koperasi:{' '}
                  <Weight value={selectedCommodity.current_stock_kg} />
                </>
              )}
            </div>
          )}
        </div>
      </Modal>

      {/* ── QR Code Modal ── */}
      <Modal
        open={!!qrIntake}
        onClose={() => setQrIntake(null)}
        title="Token QR Setoran"
      >
        {qrIntake && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, alignItems: 'center' }}>
            <Alert type="success">
              Setoran dikonfirmasi. Tunjukkan token ini ke petugas gudang.
            </Alert>
            <QRBox token={qrIntake.qr_token} />
            <div
              style={{
                width: '100%',
                fontSize: '0.8125rem',
                color: 'var(--muted)',
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
              }}
            >
              <div>
                <span style={{ fontWeight: 600, color: 'var(--ink-2)' }}>Tanggal:</span>{' '}
                {formatDateTime(qrIntake.created_at)}
              </div>
              <div>
                <span style={{ fontWeight: 600, color: 'var(--ink-2)' }}>Berat:</span>{' '}
                <Weight value={qrIntake.weight_kg} />
              </div>
              {qrIntake.estimated_value && (
                <div>
                  <span style={{ fontWeight: 600, color: 'var(--ink-2)' }}>Nilai Estimasi:</span>{' '}
                  <Money value={qrIntake.estimated_value} />
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>

      {/* ── Intakes Table ── */}
      {loading ? (
        <Card>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {[1, 2, 3, 4].map((i) => <Skeleton key={i} height={22} />)}
          </div>
        </Card>
      ) : intakes.length === 0 ? (
        <EmptyState
          icon={<PackageIcon />}
          title="Belum ada setoran panen"
          desc="Buat setoran baru untuk mendaftarkan hasil panen Anda."
          action={
            <button className="btn btn-primary" onClick={() => setShowForm(true)}>
              <PlusIcon />
              Buat Setoran
            </button>
          }
        />
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Tanggal</th>
                <th>Komoditas</th>
                <th>Berat</th>
                <th>Harga/kg</th>
                <th>Estimasi Nilai</th>
                <th>Sudah Dibayar</th>
                <th>Status</th>
                <th>Aksi</th>
              </tr>
            </thead>
            <tbody>
              {intakes.map((intake) => (
                <tr key={intake.id}>
                  <td className="td-muted td-mono">{formatDate(intake.created_at)}</td>
                  <td className="td-primary">
                    {intake.commodity_name || `Komoditas #${intake.commodity_id}`}
                  </td>
                  <td><Weight value={intake.weight_kg} /></td>
                  <td className="td-mono">
                    {intake.price_per_kg
                      ? <Money value={intake.price_per_kg} />
                      : <span className="td-muted">—</span>}
                  </td>
                  <td className="td-mono">
                    {intake.estimated_value
                      ? <Money value={intake.estimated_value} />
                      : <span className="td-muted">—</span>}
                  </td>
                  <td className="td-mono">
                    {intake.total_paid
                      ? <Money value={intake.total_paid} />
                      : <span className="td-muted">—</span>}
                  </td>
                  <td><StatusBadge status={intake.status} /></td>
                  <td>
                    {intake.status === 'confirmed' && intake.qr_token ? (
                      <button
                        className="btn btn-secondary btn-xs"
                        onClick={() => setQrIntake(intake)}
                        title="Lihat Token QR"
                      >
                        <QrIcon />
                        QR
                      </button>
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

// ─── Loan Detail Modal ────────────────────────────────────────────────────────

function LoanDetailModal({ loan, open, onClose, onRepaid }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState('');

  const [repayingId, setRepayingId] = useState(null);
  const [repayAmount, setRepayAmount] = useState('');
  const [repayError, setRepayError] = useState('');
  const [repaySubmitting, setRepaySubmitting] = useState(false);

  const loadDetail = useCallback(async () => {
    if (!loan) return;
    setLoading(true);
    setFetchError('');
    try {
      const r = await loansAPI.get(loan.id);
      setDetail(r.data);
    } catch (err) {
      setFetchError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [loan]);

  useEffect(() => {
    if (open && loan) {
      setDetail(null);
      setRepayingId(null);
      setRepayAmount('');
      setRepayError('');
      loadDetail();
    }
  }, [open, loan, loadDetail]);

  const handleRepay = async (inst) => {
    setRepayError('');
    const amount = parseFloat(repayAmount);
    if (!amount || amount <= 0) {
      setRepayError('Masukkan jumlah pembayaran yang valid.');
      return;
    }
    setRepaySubmitting(true);
    try {
      await loansAPI.repay(loan.id, inst.id, amount);
      toast.success('Angsuran berhasil dibayar!');
      setRepayingId(null);
      setRepayAmount('');
      await loadDetail();
      onRepaid?.();
    } catch (err) {
      setRepayError(getErrorMessage(err));
    } finally {
      setRepaySubmitting(false);
    }
  };

  const handleClose = () => {
    onClose();
    setRepayingId(null);
    setRepayAmount('');
    setRepayError('');
  };

  const installments = detail?.installments || [];
  const paidCount = installments.filter((i) => i.status === 'paid').length;
  const creditScore = detail?.latest_credit_score;

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title={
        loan
          ? `Detail Pinjaman — ${loan.purpose.charAt(0).toUpperCase()}${loan.purpose.slice(1)}`
          : 'Detail Pinjaman'
      }
    >
      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
          <Spinner large />
        </div>
      ) : fetchError ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Alert type="danger">{fetchError}</Alert>
          <button className="btn btn-secondary btn-sm" onClick={loadDetail}>
            <RefreshIcon />
            Coba Lagi
          </button>
        </div>
      ) : detail ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Summary grid */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: 12,
              background: 'var(--surface-2)',
              borderRadius: 10,
              padding: 16,
            }}
          >
            {[
              { label: 'Pokok Pinjaman', value: <Money value={detail.loan.principal} /> },
              { label: 'Status', value: <StatusBadge status={detail.loan.status} /> },
              { label: 'Bunga/Tahun', value: `${detail.loan.interest_rate}%` },
              { label: 'Tenor', value: `${detail.loan.installment_months} bulan` },
              { label: 'Tujuan', value: detail.loan.purpose },
              { label: 'Tanggal Pengajuan', value: formatDate(detail.loan.created_at) },
              ...(creditScore
                ? [
                    { label: 'Skor Kredit', value: creditScore.score },
                    { label: 'Tier Kredit', value: <CreditTierBadge tier={creditScore.tier} /> },
                  ]
                : []),
            ].map(({ label, value }) => (
              <div key={label}>
                <div style={{ fontSize: '0.75rem', color: 'var(--muted)', fontWeight: 500 }}>
                  {label}
                </div>
                <div style={{ fontWeight: 600, color: 'var(--ink)', fontSize: '0.875rem', marginTop: 2 }}>
                  {value}
                </div>
              </div>
            ))}
          </div>

          {/* Installment progress bar */}
          {installments.length > 0 && (
            <div>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  marginBottom: 6,
                  fontSize: '0.8125rem',
                }}
              >
                <span style={{ fontWeight: 600, color: 'var(--ink-2)' }}>Progres Angsuran</span>
                <span style={{ color: 'var(--muted)' }}>
                  {paidCount}/{installments.length} lunas
                </span>
              </div>
              <div className="progress-bar">
                <div
                  className="progress-bar-fill green"
                  style={{
                    width: `${installments.length > 0 ? (paidCount / installments.length) * 100 : 0}%`,
                  }}
                />
              </div>
            </div>
          )}

          {repayError && <Alert type="danger">{repayError}</Alert>}

          {/* Installment schedule */}
          <div>
            <div
              style={{
                fontWeight: 700,
                color: 'var(--ink)',
                fontSize: '0.9375rem',
                marginBottom: 12,
              }}
            >
              Jadwal Angsuran
            </div>

            {installments.length === 0 ? (
              <p style={{ color: 'var(--muted)', fontSize: '0.875rem' }}>
                Belum ada jadwal angsuran yang tersedia.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {installments.map((inst, idx) => {
                  const isPaid = inst.status === 'paid';
                  const isPastDue = inst.status === 'past_due';
                  const canRepay =
                    !isPaid &&
                    detail.loan.status === 'active' &&
                    repayingId !== inst.id;
                  const isRepaying = repayingId === inst.id;

                  return (
                    <div
                      key={inst.id}
                      style={{
                        border: `1px solid ${
                          isPaid
                            ? 'var(--success-border)'
                            : isPastDue
                            ? 'var(--danger-border)'
                            : 'var(--border)'
                        }`,
                        borderRadius: 8,
                        padding: '12px 14px',
                        background: isPaid
                          ? 'var(--success-bg)'
                          : isPastDue
                          ? 'var(--danger-bg)'
                          : 'var(--surface)',
                      }}
                    >
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          flexWrap: 'wrap',
                          gap: 8,
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          {/* Installment number circle */}
                          <span
                            style={{
                              width: 24,
                              height: 24,
                              borderRadius: '50%',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontSize: '0.6875rem',
                              fontWeight: 700,
                              flexShrink: 0,
                              background: isPaid
                                ? 'var(--success)'
                                : isPastDue
                                ? 'var(--danger)'
                                : 'var(--surface-3)',
                              color:
                                isPaid || isPastDue ? 'white' : 'var(--muted)',
                            }}
                          >
                            {idx + 1}
                          </span>
                          <div>
                            <div
                              style={{
                                fontWeight: 600,
                                color: 'var(--ink)',
                                fontSize: '0.875rem',
                              }}
                            >
                              <Money value={inst.amount_due} />
                            </div>
                            <div
                              style={{
                                fontSize: '0.75rem',
                                color: 'var(--muted)',
                                fontFamily: 'var(--font-mono)',
                              }}
                            >
                              Jatuh tempo: {formatDate(inst.due_date)}
                            </div>
                          </div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <StatusBadge status={inst.status} />
                          {canRepay && (
                            <button
                              className="btn btn-success btn-xs"
                              onClick={() => {
                                setRepayingId(inst.id);
                                setRepayAmount(String(inst.amount_due));
                                setRepayError('');
                              }}
                            >
                              Bayar
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Paid amount shown */}
                      {isPaid && inst.amount_paid != null && (
                        <div
                          style={{
                            marginTop: 6,
                            fontSize: '0.75rem',
                            color: 'var(--success)',
                            fontWeight: 500,
                          }}
                        >
                          ✓ Dibayar: <Money value={inst.amount_paid} />
                        </div>
                      )}

                      {/* Inline repay form */}
                      {isRepaying && (
                        <div
                          style={{
                            marginTop: 12,
                            padding: '12px 14px',
                            background: 'var(--surface)',
                            border: '1px solid var(--border)',
                            borderRadius: 8,
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 10,
                          }}
                        >
                          <FormGroup
                            label="Jumlah Bayar (Rp)"
                            hint={`Tagihan: Rp ${Number(inst.amount_due).toLocaleString('id-ID')}`}
                          >
                            <input
                              type="number"
                              min="1"
                              step="1"
                              value={repayAmount}
                              onChange={(e) => setRepayAmount(e.target.value)}
                            />
                          </FormGroup>
                          <div
                            style={{
                              display: 'flex',
                              gap: 8,
                              justifyContent: 'flex-end',
                            }}
                          >
                            <button
                              className="btn btn-ghost btn-sm"
                              onClick={() => {
                                setRepayingId(null);
                                setRepayAmount('');
                                setRepayError('');
                              }}
                              disabled={repaySubmitting}
                            >
                              Batal
                            </button>
                            <button
                              className="btn btn-primary btn-sm"
                              onClick={() => handleRepay(inst)}
                              disabled={repaySubmitting}
                            >
                              {repaySubmitting && <Spinner />}
                              {repaySubmitting ? 'Memproses...' : 'Konfirmasi Bayar'}
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      ) : null}
    </Modal>
  );
}

// ─── Loans Tab ────────────────────────────────────────────────────────────────

const PURPOSE_OPTIONS = [
  { value: 'benih', label: 'Benih' },
  { value: 'pupuk', label: 'Pupuk' },
  { value: 'alat', label: 'Alat Pertanian' },
];

const TENOR_OPTIONS = [3, 6, 9, 12, 18, 24, 36, 48, 60];

const STATUS_FILTERS = [
  { value: 'all', label: 'Semua' },
  { value: 'pending', label: 'Menunggu' },
  { value: 'active', label: 'Aktif' },
  { value: 'paid', label: 'Lunas' },
  { value: 'rejected', label: 'Ditolak' },
  { value: 'seized', label: 'Disita' },
];

function LoanCard({ loan, onViewDetail }) {
  return (
    <div className="pool-card">
      <div className="pool-header">
        <div>
          <div className="pool-label" style={{ textTransform: 'capitalize' }}>
            {loan.purpose}
          </div>
          <div className="pool-amount">
            <Money value={loan.principal} />
          </div>
        </div>
        <StatusBadge status={loan.status} />
      </div>

      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: '0.75rem', color: 'var(--muted)', fontWeight: 500 }}>
            Tenor
          </div>
          <div style={{ fontWeight: 600, color: 'var(--ink)', fontSize: '0.875rem' }}>
            {loan.installment_months} bulan
          </div>
        </div>
        <div>
          <div style={{ fontSize: '0.75rem', color: 'var(--muted)', fontWeight: 500 }}>
            Bunga/Tahun
          </div>
          <div style={{ fontWeight: 600, color: 'var(--ink)', fontSize: '0.875rem' }}>
            {loan.interest_rate}%
          </div>
        </div>
        {loan.credit_score != null && (
          <div>
            <div style={{ fontSize: '0.75rem', color: 'var(--muted)', fontWeight: 500 }}>
              Skor Kredit
            </div>
            <div style={{ fontWeight: 600, color: 'var(--ink)', fontSize: '0.875rem' }}>
              {loan.credit_score}
            </div>
          </div>
        )}
        <div>
          <div style={{ fontSize: '0.75rem', color: 'var(--muted)', fontWeight: 500 }}>
            Tanggal Pengajuan
          </div>
          <div style={{ fontWeight: 600, color: 'var(--ink)', fontSize: '0.875rem' }}>
            {formatDate(loan.created_at)}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
        <button className="btn btn-secondary btn-sm" onClick={() => onViewDetail(loan)}>
          <EyeIcon />
          Detail &amp; Angsuran
        </button>
      </div>
    </div>
  );
}

function LoansTab({ loans, loading, onRefresh }) {
  const [showApplyForm, setShowApplyForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  const [principal, setPrincipal] = useState('');
  const [purpose, setPurpose] = useState('benih');
  const [installmentMonths, setInstallmentMonths] = useState('6');
  const INTEREST_RATE = 12; // fixed per spec

  const [filterStatus, setFilterStatus] = useState('all');

  const [detailLoan, setDetailLoan] = useState(null);
  const [showDetail, setShowDetail] = useState(false);

  const filteredLoans =
    filterStatus === 'all'
      ? loans
      : loans.filter((l) => l.status === filterStatus);

  const resetForm = () => {
    setPrincipal('');
    setPurpose('benih');
    setInstallmentMonths('6');
    setFormError('');
  };

  // Monthly installment estimate (annuity formula)
  const monthlyEstimate = (() => {
    const p = parseFloat(principal);
    const m = parseInt(installmentMonths, 10);
    if (!p || !m || p <= 0 || m <= 0) return null;
    const r = INTEREST_RATE / 100 / 12;
    if (r === 0) return p / m;
    return (p * r * Math.pow(1 + r, m)) / (Math.pow(1 + r, m) - 1);
  })();

  const handleApply = async (e) => {
    e.preventDefault();
    setFormError('');
    const p = parseFloat(principal);
    if (!p || p <= 0) {
      setFormError('Masukkan jumlah pokok pinjaman yang valid.');
      return;
    }
    const m = parseInt(installmentMonths, 10);
    if (!m || m < 1 || m > 60) {
      setFormError('Tenor harus antara 1–60 bulan.');
      return;
    }
    setSubmitting(true);
    try {
      await loansAPI.apply({
        principal: p,
        purpose,
        installment_months: m,
        interest_rate: INTEREST_RATE,
      });
      toast.success('Pengajuan pinjaman berhasil dikirim! Menunggu persetujuan.');
      setShowApplyForm(false);
      resetForm();
      onRefresh();
    } catch (err) {
      setFormError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="section-gap">
      <PageHeader
        title="Pinjaman"
        desc="Ajukan pinjaman untuk kebutuhan pertanian dan pantau jadwal angsuran."
        actions={
          <button className="btn btn-primary" onClick={() => setShowApplyForm(true)}>
            <PlusIcon />
            Ajukan Pinjaman
          </button>
        }
      />

      {/* ── Apply Loan Modal ── */}
      <Modal
        open={showApplyForm}
        onClose={() => { setShowApplyForm(false); resetForm(); }}
        title="Ajukan Pinjaman"
        footer={
          <>
            <button
              className="btn btn-secondary"
              onClick={() => { setShowApplyForm(false); resetForm(); }}
              disabled={submitting}
            >
              Batal
            </button>
            <button
              className="btn btn-primary"
              onClick={handleApply}
              disabled={submitting}
            >
              {submitting && <Spinner />}
              {submitting ? 'Mengajukan...' : 'Ajukan Pinjaman'}
            </button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          {formError && <Alert type="danger">{formError}</Alert>}

          <Alert type="info">
            Bunga pinjaman ditetapkan{' '}
            <strong>{INTEREST_RATE}%/tahun</strong> dengan skema angsuran tetap
            (flat annuity). Pengajuan akan ditinjau oleh admin koperasi.
          </Alert>

          <FormGroup label="Jumlah Pinjaman (Rp)" required>
            <input
              type="number"
              min="100000"
              step="50000"
              placeholder="mis. 5.000.000"
              value={principal}
              onChange={(e) => setPrincipal(e.target.value)}
            />
          </FormGroup>

          <FormGroup label="Tujuan Pinjaman" required>
            <select value={purpose} onChange={(e) => setPurpose(e.target.value)}>
              {PURPOSE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </FormGroup>

          <FormGroup
            label="Tenor (bulan)"
            required
            hint={
              monthlyEstimate != null
                ? `Estimasi angsuran/bulan: Rp ${Math.round(monthlyEstimate).toLocaleString('id-ID')}`
                : 'Isi jumlah pinjaman untuk melihat estimasi angsuran.'
            }
          >
            <select
              value={installmentMonths}
              onChange={(e) => setInstallmentMonths(e.target.value)}
            >
              {TENOR_OPTIONS.map((m) => (
                <option key={m} value={m}>
                  {m} bulan
                </option>
              ))}
            </select>
          </FormGroup>

          {monthlyEstimate != null && (
            <div
              style={{
                background: 'var(--success-bg)',
                border: '1px solid var(--success-border)',
                borderRadius: 8,
                padding: '10px 14px',
                fontSize: '0.8125rem',
                color: 'var(--success)',
              }}
            >
              <strong>Ringkasan:</strong> Pinjaman{' '}
              <strong>
                Rp {Number(principal || 0).toLocaleString('id-ID')}
              </strong>{' '}
              selama <strong>{installmentMonths} bulan</strong> · bunga{' '}
              <strong>{INTEREST_RATE}%/tahun</strong> → angsuran ≈{' '}
              <strong>
                Rp {Math.round(monthlyEstimate).toLocaleString('id-ID')}/bulan
              </strong>
            </div>
          )}
        </div>
      </Modal>

      {/* ── Loan Detail Modal ── */}
      <LoanDetailModal
        loan={detailLoan}
        open={showDetail}
        onClose={() => {
          setShowDetail(false);
          setDetailLoan(null);
        }}
        onRepaid={onRefresh}
      />

      {/* ── Status Filter ── */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value}
            className={`btn btn-sm ${
              filterStatus === f.value ? 'btn-primary' : 'btn-secondary'
            }`}
            onClick={() => setFilterStatus(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* ── Loan List ── */}
      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {[1, 2, 3].map((i) => <Skeleton key={i} height={130} />)}
        </div>
      ) : filteredLoans.length === 0 ? (
        <EmptyState
          icon={<CreditCardIcon />}
          title={
            filterStatus === 'all'
              ? 'Belum ada pinjaman'
              : `Tidak ada pinjaman dengan status ini`
          }
          desc={
            filterStatus === 'all'
              ? 'Ajukan pinjaman untuk mendukung kegiatan pertanian Anda.'
              : undefined
          }
          action={
            filterStatus === 'all' ? (
              <button
                className="btn btn-primary"
                onClick={() => setShowApplyForm(true)}
              >
                <PlusIcon />
                Ajukan Pinjaman
              </button>
            ) : undefined
          }
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {filteredLoans.map((loan) => (
            <LoanCard
              key={loan.id}
              loan={loan}
              onViewDetail={(l) => {
                setDetailLoan(l);
                setShowDetail(true);
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main Page Component ──────────────────────────────────────────────────────

export default function FarmerDashboard({ user, onLogout }) {
  const [activeTab, setActiveTab] = useState('dashboard');

  const [intakes, setIntakes] = useState([]);
  const [loans, setLoans] = useState([]);
  const [loadingIntakes, setLoadingIntakes] = useState(true);
  const [loadingLoans, setLoadingLoans] = useState(true);
  const [intakesError, setIntakesError] = useState('');
  const [loansError, setLoansError] = useState('');

  const fetchIntakes = useCallback(() => {
    setLoadingIntakes(true);
    setIntakesError('');
    intakesAPI
      .listMine()
      .then((r) => setIntakes(Array.isArray(r.data) ? r.data : []))
      .catch((err) => setIntakesError(getErrorMessage(err)))
      .finally(() => setLoadingIntakes(false));
  }, []);

  const fetchLoans = useCallback(() => {
    setLoadingLoans(true);
    setLoansError('');
    loansAPI
      .listMine()
      .then((r) => setLoans(Array.isArray(r.data) ? r.data : []))
      .catch((err) => setLoansError(getErrorMessage(err)))
      .finally(() => setLoadingLoans(false));
  }, []);

  useEffect(() => {
    fetchIntakes();
    fetchLoans();
  }, [fetchIntakes, fetchLoans]);

  const pendingIntakesCount = intakes.filter((i) => i.status === 'pending').length;
  const activeLoansCount = loans.filter((l) => l.status === 'active').length;

  const navItems = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: <HomeIcon />,
      active: activeTab === 'dashboard',
      onClick: () => setActiveTab('dashboard'),
    },
    {
      id: 'intakes',
      label: 'Setoran Panen',
      icon: <PackageIcon />,
      active: activeTab === 'intakes',
      onClick: () => setActiveTab('intakes'),
      badge: pendingIntakesCount,
    },
    {
      id: 'loans',
      label: 'Pinjaman',
      icon: <CreditCardIcon />,
      active: activeTab === 'loans',
      onClick: () => setActiveTab('loans'),
      badge: activeLoansCount,
    },
  ];

  const TAB_TITLES = {
    dashboard: 'Dashboard',
    intakes: 'Setoran Panen',
    loans: 'Pinjaman',
  };

  return (
    <AppShell
      user={user}
      onLogout={onLogout}
      navItems={navItems}
      topbarTitle={`Petani — ${TAB_TITLES[activeTab]}`}
    >
      {/* Global error banners */}
      {intakesError && (
        <div style={{ marginBottom: 16 }}>
          <Alert type="danger">
            Gagal memuat data setoran: {intakesError}{' '}
            <button
              className="btn btn-ghost btn-xs"
              onClick={fetchIntakes}
              style={{ marginLeft: 8 }}
            >
              <RefreshIcon /> Coba lagi
            </button>
          </Alert>
        </div>
      )}
      {loansError && (
        <div style={{ marginBottom: 16 }}>
          <Alert type="danger">
            Gagal memuat data pinjaman: {loansError}{' '}
            <button
              className="btn btn-ghost btn-xs"
              onClick={fetchLoans}
              style={{ marginLeft: 8 }}
            >
              <RefreshIcon /> Coba lagi
            </button>
          </Alert>
        </div>
      )}

      {/* Tab navigation */}
      <Tabs
        items={[
          {
            id: 'dashboard',
            label: 'Dashboard',
            icon: <HomeIcon />,
          },
          {
            id: 'intakes',
            label: 'Setoran Panen',
            icon: <PackageIcon />,
            count: pendingIntakesCount > 0 ? pendingIntakesCount : undefined,
          },
          {
            id: 'loans',
            label: 'Pinjaman',
            icon: <CreditCardIcon />,
            count: activeLoansCount > 0 ? activeLoansCount : undefined,
          },
        ]}
        active={activeTab}
        onChange={setActiveTab}
      />

      {/* Tab content */}
      {activeTab === 'dashboard' && (
        <DashboardTab
          intakes={intakes}
          loans={loans}
          loadingIntakes={loadingIntakes}
          loadingLoans={loadingLoans}
        />
      )}

      {activeTab === 'intakes' && (
        <IntakesTab
          intakes={intakes}
          loading={loadingIntakes}
          onRefresh={fetchIntakes}
        />
      )}

      {activeTab === 'loans' && (
        <LoansTab
          loans={loans}
          loading={loadingLoans}
          onRefresh={fetchLoans}
        />
      )}
    </AppShell>
  );
}
