import { useState, useEffect } from 'react';
import AppShell from '../components/AppShell.jsx';
import { Money, StatusBadge, PageHeader, Card, EmptyState, Spinner, Alert, formatDate, formatDateTime, getErrorMessage } from '../components/ui.jsx';
import { ordersAPI, koperasiAPI } from '../api/client.js';
import { toast } from '../hooks/useToast.jsx';

// ─── Lucide-style icons ───────────────────────────────────────────────────
const ShoppingCartIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
    <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>
  </svg>
);

const StoreIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
    <polyline points="9 22 9 12 15 12 15 22"/>
  </svg>
);

const PackageIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <line x1="16.5" y1="9.4" x2="7.5" y2="4.21"/><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>
  </svg>
);

function formatRp(val) {
  return 'Rp ' + (parseFloat(val) || 0).toLocaleString('id-ID', { maximumFractionDigits: 0 });
}

// ─── Checkout Modal ────────────────────────────────────────────────────────
function CheckoutModal({ catalogItem, onClose, onSuccess }) {
  const [weightKg, setWeightKg] = useState('');
  const [fulfillmentType, setFulfillmentType] = useState('pickup');
  const [deliveryAddress, setDeliveryAddress] = useState('');
  const [loading, setLoading] = useState(false);

  const subtotal = parseFloat(weightKg) > 0
    ? parseFloat(weightKg) * parseFloat(catalogItem.pihps_price)
    : 0;
  const fee = subtotal * 0.015; // 1.5% platform fee
  const total = subtotal + fee;

  const handleSubmit = async (e) => {
    e.preventDefault();
    const w = parseFloat(weightKg);
    if (!w || w <= 0) {
      toast.error('Masukkan berat yang valid.');
      return;
    }
    if (fulfillmentType === 'delivery' && !deliveryAddress.trim()) {
      toast.error('Masukkan alamat pengiriman.');
      return;
    }
    setLoading(true);
    try {
      const res = await ordersAPI.checkout({
        koperasi_id: catalogItem.koperasi_id,
        fulfillment_type: fulfillmentType,
        delivery_address: fulfillmentType === 'delivery' ? deliveryAddress.trim() : null,
        items: [{ commodity_id: catalogItem.id, weight_kg: w }],
      });
      toast.success('Pesanan berhasil dibuat!');
      onSuccess(res.data);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <div className="modal-header">
          <span className="modal-title">Buat Pesanan</span>
          <button className="btn btn-ghost btn-icon btn-sm" onClick={onClose}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="15" height="15"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ padding: 14, background: 'var(--surface-2)', borderRadius: 10, border: '1px solid var(--border)' }}>
              <div style={{ fontWeight: 700, color: 'var(--ink)', marginBottom: 4 }}>{catalogItem.name}</div>
              <div style={{ fontSize: '0.875rem', color: 'var(--muted)' }}>
                Harga PIHPS: {formatRp(catalogItem.pihps_price)} / kg
              </div>
              <div style={{ fontSize: '0.875rem', color: 'var(--muted)' }}>
                Stok tersedia: <strong style={{ color: 'var(--ink)' }}>{parseFloat(catalogItem.current_stock_kg).toLocaleString('id-ID')} kg</strong>
              </div>
              {catalogItem.koperasi_name && (
                <div style={{ fontSize: '0.875rem', color: 'var(--muted)', marginTop: 2 }}>
                  Koperasi: {catalogItem.koperasi_name}
                </div>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="checkout-weight">Berat (kg) <span style={{ color: 'var(--danger)' }}>*</span></label>
              <input
                id="checkout-weight"
                type="number"
                step="0.001"
                min="0.001"
                placeholder="0.000"
                value={weightKg}
                onChange={(e) => setWeightKg(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="checkout-fulfillment">Jenis Pengiriman <span style={{ color: 'var(--danger)' }}>*</span></label>
              <select id="checkout-fulfillment" value={fulfillmentType} onChange={(e) => setFulfillmentType(e.target.value)}>
                <option value="pickup">Ambil Sendiri (Pickup)</option>
                <option value="delivery">Diantar (Delivery)</option>
              </select>
            </div>

            {fulfillmentType === 'delivery' && (
              <div className="form-group">
                <label htmlFor="checkout-address">Alamat Pengiriman <span style={{ color: 'var(--danger)' }}>*</span></label>
                <textarea
                  id="checkout-address"
                  placeholder="Masukkan alamat lengkap..."
                  value={deliveryAddress}
                  onChange={(e) => setDeliveryAddress(e.target.value)}
                  rows={3}
                />
              </div>
            )}

            {subtotal > 0 && (
              <div style={{ background: 'var(--primary-subtle)', border: '1px solid var(--primary-light)', borderRadius: 10, padding: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: '0.875rem' }}>
                  <span style={{ color: 'var(--ink-2)' }}>Subtotal</span>
                  <span style={{ color: 'var(--ink)', fontWeight: 600 }}>{formatRp(subtotal)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, fontSize: '0.875rem' }}>
                  <span style={{ color: 'var(--ink-2)' }}>Platform fee (1.5%)</span>
                  <span style={{ color: 'var(--ink)', fontWeight: 600 }}>{formatRp(fee)}</span>
                </div>
                <div style={{ borderTop: '1px solid var(--primary-light)', paddingTop: 8, display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontWeight: 700, color: 'var(--ink)' }}>Total</span>
                  <span style={{ fontWeight: 800, color: 'var(--primary-text)', fontSize: '1.0625rem' }}>{formatRp(total)}</span>
                </div>
                <div style={{ marginTop: 8, fontSize: '0.75rem', color: 'var(--muted)' }}>
                  {total > 10_000_000 ? '⚡ Virtual Account (> Rp 10 juta)' : '📱 QRIS (≤ Rp 10 juta)'}
                </div>
              </div>
            )}
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={loading}>Batal</button>
            <button type="submit" id="checkout-submit-btn" className="btn btn-primary" disabled={loading}>
              {loading ? <><div className="spinner" />Memproses...</> : 'Buat Pesanan'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Catalog tab ────────────────────────────────────────────────────────────
function CatalogTab({ onOrderCreated }) {
  const [catalog, setCatalog] = useState([]);
  const [koperasiMap, setKoperasiMap] = useState({});
  const [loading, setLoading] = useState(true);
  const [selectedItem, setSelectedItem] = useState(null);
  const [koperasiFilter, setKoperasiFilter] = useState('');

  useEffect(() => {
    Promise.all([
      ordersAPI.catalog({ in_stock_only: false }),
      koperasiAPI.list().catch(() => ({ data: [] })),
    ])
      .then(([catalogRes, koperasiRes]) => {
        setCatalog(catalogRes.data);
        const map = {};
        (koperasiRes.data || []).forEach(k => { map[k.id] = k.name; });
        setKoperasiMap(map);
      })
      .catch(() => toast.error('Gagal memuat katalog.'))
      .finally(() => setLoading(false));
  }, []);

  const filtered = koperasiFilter
    ? catalog.filter((c) => String(c.koperasi_id) === koperasiFilter)
    : catalog;

  const koperasiIds = [...new Set(catalog.map((c) => c.koperasi_id))];
  const getKoperasiName = (id) => koperasiMap[id] || `Koperasi #${id}`;

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}><Spinner large /></div>;

  return (
    <>
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, alignItems: 'center', flexWrap: 'wrap' }}>
        <select
          id="catalog-koperasi-filter"
          style={{ width: 'auto', minWidth: 180 }}
          value={koperasiFilter}
          onChange={(e) => setKoperasiFilter(e.target.value)}
        >
          <option value="">Semua Koperasi</option>
          {koperasiIds.map((id) => (
            <option key={id} value={id}>{getKoperasiName(id)}</option>
          ))}
        </select>
        <span style={{ color: 'var(--muted)', fontSize: '0.875rem' }}>
          {filtered.length} komoditas tersedia
        </span>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={<PackageIcon />}
          title="Tidak ada komoditas"
          desc="Saat ini belum ada komoditas yang tersedia di marketplace."
        />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
          {filtered.map((item) => (
            <div
              key={item.id}
              style={{
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                borderRadius: 12,
                padding: 20,
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
                boxShadow: 'var(--shadow-xs)',
                transition: 'border-color 120ms, box-shadow 120ms',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--primary)';
                e.currentTarget.style.boxShadow = '0 0 0 3px var(--primary-subtle)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--border)';
                e.currentTarget.style.boxShadow = 'var(--shadow-xs)';
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontWeight: 700, color: 'var(--ink)', fontSize: '1rem' }}>{item.name}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--muted)', marginTop: 2 }}>{getKoperasiName(item.koperasi_id)}</div>
                </div>
                {parseFloat(item.current_stock_kg) > 0 ? (
                  <span className="badge badge-active">Tersedia</span>
                ) : (
                  <span className="badge badge-cancelled">Habis</span>
                )}
              </div>

              <div style={{ display: 'flex', gap: 16 }}>
                <div>
                  <div style={{ fontSize: '0.6875rem', color: 'var(--muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Harga / kg</div>
                  <div style={{ fontSize: '1.125rem', fontWeight: 800, color: 'var(--primary-text)', fontFamily: 'var(--font-mono)' }}>{formatRp(item.pihps_price)}</div>
                </div>
                <div>
                  <div style={{ fontSize: '0.6875rem', color: 'var(--muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Stok</div>
                  <div style={{ fontSize: '1.125rem', fontWeight: 800, color: 'var(--ink)', fontFamily: 'var(--font-mono)' }}>
                    {parseFloat(item.current_stock_kg).toLocaleString('id-ID', { maximumFractionDigits: 0 })} kg
                  </div>
                </div>
              </div>

              {item.cold_storage_location && (
                <div style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>📍 {item.cold_storage_location}</div>
              )}

              <button
                id={`order-btn-${item.id}`}
                className="btn btn-primary btn-sm"
                style={{ width: '100%', justifyContent: 'center', marginTop: 4 }}
                disabled={parseFloat(item.current_stock_kg) <= 0}
                onClick={() => setSelectedItem(item)}
              >
                Pesan Sekarang
              </button>
            </div>
          ))}
        </div>
      )}

      {selectedItem && (
        <CheckoutModal
          catalogItem={selectedItem}
          onClose={() => setSelectedItem(null)}
          onSuccess={(order) => {
            setSelectedItem(null);
            onOrderCreated(order);
          }}
        />
      )}
    </>
  );
}

// ─── Orders tab ─────────────────────────────────────────────────────────────
function OrdersTab() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [orderDetail, setOrderDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [mockPayLoading, setMockPayLoading] = useState(null);

  const loadOrders = () => {
    setLoading(true);
    ordersAPI.listMine()
      .then((r) => setOrders(r.data))
      .catch(() => toast.error('Gagal memuat pesanan.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadOrders(); }, []);

  const openDetail = async (id) => {
    setSelected(id);
    setDetailLoading(true);
    try {
      const r = await ordersAPI.getOrder(id);
      setOrderDetail(r.data);
    } catch {
      toast.error('Gagal memuat detail pesanan.');
    } finally {
      setDetailLoading(false);
    }
  };

  const handleMockPay = async (order) => {
    if (!order.xendit_invoice_id) {
      toast.error('Invoice ID tidak tersedia untuk simulasi pembayaran.');
      return;
    }
    setMockPayLoading(order.id);
    try {
      await ordersAPI.mockWebhook({ xendit_invoice_id: order.xendit_invoice_id });
      toast.success('Simulasi pembayaran berhasil! Pesanan sekarang berstatus Paid.');
      loadOrders();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setMockPayLoading(null);
    }
  };

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}><Spinner large /></div>;
  if (orders.length === 0) return (
    <EmptyState
      icon={<ShoppingCartIcon />}
      title="Belum ada pesanan"
      desc="Buat pesanan dari katalog marketplace."
    />
  );

  return (
    <>
      <Alert type="info" style={{ marginBottom: 16, fontSize: '0.8125rem' }}>
        <strong>Mode Demo:</strong> Gunakan tombol <strong>Simulasi Bayar</strong> pada pesanan yang masih pending untuk mensimulasikan pembayaran Xendit.
      </Alert>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Status</th>
              <th>Jenis</th>
              <th>Total</th>
              <th>Pembayaran</th>
              <th>Tanggal</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {orders.map((o) => (
              <tr key={o.id}>
                <td className="td-mono">#{o.id}</td>
                <td><StatusBadge status={o.status} /></td>
                <td style={{ textTransform: 'capitalize' }}>{o.fulfillment_type}</td>
                <td className="td-primary"><Money value={o.total} /></td>
                <td>
                  {o.payment_status
                    ? <span className={`badge ${o.payment_status === 'paid' ? 'badge-paid' : 'badge-pending'}`}>{o.payment_status}</span>
                    : '—'
                  }
                </td>
                <td className="td-muted">{formatDate(o.created_at)}</td>
                <td>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button id={`order-detail-btn-${o.id}`} className="btn btn-secondary btn-xs" onClick={() => openDetail(o.id)}>Detail</button>
                    {o.status === 'pending' && o.payment_status !== 'paid' && (
                      <button
                        id={`mock-pay-btn-${o.id}`}
                        className="btn btn-success btn-xs"
                        onClick={() => handleMockPay(o)}
                        disabled={mockPayLoading === o.id}
                        title="Simulasi pembayaran Xendit (mode dev)"
                      >
                        {mockPayLoading === o.id ? <Spinner /> : '⚡'} Simulasi Bayar
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected && (
        <div className="modal-backdrop" onClick={(e) => e.target === e.currentTarget && setSelected(null)}>
          <div className="modal">
            <div className="modal-header">
              <span className="modal-title">Detail Pesanan #{selected}</span>
              <button className="btn btn-ghost btn-icon btn-sm" onClick={() => { setSelected(null); setOrderDetail(null); }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="15" height="15"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
            <div className="modal-body">
              {detailLoading ? (
                <div style={{ display: 'flex', justifyContent: 'center', padding: 32 }}><Spinner /></div>
              ) : orderDetail ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    {[
                      ['Status', <StatusBadge status={orderDetail.status} />],
                      ['Pengiriman', <span style={{ textTransform: 'capitalize' }}>{orderDetail.fulfillment_type}</span>],
                      ['Subtotal', <Money value={orderDetail.subtotal} />],
                      ['Platform Fee (1.5%)', <Money value={orderDetail.platform_fee} />],
                      ['Total', <Money value={orderDetail.total} />],
                      ['Channel', orderDetail.payment_channel === 'qris' ? '📱 QRIS' : orderDetail.payment_channel === 'va' ? '🏦 Virtual Account' : orderDetail.payment_channel || '—'],
                    ].map(([label, val]) => (
                      <div key={label} style={{ padding: '10px 14px', background: 'var(--surface-2)', borderRadius: 8 }}>
                        <div style={{ fontSize: '0.6875rem', color: 'var(--muted)', fontWeight: 600, marginBottom: 4 }}>{label}</div>
                        <div style={{ fontWeight: 600, color: 'var(--ink)' }}>{val}</div>
                      </div>
                    ))}
                  </div>
                  {orderDetail.delivery_address && (
                    <div style={{ padding: '10px 14px', background: 'var(--surface-2)', borderRadius: 8 }}>
                      <div style={{ fontSize: '0.6875rem', color: 'var(--muted)', fontWeight: 600, marginBottom: 4 }}>Alamat Pengiriman</div>
                      <div style={{ color: 'var(--ink)' }}>{orderDetail.delivery_address}</div>
                    </div>
                  )}
                  {orderDetail.items && orderDetail.items.length > 0 && (
                    <div>
                      <div style={{ fontWeight: 700, color: 'var(--ink)', marginBottom: 10, fontSize: '0.875rem' }}>Item Pesanan</div>
                      {orderDetail.items.map((item) => (
                        <div key={item.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                          <span style={{ color: 'var(--ink-2)' }}>
                            {item.commodity_name || `Komoditas #${item.commodity_id}`} — {item.weight_kg} kg
                          </span>
                          <span style={{ fontWeight: 600, color: 'var(--ink)' }}><Money value={item.line_total} /></span>
                        </div>
                      ))}
                    </div>
                  )}
                  {orderDetail.status === 'pending' && orderDetail.payment_status !== 'paid' && (
                    <button
                      className="btn btn-success"
                      style={{ width: '100%', justifyContent: 'center' }}
                      onClick={() => { handleMockPay(orderDetail); setSelected(null); setOrderDetail(null); }}
                      disabled={mockPayLoading === orderDetail.id}
                    >
                      {mockPayLoading === orderDetail.id ? <Spinner /> : '⚡'} Simulasi Pembayaran
                    </button>
                  )}
                  {orderDetail.payment_url && orderDetail.payment_status !== 'paid' && (
                    <a href={orderDetail.payment_url} target="_blank" rel="noopener noreferrer" className="btn btn-primary" style={{ textAlign: 'center', justifyContent: 'center' }}>
                      Bayar via Xendit
                    </a>
                  )}
                </div>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ─── Main component ──────────────────────────────────────────────────────────
const SECTIONS = ['catalog', 'orders'];

export default function DistributorDashboard({ user, onLogout }) {
  const [active, setActive] = useState('catalog');
  const [orderCount, setOrderCount] = useState(0);

  useEffect(() => {
    ordersAPI.listMine()
      .then((r) => setOrderCount(r.data.length))
      .catch(() => {});
  }, []);

  const nav = [
    {
      id: 'catalog',
      label: 'Katalog',
      active: active === 'catalog',
      onClick: () => setActive('catalog'),
      icon: <StoreIcon />,
    },
    {
      id: 'orders',
      label: 'Pesanan Saya',
      active: active === 'orders',
      onClick: () => setActive('orders'),
      icon: <ShoppingCartIcon />,
      badge: orderCount,
    },
  ];

  const TITLES = {
    catalog: 'Katalog Marketplace',
    orders: 'Pesanan Saya',
  };

  return (
    <AppShell
      user={user}
      onLogout={onLogout}
      navItems={nav}
      topbarTitle={TITLES[active]}
    >
      <PageHeader
        title={TITLES[active]}
        desc={active === 'catalog' ? 'Beli komoditas sayuran dari koperasi mitra' : 'Riwayat dan status pesanan Anda'}
      />

      {active === 'catalog' && (
        <CatalogTab
          onOrderCreated={() => {
            setOrderCount((c) => c + 1);
            setActive('orders');
          }}
        />
      )}
      {active === 'orders' && <OrdersTab />}
    </AppShell>
  );
}
