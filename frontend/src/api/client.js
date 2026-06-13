import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('koperalink_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('koperalink_token');
      window.location.href = '/';
    }
    return Promise.reject(err);
  }
);

export default api;

// ─── Auth ───────────────────────────────────────────────────────────────────
export const authAPI = {
  login: (identifier, password) =>
    api.post('/auth/login', { identifier, password }),
  me: () => api.get('/auth/me'),
  signupDistributor: (data) => api.post('/auth/signup/distributor', data),
  activate: (token, password) => api.post('/auth/activate', { token, password }),
};

// ─── Intakes ─────────────────────────────────────────────────────────────────
export const intakesAPI = {
  create: (data) => api.post('/intakes', data),
  listMine: (status) => api.get('/intakes/mine', { params: status ? { status } : {} }),
  listAll: (status) => api.get('/intakes', { params: status ? { status } : {} }),
  get: (id) => api.get(`/intakes/${id}`),
  confirm: (id, weight_kg) => api.post(`/intakes/${id}/confirm`, { weight_kg }),
  reject: (id, reason) => api.post(`/intakes/${id}/reject`, { reason }),
  verifyQR: (token) => api.post('/intakes/verify-qr', { token }),
};

// ─── Commodities ─────────────────────────────────────────────────────────────
export const commoditiesAPI = {
  list: () => api.get('/commodities'),
  create: (data) => api.post('/commodities', data),
  update: (id, data) => api.patch(`/commodities/${id}`, data),
  delete: (id) => api.delete(`/commodities/${id}`),
};

// ─── Orders ──────────────────────────────────────────────────────────────────
export const ordersAPI = {
  catalog: (params) => api.get('/marketplace/catalog', { params }),
  checkout: (data) => api.post('/marketplace/orders', data),
  listMine: () => api.get('/marketplace/orders'),
  getOrder: (id) => api.get(`/marketplace/orders/${id}`),
  listKoperasi: (status) => api.get('/orders', { params: status ? { status_filter: status } : {} }),
  getKoperasiOrder: (id) => api.get(`/orders/${id}`),
  verifyPickup: (token) => api.post('/orders/pickup/verify', { token }),
  fulfillDelivery: (id) => api.post(`/orders/${id}/fulfill-delivery`),
  mockWebhook: (data) => api.post('/webhooks/xendit/mock-invoice', data),
};

// ─── Loans ───────────────────────────────────────────────────────────────────
export const loansAPI = {
  apply: (data) => api.post('/loans', data),
  listMine: () => api.get('/loans'),
  get: (id) => api.get(`/loans/${id}`),
  repay: (id, installment_id, amount) =>
    api.post(`/loans/${id}/repay`, { installment_id, amount }),
};

// ─── Admin: Farmers ──────────────────────────────────────────────────────────
export const adminFarmersAPI = {
  create: (data) => api.post('/admin/farmers', data),
  list: (status) => api.get('/admin/farmers', { params: status ? { status } : {} }),
  get: (id) => api.get(`/admin/farmers/${id}`),
  approve: (id) => api.post(`/admin/farmers/${id}/approve`),
  reject: (id, reason) => api.post(`/admin/farmers/${id}/reject`, { reason }),
};

// ─── Admin: Loans ────────────────────────────────────────────────────────────
export const adminLoansAPI = {
  list: (status) => api.get('/admin/loans', { params: status ? { status } : {} }),
  get: (id) => api.get(`/admin/loans/${id}`),
  approve: (id) => api.post(`/admin/loans/${id}/approve`),
  reject: (id, reason) => api.post(`/admin/loans/${id}/reject`, { reason }),
  seize: (id, reason) => api.post(`/admin/loans/${id}/seize`, { reason }),
  markPastDue: () => api.post('/admin/loans/mark-past-due'),
};

// ─── Admin: Funds ────────────────────────────────────────────────────────────
export const adminFundsAPI = {
  get: () => api.get('/admin/funds'),
  apbnGrant: (amount, note) => api.post('/admin/funds/apbn-grant', { amount, note }),
  marginalDummy: (amount, note) => api.post('/admin/funds/marginal-dummy', { amount, note }),
  ledger: (params) => api.get('/admin/ledger', { params }),
};

// ─── Admin: Oversight ────────────────────────────────────────────────────────
export const adminOversightAPI = {
  auditLog: (params) => api.get('/admin/audit-log', { params }),
  dashboard: () => api.get('/admin/dashboard'),
};

// ─── Koperasi ────────────────────────────────────────────────────────────────
export const koperasiAPI = {
  myProfile: () => api.get('/koperasi/me/profile'),
  list: () => api.get('/koperasi'),
  get: (id) => api.get(`/koperasi/${id}`),
  create: (data) => api.post('/koperasi', data),
  update: (id, data) => api.patch(`/koperasi/${id}`, data),
};

// ─── Reports ─────────────────────────────────────────────────────────────────
export const reportsAPI = {
  portfolio: () => api.get('/reports/portfolio'),
  anomalies: () => api.get('/reports/anomalies'),
  grants: () => api.get('/reports/grants'),
  createGrant: (data) => api.post('/reports/grants', data),
  revokeGrant: (id) => api.post(`/reports/grants/${id}/revoke`),
};

// ─── Platform Admin ──────────────────────────────────────────────────────────
export const platformAPI = {
  createStaff: (koperasiId, data) => api.post(`/koperasi/${koperasiId}/staff`, data),
  listStaff: (koperasiId) => api.get(`/koperasi/${koperasiId}/staff`),
};

// ─── Notifications ──────────────────────────────────────────────────────────
export const notificationsAPI = {
  list: (unread_only = false) => api.get('/notifications', { params: { unread_only } }),
  unreadCount: () => api.get('/notifications/unread-count'),
  markRead: (id) => api.post(`/notifications/${id}/read`),
  markAllRead: () => api.post('/notifications/read-all'),
};
