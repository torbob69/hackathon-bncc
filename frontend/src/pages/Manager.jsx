import { useState, useEffect, useCallback } from 'react';
import AppShell from '../components/AppShell.jsx';
import {
  Money, StatusBadge, formatDate, formatDateTime, Weight,
  Spinner, EmptyState, PageHeader, Modal, Card, Alert,
  FormGroup, Skeleton, getErrorMessage,
} from '../components/ui.jsx';
import { intakesAPI, ordersAPI, commoditiesAPI } from '../api/client.js';
import { toast } from '../hooks/useToast.jsx';

// ─── SVG Icons ────────────────────────────────────────────────────────────────
function PackageIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" width="18" height="18">
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
      <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
      <line x1="12" y1="22.08" x2="12" y2="12" />
    </svg>
  );
}

function LayersIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" width="18" height="18">
      <polygon points="12 2 2 7 12 12 22 7 12 2" />
      <polyline points="2 17 12 22 22 17" />
      <polyline points="2 12 12 17 22 12" />
    </svg>
  );
}

function ScanIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" width="18" height="18">
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <path d="M14 14h1v1h-1z" />
      <path d="M18 14h3v3" />
      <path d="M21 21v-3h-3" />
      <path d="M14 21h3" />
    </svg>
  );
}

function ShoppingBagIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" width="18" height="18">
      <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z" />
      <line x1="3" y1="6" x2="21" y2="6" />
      <path d="M16 10a4 4 0 0 1-8 0" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="14" height="14">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="14" height="14">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function EditIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" width="14" height="14">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  );
}

function RefreshIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" width="14" height="14">
      <polyline points="23 4 23 10 17 10" />
      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
    </svg>
  );
}

function TruckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" width="14" height="14">
      <rect x="1" y="3" width="15" height="13" rx="2" />
      <polygon points="16 8 20 8 23 11 23 16 16 16 16 8" />
      <circle cx="5.5" cy="18.5" r="2.5" />
      <circle cx="18.5" cy="18.5" r="2.5" />
    </svg>
  );
}

function QrCodeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" width="14" height="14">
      <rect x="3" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="3" y="14" width="7" height="7" rx="1" />
      <path d="M14 14h1v1h-1z" />
      <path d="M18 14h3v3" />
      <path d="M21 21v-3h-3" />
      <path d="M14 21h3" />
    </svg>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
const SECTION_TITLES = {
  intakes:   'Antrean Panen',
  stock:     'Stok & Komoditas',
  'qr-verify': 'Verifikasi QR Panen',
  orders:    'Pesanan',
};

const ORDER_STATUS_OPTIONS = [
  { value: '', label: 'Semua Status' },
  { value: 'pending', label: 'Pending' },
  { value: 'paid', label: 'Lunas' },
  { value: 'fulfilled', label: 'Terpenuhi' },
  { value: 'cancelled', label: 'Dibatalkan' },
];

function DetailRow({ label, children }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, padding: '6px 0', borderBottom: '1px solid var(--border-subtle)' }}>
      <span style={{ color: 'var(--muted)', fontSize: '0.8125rem', minWidth: 120 }}>{label}</span>
      <span style={{ fontWeight: 500, color: 'var(--ink)', textAlign: 'right', fontSize: '0.875rem' }}>{children}</span>
    </div>
  );
}

// ─── Tab: Antrean Panen ───────────────────────────────────────────────────────
function AntreanPanen() {
  const [intakes, setIntakes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Confirm modal
  const [confirmModal, setConfirmModal] = useState(null); // { intake }
  const [actualWeight, setActualWeight] = useState('');
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [confirmError, setConfirmError] = useState('');

  // Reject modal
  const [rejectModal, setRejectModal] = useState(null); // { intake }
  const [rejectReason, setRejectReason] = useState('');
  const [rejectLoading, setRejectLoading] = useState(false);
  const [rejectError, setRejectError] = useState('');

  const fetchIntakes = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await intakesAPI.listAll('pending');
      setIntakes(res.data);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchIntakes();
  }, [fetchIntakes]);

  const openConfirm = (intake) => {
    setConfirmModal({ intake });
    setActualWeight('');
    setConfirmError('');
  };

  const closeConfirm = () => {
    if (confirmLoading) return;
    setConfirmModal(null);
    setActualWeight('');
    setConfirmError('');
  };

  const handleConfirm = async () => {
    const wKg = parseFloat(actualWeight);
    if (!actualWeight || isNaN(wKg) || wKg <= 0) {
      setConfirmError('Masukkan berat aktual yang valid (> 0 kg).');
      return;
    }
    setConfirmLoading(true);
    setConfirmError('');
    try {
      await intakesAPI.confirm(confirmModal.intake.id, wKg);
      toast.success(`Intake #${confirmModal.intake.id} berhasil dikonfirmasi.`);
      closeConfirm();
      fetchIntakes();
    } catch (err) {
      setConfirmError(getErrorMessage(err));
    } finally {
      setConfirmLoading(false);
    }
  };

  const openReject = (intake) => {
    setRejectModal({ intake });
    setRejectReason('');
    setRejectError('');
  };

  const closeReject = () => {
    if (rejectLoading) return;
    setRejectModal(null);
    setRejectReason('');
    setRejectError('');
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) {
      setRejectError('Alasan penolakan wajib diisi.');
      return;
    }
    setRejectLoading(true);
    setRejectError('');
    try {
      await intakesAPI.reject(rejectModal.intake.id, rejectReason.trim());
      toast.success(`Intake #${rejectModal.intake.id} telah ditolak.`);
      closeReject();
      fetchIntakes();
    } catch (err) {
      setRejectError(getErrorMessage(err));
    } finally {
      setRejectLoading(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Antrean Panen"
        desc="Daftar pengajuan panen yang menunggu konfirmasi dari manajer"
        actions={
          <button className="btn btn-secondary btn-sm" onClick={fetchIntakes} disabled={loading}>
            <RefreshIcon /> Refresh
          </button>
        }
      />

      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <Skeleton height={20} width="40%" />
              <div style={{ marginTop: 8 }}><Skeleton height={16} width="60%" /></div>
              <div style={{ marginTop: 6 }}><Skeleton height={16} width="30%" /></div>
            </Card>
          ))}
        </div>
      ) : error ? (
        <Alert type="danger">{error}</Alert>
      ) : intakes.length === 0 ? (
        <EmptyState
          icon={<PackageIcon />}
          title="Tidak ada antrean panen"
          desc="Semua pengajuan panen telah diproses."
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {intakes.map((intake) => (
            <Card key={intake.id}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
                <div style={{ flex: 1, minWidth: 200 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <span style={{ fontWeight: 700, color: 'var(--ink)', fontFamily: 'var(--font-mono)', fontSize: '0.8125rem' }}>
                      #{intake.id}
                    </span>
                    <StatusBadge status={intake.status} />
                    {intake.commodity_name && (
                      <span style={{ fontSize: '0.8125rem', color: 'var(--muted)', background: 'var(--surface-2)', padding: '2px 8px', borderRadius: 20 }}>
                        {intake.commodity_name}
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: '4px 24px' }}>
                    <div style={{ fontSize: '0.8125rem' }}>
                      <span style={{ color: 'var(--muted)' }}>Petani: </span>
                      <span style={{ fontWeight: 600 }}>{intake.farmer_name || intake.farmer_id || '—'}</span>
                    </div>
                    <div style={{ fontSize: '0.8125rem' }}>
                      <span style={{ color: 'var(--muted)' }}>Berat Diajukan: </span>
                      <span style={{ fontWeight: 600 }}><Weight value={intake.weight_kg} /></span>
                    </div>
                    {intake.estimated_value != null && (
                      <div style={{ fontSize: '0.8125rem' }}>
                        <span style={{ color: 'var(--muted)' }}>Est. Nilai: </span>
                        <span style={{ fontWeight: 600 }}><Money value={intake.estimated_value} /></span>
                      </div>
                    )}
                    <div style={{ fontSize: '0.8125rem' }}>
                      <span style={{ color: 'var(--muted)' }}>Waktu: </span>
                      <span>{formatDateTime(intake.created_at)}</span>
                    </div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                  <button
                    className="btn btn-success btn-sm"
                    onClick={() => openConfirm(intake)}
                  >
                    <CheckIcon /> Konfirmasi
                  </button>
                  <button
                    className="btn btn-danger btn-sm"
                    onClick={() => openReject(intake)}
                  >
                    <XIcon /> Tolak
                  </button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Confirm Modal */}
      <Modal
        open={!!confirmModal}
        onClose={closeConfirm}
        title="Konfirmasi Panen"
        footer={
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button className="btn btn-ghost" onClick={closeConfirm} disabled={confirmLoading}>
              Batal
            </button>
            <button className="btn btn-success" onClick={handleConfirm} disabled={confirmLoading}>
              {confirmLoading ? <Spinner /> : <CheckIcon />}
              {confirmLoading ? 'Menyimpan…' : 'Konfirmasi'}
            </button>
          </div>
        }
      >
        {confirmModal && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ background: 'var(--surface-2)', borderRadius: 8, padding: 14 }}>
              <div style={{ fontWeight: 700, fontSize: '0.8125rem', color: 'var(--muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Detail Pengajuan
              </div>
              <DetailRow label="ID Intake">#{confirmModal.intake.id}</DetailRow>
              <DetailRow label="Petani">{confirmModal.intake.farmer_name || confirmModal.intake.farmer_id || '—'}</DetailRow>
              <DetailRow label="Komoditas">{confirmModal.intake.commodity_name || '—'}</DetailRow>
              <DetailRow label="Berat Diajukan"><Weight value={confirmModal.intake.weight_kg} /></DetailRow>
              {confirmModal.intake.estimated_value != null && (
                <DetailRow label="Est. Nilai"><Money value={confirmModal.intake.estimated_value} /></DetailRow>
              )}
              <DetailRow label="Waktu Pengajuan">{formatDateTime(confirmModal.intake.created_at)}</DetailRow>
            </div>
            <FormGroup
              label="Berat Aktual (kg)"
              required
              hint="Masukkan berat timbang aktual dari hasil panen ini."
              error={confirmError}
            >
              <input
                type="number"
                className="input"
                min="0.001"
                step="0.001"
                placeholder="contoh: 125.500"
                value={actualWeight}
                onChange={(e) => { setActualWeight(e.target.value); setConfirmError(''); }}
                autoFocus
                disabled={confirmLoading}
              />
            </FormGroup>
            {confirmError && <Alert type="danger">{confirmError}</Alert>}
          </div>
        )}
      </Modal>

      {/* Reject Modal */}
      <Modal
        open={!!rejectModal}
        onClose={closeReject}
        title="Tolak Pengajuan Panen"
        footer={
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button className="btn btn-ghost" onClick={closeReject} disabled={rejectLoading}>
              Batal
            </button>
            <button className="btn btn-danger" onClick={handleReject} disabled={rejectLoading}>
              {rejectLoading ? <Spinner /> : <XIcon />}
              {rejectLoading ? 'Menolak…' : 'Tolak Panen'}
            </button>
          </div>
        }
      >
        {rejectModal && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <Alert type="warning">
              Tindakan ini akan menolak pengajuan panen dan memberi tahu petani melalui notifikasi.
            </Alert>
            <div style={{ background: 'var(--surface-2)', borderRadius: 8, padding: 14 }}>
              <div style={{ fontWeight: 700, fontSize: '0.8125rem', color: 'var(--muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Detail Pengajuan
              </div>
              <DetailRow label="ID Intake">#{rejectModal.intake.id}</DetailRow>
              <DetailRow label="Petani">{rejectModal.intake.farmer_name || rejectModal.intake.farmer_id || '—'}</DetailRow>
              <DetailRow label="Komoditas">{rejectModal.intake.commodity_name || '—'}</DetailRow>
              <DetailRow label="Berat Diajukan"><Weight value={rejectModal.intake.weight_kg} /></DetailRow>
            </div>
            <FormGroup
              label="Alasan Penolakan"
              required
              hint="Alasan ini akan dikirim ke petani sebagai notifikasi."
              error={rejectError}
            >
              <textarea
                className="input"
                rows={3}
                placeholder="Contoh: Kualitas tidak memenuhi standar minimum koperasi..."
                value={rejectReason}
                onChange={(e) => { setRejectReason(e.target.value); setRejectError(''); }}
                autoFocus
                disabled={rejectLoading}
                style={{ resize: 'vertical', minHeight: 80 }}
              />
            </FormGroup>
            {rejectError && <Alert type="danger">{rejectError}</Alert>}
          </div>
        )}
      </Modal>
    </>
  );
}

// ─── Tab: Stok & Komoditas ────────────────────────────────────────────────────
function StokKomoditas() {
  const [commodities, setCommodities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Edit stock modal
  const [editModal, setEditModal] = useState(null); // { commodity }
  const [editStock, setEditStock] = useState('');
  const [editPrice, setEditPrice] = useState('');
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState('');

  const fetchCommodities = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await commoditiesAPI.list();
      setCommodities(res.data);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCommodities();
  }, [fetchCommodities]);

  const openEdit = (commodity) => {
    setEditModal({ commodity });
    setEditStock(commodity.current_stock_kg != null ? String(commodity.current_stock_kg) : '');
    setEditPrice(commodity.pihps_price != null ? String(commodity.pihps_price) : '');
    setEditError('');
  };

  const closeEdit = () => {
    if (editLoading) return;
    setEditModal(null);
    setEditStock('');
    setEditPrice('');
    setEditError('');
  };

  const handleEditSave = async () => {
    const stockVal = parseFloat(editStock);
    const priceVal = parseFloat(editPrice);
    if (editStock !== '' && (isNaN(stockVal) || stockVal < 0)) {
      setEditError('Stok tidak valid (minimal 0).');
      return;
    }
    if (editPrice !== '' && (isNaN(priceVal) || priceVal < 0)) {
      setEditError('Harga PIHPS tidak valid.');
      return;
    }
    setEditLoading(true);
    setEditError('');
    const payload = {};
    if (editStock !== '') payload.current_stock_kg = stockVal;
    if (editPrice !== '') payload.pihps_price = priceVal;
    try {
      await commoditiesAPI.update(editModal.commodity.id, payload);
      toast.success(`Komoditas "${editModal.commodity.name}" berhasil diperbarui.`);
      closeEdit();
      fetchCommodities();
    } catch (err) {
      setEditError(getErrorMessage(err));
    } finally {
      setEditLoading(false);
    }
  };

  const getStockStatus = (stock) => {
    if (stock == null) return null;
    if (stock === 0) return { label: 'Habis', color: 'var(--danger)', bg: 'var(--danger-bg)' };
    if (stock < 100) return { label: 'Rendah', color: 'var(--warning)', bg: 'var(--warning-bg)' };
    return { label: 'Cukup', color: 'var(--success)', bg: 'var(--success-bg)' };
  };

  return (
    <>
      <PageHeader
        title="Stok & Komoditas"
        desc="Pantau dan perbarui stok komoditas serta harga PIHPS"
        actions={
          <button className="btn btn-secondary btn-sm" onClick={fetchCommodities} disabled={loading}>
            <RefreshIcon /> Refresh
          </button>
        }
      />

      {loading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
          {[1, 2, 3, 4].map((i) => (
            <Card key={i}>
              <Skeleton height={22} width="50%" />
              <div style={{ marginTop: 10 }}><Skeleton height={36} /></div>
              <div style={{ marginTop: 8 }}><Skeleton height={16} width="60%" /></div>
            </Card>
          ))}
        </div>
      ) : error ? (
        <Alert type="danger">{error}</Alert>
      ) : commodities.length === 0 ? (
        <EmptyState
          icon={<LayersIcon />}
          title="Belum ada komoditas"
          desc="Tidak ada komoditas yang terdaftar."
        />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
          {commodities.map((c) => {
            const stockStatus = getStockStatus(c.current_stock_kg);
            return (
              <Card
                key={c.id}
                actions={
                  <button className="btn btn-ghost btn-icon btn-sm" onClick={() => openEdit(c)} title="Edit stok & harga">
                    <EditIcon />
                  </button>
                }
                title={c.name}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {/* Stock indicator */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div>
                      <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--ink)', lineHeight: 1.1 }}>
                        {c.current_stock_kg != null
                          ? c.current_stock_kg.toLocaleString('id-ID', { maximumFractionDigits: 3 })
                          : '—'}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--muted)', marginTop: 1 }}>kg stok saat ini</div>
                    </div>
                    {stockStatus && (
                      <span style={{
                        fontSize: '0.75rem', fontWeight: 700, padding: '3px 10px', borderRadius: 20,
                        color: stockStatus.color, background: stockStatus.bg,
                      }}>
                        {stockStatus.label}
                      </span>
                    )}
                  </div>

                  {/* Stock bar */}
                  {c.current_stock_kg != null && c.max_stock_kg != null && c.max_stock_kg > 0 && (
                    <div style={{ background: 'var(--surface-2)', borderRadius: 4, height: 6, overflow: 'hidden' }}>
                      <div style={{
                        height: '100%',
                        width: `${Math.min(100, (c.current_stock_kg / c.max_stock_kg) * 100)}%`,
                        background: stockStatus?.color || 'var(--primary)',
                        borderRadius: 4,
                        transition: 'width 0.4s ease',
                      }} />
                    </div>
                  )}

                  <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 10, display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem' }}>
                      <span style={{ color: 'var(--muted)' }}>Harga PIHPS</span>
                      <span style={{ fontWeight: 600 }}>
                        {c.pihps_price != null ? <Money value={c.pihps_price} /> : '—'}
                        <span style={{ color: 'var(--muted)', fontWeight: 400 }}>/kg</span>
                      </span>
                    </div>
                    {c.unit && (
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem' }}>
                        <span style={{ color: 'var(--muted)' }}>Satuan</span>
                        <span style={{ fontWeight: 600 }}>{c.unit}</span>
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Edit Stock Modal */}
      <Modal
        open={!!editModal}
        onClose={closeEdit}
        title="Perbarui Stok & Harga"
        footer={
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button className="btn btn-ghost" onClick={closeEdit} disabled={editLoading}>
              Batal
            </button>
            <button className="btn btn-primary" onClick={handleEditSave} disabled={editLoading}>
              {editLoading ? <Spinner /> : null}
              {editLoading ? 'Menyimpan…' : 'Simpan'}
            </button>
          </div>
        }
      >
        {editModal && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ background: 'var(--primary-subtle)', borderRadius: 8, padding: '10px 14px' }}>
              <div style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--ink)' }}>{editModal.commodity.name}</div>
              {editModal.commodity.unit && (
                <div style={{ fontSize: '0.8125rem', color: 'var(--muted)', marginTop: 2 }}>Satuan: {editModal.commodity.unit}</div>
              )}
            </div>
            <FormGroup
              label="Stok Saat Ini (kg)"
              hint="Masukkan jumlah stok terkini secara manual."
              error={editError}
            >
              <input
                type="number"
                className="input"
                min="0"
                step="0.001"
                placeholder={editModal.commodity.current_stock_kg != null ? String(editModal.commodity.current_stock_kg) : '0'}
                value={editStock}
                onChange={(e) => { setEditStock(e.target.value); setEditError(''); }}
                autoFocus
                disabled={editLoading}
              />
            </FormGroup>
            <FormGroup
              label="Harga PIHPS (Rp/kg)"
              hint="Harga acuan dari Panel Harga Pangan Strategis."
            >
              <input
                type="number"
                className="input"
                min="0"
                step="1"
                placeholder={editModal.commodity.pihps_price != null ? String(editModal.commodity.pihps_price) : '0'}
                value={editPrice}
                onChange={(e) => { setEditPrice(e.target.value); setEditError(''); }}
                disabled={editLoading}
              />
            </FormGroup>
            {editError && <Alert type="danger">{editError}</Alert>}
          </div>
        )}
      </Modal>
    </>
  );
}

// ─── Tab: Verifikasi QR Panen ─────────────────────────────────────────────────
function VerifikasiQR() {
  const [token, setToken] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const handleVerify = async (e) => {
    e?.preventDefault();
    const t = token.trim();
    if (!t) {
      setError('Token QR tidak boleh kosong.');
      return;
    }
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await intakesAPI.verifyQR(t);
      setResult(res.data);
      toast.success('QR berhasil diverifikasi!');
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setToken('');
    setResult(null);
    setError('');
  };

  return (
    <>
      <PageHeader
        title="Verifikasi QR Panen"
        desc="Scan atau masukkan token QR dari bukti panen petani untuk memverifikasi keasliannya"
      />

      <div style={{ maxWidth: 560 }}>
        <Card title="Masukkan Token QR">
          <form onSubmit={handleVerify} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <FormGroup
              label="Token QR"
              required
              hint="Salin token dari QR code petani, atau tempel hasil scan di sini."
              error={error}
            >
              <div style={{ position: 'relative' }}>
                <textarea
                  className="input"
                  rows={4}
                  placeholder="Tempel token QR di sini…"
                  value={token}
                  onChange={(e) => { setToken(e.target.value); setError(''); setResult(null); }}
                  disabled={loading}
                  style={{
                    resize: 'none',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.8125rem',
                    letterSpacing: '0.02em',
                  }}
                  autoFocus
                />
              </div>
            </FormGroup>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={loading || !token.trim()}
                style={{ flex: 1 }}
              >
                {loading ? <Spinner /> : <ScanIcon />}
                {loading ? 'Memverifikasi…' : 'Verifikasi QR'}
              </button>
              {(result || token) && (
                <button type="button" className="btn btn-ghost" onClick={handleReset} disabled={loading}>
                  Reset
                </button>
              )}
            </div>
          </form>
        </Card>

        {/* Result */}
        {result && (
          <div style={{ marginTop: 16 }}>
            <Card title="Hasil Verifikasi">
              <Alert type="success">
                QR token valid — pengajuan panen terverifikasi.
              </Alert>
              <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 0 }}>
                <DetailRow label="ID Intake">#{result.id || result.intake_id || '—'}</DetailRow>
                {(result.farmer_name || result.farmer_id) && (
                  <DetailRow label="Petani">{result.farmer_name || result.farmer_id}</DetailRow>
                )}
                {result.commodity_name && (
                  <DetailRow label="Komoditas">{result.commodity_name}</DetailRow>
                )}
                {result.weight_kg != null && (
                  <DetailRow label="Berat"><Weight value={result.weight_kg} /></DetailRow>
                )}
                {result.actual_weight_kg != null && (
                  <DetailRow label="Berat Aktual"><Weight value={result.actual_weight_kg} /></DetailRow>
                )}
                {result.estimated_value != null && (
                  <DetailRow label="Est. Nilai"><Money value={result.estimated_value} /></DetailRow>
                )}
                {result.status && (
                  <DetailRow label="Status"><StatusBadge status={result.status} /></DetailRow>
                )}
                {result.created_at && (
                  <DetailRow label="Waktu Pengajuan">{formatDateTime(result.created_at)}</DetailRow>
                )}
                {result.confirmed_at && (
                  <DetailRow label="Waktu Konfirmasi">{formatDateTime(result.confirmed_at)}</DetailRow>
                )}
              </div>
            </Card>
          </div>
        )}

        {error && (
          <div style={{ marginTop: 16 }}>
            <Alert type="danger">{error}</Alert>
          </div>
        )}
      </div>
    </>
  );
}

// ─── Tab: Pesanan ─────────────────────────────────────────────────────────────
function Pesanan() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // Pickup QR modal
  const [pickupModal, setPickupModal] = useState(null); // { order }
  const [pickupToken, setPickupToken] = useState('');
  const [pickupLoading, setPickupLoading] = useState(false);
  const [pickupError, setPickupError] = useState('');
  const [pickupResult, setPickupResult] = useState(null);

  // Delivery fulfill loading per order id
  const [deliveryLoading, setDeliveryLoading] = useState({});

  const fetchOrders = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await ordersAPI.listKoperasi(statusFilter);
      setOrders(res.data);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  const openPickup = (order) => {
    setPickupModal({ order });
    setPickupToken('');
    setPickupError('');
    setPickupResult(null);
  };

  const closePickup = () => {
    if (pickupLoading) return;
    setPickupModal(null);
    setPickupToken('');
    setPickupError('');
    setPickupResult(null);
  };

  const handlePickupVerify = async () => {
    const t = pickupToken.trim();
    if (!t) {
      setPickupError('Token QR pickup tidak boleh kosong.');
      return;
    }
    setPickupLoading(true);
    setPickupError('');
    setPickupResult(null);
    try {
      const res = await ordersAPI.verifyPickup(t);
      setPickupResult(res.data);
      toast.success('Pickup berhasil diverifikasi!');
      fetchOrders();
    } catch (err) {
      setPickupError(getErrorMessage(err));
    } finally {
      setPickupLoading(false);
    }
  };

  const handleFulfillDelivery = async (orderId) => {
    setDeliveryLoading((prev) => ({ ...prev, [orderId]: true }));
    try {
      await ordersAPI.fulfillDelivery(orderId);
      toast.success(`Pesanan #${orderId} ditandai selesai dikirim.`);
      fetchOrders();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setDeliveryLoading((prev) => ({ ...prev, [orderId]: false }));
    }
  };

  const isPickupOrder = (order) =>
    order.delivery_type === 'pickup' || order.fulfillment_type === 'pickup';

  const isDeliveryOrder = (order) =>
    order.delivery_type === 'delivery' || order.fulfillment_type === 'delivery';

  const canAction = (order) =>
    order.status === 'paid';

  return (
    <>
      <PageHeader
        title="Pesanan"
        desc="Kelola pesanan dari distributor — verifikasi pickup atau tandai pengiriman selesai"
        actions={
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <select
              className="input"
              style={{ width: 'auto', minWidth: 160, padding: '6px 10px', fontSize: '0.875rem' }}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              {ORDER_STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <button className="btn btn-secondary btn-sm" onClick={fetchOrders} disabled={loading}>
              <RefreshIcon /> Refresh
            </button>
          </div>
        }
      />

      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <Skeleton height={20} width="40%" />
              <div style={{ marginTop: 8 }}><Skeleton height={16} width="70%" /></div>
              <div style={{ marginTop: 6 }}><Skeleton height={16} width="40%" /></div>
            </Card>
          ))}
        </div>
      ) : error ? (
        <Alert type="danger">{error}</Alert>
      ) : orders.length === 0 ? (
        <EmptyState
          icon={<ShoppingBagIcon />}
          title="Tidak ada pesanan"
          desc={statusFilter ? `Tidak ada pesanan dengan status "${statusFilter}".` : 'Belum ada pesanan yang masuk.'}
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {orders.map((order) => {
            const pickup = isPickupOrder(order);
            const delivery = isDeliveryOrder(order);
            const actionable = canAction(order);
            const isDeliverying = deliveryLoading[order.id];

            return (
              <Card key={order.id}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
                  <div style={{ flex: 1, minWidth: 220 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
                      <span style={{ fontWeight: 700, fontFamily: 'var(--font-mono)', fontSize: '0.8125rem', color: 'var(--ink)' }}>
                        #{order.id}
                      </span>
                      <StatusBadge status={order.status} />
                      {(pickup || delivery) && (
                        <span style={{
                          fontSize: '0.75rem', fontWeight: 600, padding: '2px 8px', borderRadius: 20,
                          background: pickup ? 'var(--info-bg)' : 'var(--warning-bg)',
                          color: pickup ? 'var(--info)' : 'var(--warning)',
                        }}>
                          {pickup ? '📦 Pickup' : '🚚 Pengiriman'}
                        </span>
                      )}
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '4px 24px' }}>
                      {order.distributor_name && (
                        <div style={{ fontSize: '0.8125rem' }}>
                          <span style={{ color: 'var(--muted)' }}>Distributor: </span>
                          <span style={{ fontWeight: 600 }}>{order.distributor_name}</span>
                        </div>
                      )}
                      {order.total_amount != null && (
                        <div style={{ fontSize: '0.8125rem' }}>
                          <span style={{ color: 'var(--muted)' }}>Total: </span>
                          <span style={{ fontWeight: 700, color: 'var(--primary-text)' }}>
                            <Money value={order.total_amount} />
                          </span>
                        </div>
                      )}
                      {order.total_weight_kg != null && (
                        <div style={{ fontSize: '0.8125rem' }}>
                          <span style={{ color: 'var(--muted)' }}>Berat: </span>
                          <span style={{ fontWeight: 600 }}><Weight value={order.total_weight_kg} /></span>
                        </div>
                      )}
                      <div style={{ fontSize: '0.8125rem' }}>
                        <span style={{ color: 'var(--muted)' }}>Dibuat: </span>
                        <span>{formatDate(order.created_at)}</span>
                      </div>
                    </div>

                    {/* Order items preview */}
                    {order.items && order.items.length > 0 && (
                      <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {order.items.map((item, idx) => (
                          <span
                            key={idx}
                            style={{
                              fontSize: '0.75rem', background: 'var(--surface-2)', border: '1px solid var(--border)',
                              borderRadius: 6, padding: '2px 8px', color: 'var(--ink-2)',
                            }}
                          >
                            {item.commodity_name || item.commodity_id}
                            {item.weight_kg != null && ` · ${item.weight_kg.toLocaleString('id-ID', { maximumFractionDigits: 1 })} kg`}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Action buttons */}
                  {actionable && (
                    <div style={{ display: 'flex', gap: 8, flexShrink: 0, alignItems: 'flex-start' }}>
                      {pickup && (
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => openPickup(order)}
                        >
                          <QrCodeIcon /> Verifikasi Pickup
                        </button>
                      )}
                      {delivery && (
                        <button
                          className="btn btn-success btn-sm"
                          onClick={() => handleFulfillDelivery(order.id)}
                          disabled={isDeliverying}
                        >
                          {isDeliverying ? <Spinner /> : <TruckIcon />}
                          {isDeliverying ? 'Memproses…' : 'Tandai Terkirim'}
                        </button>
                      )}
                      {!pickup && !delivery && (
                        <button
                          className="btn btn-success btn-sm"
                          onClick={() => handleFulfillDelivery(order.id)}
                          disabled={isDeliverying}
                        >
                          {isDeliverying ? <Spinner /> : <CheckIcon />}
                          {isDeliverying ? 'Memproses…' : 'Selesaikan'}
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Pickup QR Modal */}
      <Modal
        open={!!pickupModal}
        onClose={closePickup}
        title="Verifikasi Pickup QR"
        footer={
          pickupResult ? (
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button className="btn btn-primary" onClick={closePickup}>
                Selesai
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={closePickup} disabled={pickupLoading}>
                Batal
              </button>
              <button className="btn btn-primary" onClick={handlePickupVerify} disabled={pickupLoading || !pickupToken.trim()}>
                {pickupLoading ? <Spinner /> : <ScanIcon />}
                {pickupLoading ? 'Memverifikasi…' : 'Verifikasi'}
              </button>
            </div>
          )
        }
      >
        {pickupModal && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {!pickupResult ? (
              <>
                <div style={{ background: 'var(--info-bg)', borderRadius: 8, padding: '10px 14px', fontSize: '0.875rem', color: 'var(--info)' }}>
                  <strong>Pesanan #{pickupModal.order.id}</strong>
                  {pickupModal.order.distributor_name && ` · ${pickupModal.order.distributor_name}`}
                </div>
                <FormGroup
                  label="Token QR Pickup"
                  required
                  hint="Minta distributor menunjukkan QR code atau salin tokennya di sini."
                  error={pickupError}
                >
                  <textarea
                    className="input"
                    rows={5}
                    placeholder="Tempel token QR pickup di sini…"
                    value={pickupToken}
                    onChange={(e) => { setPickupToken(e.target.value); setPickupError(''); setPickupResult(null); }}
                    disabled={pickupLoading}
                    autoFocus
                    style={{
                      resize: 'none',
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.8125rem',
                      letterSpacing: '0.02em',
                    }}
                  />
                </FormGroup>
                {pickupError && <Alert type="danger">{pickupError}</Alert>}
              </>
            ) : (
              <>
                <Alert type="success">Pickup berhasil diverifikasi! Pesanan telah diselesaikan.</Alert>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                  {pickupResult.id && <DetailRow label="ID Pesanan">#{pickupResult.id}</DetailRow>}
                  {pickupResult.distributor_name && <DetailRow label="Distributor">{pickupResult.distributor_name}</DetailRow>}
                  {pickupResult.total_amount != null && <DetailRow label="Total"><Money value={pickupResult.total_amount} /></DetailRow>}
                  {pickupResult.status && <DetailRow label="Status"><StatusBadge status={pickupResult.status} /></DetailRow>}
                  {pickupResult.fulfilled_at && <DetailRow label="Diselesaikan">{formatDateTime(pickupResult.fulfilled_at)}</DetailRow>}
                </div>
              </>
            )}
          </div>
        )}
      </Modal>
    </>
  );
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────
export default function ManagerDashboard({ user, onLogout }) {
  const [activeSection, setActiveSection] = useState('intakes');
  const [pendingCount, setPendingCount] = useState(0);

  // Fetch pending intakes count for the sidebar badge
  useEffect(() => {
    const fetchPendingCount = async () => {
      try {
        const res = await intakesAPI.listAll('pending');
        setPendingCount(res.data.length);
      } catch {
        // silently fail
      }
    };
    fetchPendingCount();
    const interval = setInterval(fetchPendingCount, 60000);
    return () => clearInterval(interval);
  }, []);

  const navItems = [
    {
      id: 'intakes',
      label: 'Antrean Panen',
      icon: <PackageIcon />,
      badge: pendingCount,
      active: activeSection === 'intakes',
      onClick: () => setActiveSection('intakes'),
    },
    {
      id: 'stock',
      label: 'Stok & Komoditas',
      icon: <LayersIcon />,
      active: activeSection === 'stock',
      onClick: () => setActiveSection('stock'),
    },
    {
      id: 'qr-verify',
      label: 'Verifikasi QR',
      icon: <ScanIcon />,
      active: activeSection === 'qr-verify',
      onClick: () => setActiveSection('qr-verify'),
    },
    {
      id: 'orders',
      label: 'Pesanan',
      icon: <ShoppingBagIcon />,
      active: activeSection === 'orders',
      onClick: () => setActiveSection('orders'),
    },
  ];

  return (
    <AppShell
      user={user}
      onLogout={onLogout}
      navItems={navItems}
      topbarTitle={SECTION_TITLES[activeSection]}
    >
      <div style={{ maxWidth: 1100, margin: '0 auto' }}>
        {activeSection === 'intakes'   && <AntreanPanen />}
        {activeSection === 'stock'     && <StokKomoditas />}
        {activeSection === 'qr-verify' && <VerifikasiQR />}
        {activeSection === 'orders'    && <Pesanan />}
      </div>
    </AppShell>
  );
}
