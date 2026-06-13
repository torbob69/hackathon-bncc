import { useState, useEffect } from 'react';
import AppShell from '../components/AppShell.jsx';
import { Money, StatusBadge, PageHeader, EmptyState, Spinner, formatDate, formatDateTime, getErrorMessage } from '../components/ui.jsx';
import { reportsAPI } from '../api/client.js';
import { toast } from '../hooks/useToast.jsx';

const FileTextIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>
  </svg>
);

const TrendingUpIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>
  </svg>
);

function formatRp(val) {
  if (val == null) return '—';
  return 'Rp ' + (parseFloat(val) || 0).toLocaleString('id-ID', { maximumFractionDigits: 0 });
}

function PortfolioCard({ report }) {
  const koperasiId = report.koperasi_id;
  const data = report.data || {};
  const fields = report.fields_included || Object.keys(data);

  return (
    <div className="card" style={{ marginBottom: 0 }}>
      <div className="card-header">
        <div>
          <div className="card-title">Koperasi #{koperasiId}</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--muted)', marginTop: 2 }}>
            {formatDate(report.date_range_start)} — {formatDate(report.date_range_end)}
          </div>
        </div>
        <span className="badge badge-active">Grant Aktif</span>
      </div>
      <div className="card-body">
        {fields.length === 0 ? (
          <div style={{ color: 'var(--muted)', fontSize: '0.875rem' }}>Tidak ada data yang diberikan akses.</div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
            {fields.map((field) => {
              const val = data[field];
              const label = {
                gmv: 'GMV',
                loan_volume: 'Volume Pinjaman',
                npl_rate: 'NPL Rate',
                farmer_count: 'Jumlah Petani',
                active_loan_count: 'Pinjaman Aktif',
              }[field] || field;

              const isPercent = field === 'npl_rate';
              const isMoney = ['gmv', 'loan_volume'].includes(field);

              return (
                <div key={field} style={{ padding: '14px 16px', background: 'var(--surface-2)', borderRadius: 10, border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: '0.6875rem', color: 'var(--muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>
                    {label}
                  </div>
                  <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--ink)', fontFamily: 'var(--font-mono)', letterSpacing: '-0.02em' }}>
                    {val == null ? '—' : isMoney ? formatRp(val) : isPercent ? `${parseFloat(val).toFixed(2)}%` : val.toLocaleString('id-ID')}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default function FinancingDashboard({ user, onLogout }) {
  const [active, setActive] = useState('portfolio');
  const [portfolio, setPortfolio] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (active === 'portfolio') {
      setLoading(true);
      reportsAPI.portfolio()
        .then((r) => { setPortfolio(r.data); setError(''); })
        .catch((err) => setError(getErrorMessage(err)))
        .finally(() => setLoading(false));
    }
  }, [active]);

  const nav = [
    {
      id: 'portfolio',
      label: 'Laporan Portofolio',
      active: active === 'portfolio',
      onClick: () => setActive('portfolio'),
      icon: <TrendingUpIcon />,
    },
  ];

  return (
    <AppShell
      user={user}
      onLogout={onLogout}
      navItems={nav}
      topbarTitle="Laporan Portofolio"
    >
      <PageHeader
        title="Laporan Portofolio Koperasi"
        desc="Data yang dibagikan kepada Anda sesuai grant yang diberikan admin koperasi"
      />

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 80 }}><Spinner large /></div>
      ) : error ? (
        <div className="alert alert-danger">{error}</div>
      ) : portfolio.length === 0 ? (
        <EmptyState
          icon={<FileTextIcon />}
          title="Belum ada laporan"
          desc="Admin koperasi belum memberikan akses data kepada akun Anda."
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div style={{ padding: '12px 16px', background: 'var(--info-bg)', borderRadius: 10, border: '1px solid var(--info-border)', fontSize: '0.875rem', color: 'var(--info)' }}>
            <strong>ℹ️</strong> Data ditampilkan sesuai dengan scope dan periode yang telah diotorisasi oleh admin masing-masing koperasi.
          </div>
          {portfolio.map((report, i) => (
            <PortfolioCard key={i} report={report} />
          ))}
        </div>
      )}
    </AppShell>
  );
}
