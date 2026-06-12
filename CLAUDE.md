# MELATI JAYA — Koperasi Tani Platform

> Guidance for Claude Code and the team building this project. Business + technical reference.
> Source-of-truth planning docs live in `context/` — this file summarizes and operationalizes them. Do not duplicate hackathon rules here; see `context/case study.md` and `context/guidebook.md`.

---

## 1. Project Overview

**MELATI JAYA** is a multi-tenant digital platform for Indonesian farmer cooperatives (koperasi tani). It replaces the error-prone Excel bookkeeping that loses stock data, and adds a B2B marketplace, member lending, and anti-fraud auditing.

**Context:** Built for **TechnoScape 2026** (BNCC) fintech hackathon — onsite final **12–14 June 2026**. Judged on two axes:
- **Technology:** architecture/design (25%), feature completeness (25%), low-bug/accuracy (25%), real implementation (20%).
- **Business:** problem/market fit (25%), competitive edge (25%), monetization (20%), presentation (15%), sustainability (15%).

**Chosen koperasi:** **Melati Jaya** — *sayuran & cold storage*. Pain: manual Excel records, incomplete/lost stock data.

**The multi-tenant twist (from `context/case study.md`):** the original system broke when a 2nd/3rd koperasi joined (data bercampur), and a financing partner asked for portfolio data the team couldn't scope. So **per-koperasi data isolation** and **controlled portfolio reporting to financing partners** are first-class, graded requirements — not afterthoughts.

---

## 2. Business Side

### 2.1 Problem → Solution
- **Problem:** stock data lost/corrupt in Excel; manual records; no fraud visibility; can't scale across koperasi; financing partners can't get scoped data.
- **Solution:** digital records with a DB, prices locked to PIHPS reference (anti-manipulation), immutable audit trail, a multi-koperasi B2B marketplace, and member lending with data-driven credit scoring.

### 2.2 Entities & Roles
1. **Koperasi** — tenant; stores & sells commodities; appears in marketplace.
2. **Farmer (Petani)** — registered member of one koperasi; deposits harvest, can borrow.
3. **Manajer** — passive verifier (re-weigh, scan, confirm); cannot change price.
4. **Admin** — validates farmer signup, audits loans.
5. **Buyer / Distributor** — B2B buyer; can purchase from any koperasi.
6. **Financing Partner** — receives scoped portfolio data via explicit grants.
7. **Platform Admin** — operates the platform across tenants.

> Farmers are **bound members of one koperasi** (KSP basis — see §3.7).

### 2.3 Business Model & Monetization
- **A. Koperasi trading margin** (~33–39% gross): buy from farmer at PIHPS, sell B2B at margin.
- **B. Platform transaction fee — flat 1–2% on ALL koperasi B2B transactions. No tiers.** Free to use, pay only on transactions; grows with GMV.
- **C. Roadmap:** member-loan interest; anonymized credit-data licensing to UMKM banks.

### 2.4 Treasury Model — Two Separated Pools (per koperasi)
| Pool | Funded by | Used for | Rule |
|---|---|---|---|
| **Marginal Profit Pool** | trading margin | **buying farmer harvest** (operational) | only source for harvest purchases |
| **Loan Pool** | **APBN / government grants only** | **farmer loans** | only source for loans; never funded by trading margin |

**The pools never cross-fund.** Loan eligibility checks against the Loan Pool only; harvest purchases against the Marginal Profit Pool only. This is enforced in the ledger (`ledger_entries.pool`).

### 2.5 Harvest Buy-Decision (oversupply prevention)
When a farmer deposits harvest, the koperasi **decides to buy or not** (manager accepts/rejects). The farmer sees status **live** (`pending` → `confirmed` / `rejected`). If the intake value **exceeds the available Marginal Profit Pool**, the system **alerts the farmer** (soft warning + flags it for the manager) so they aren't left waiting on an unaffordable purchase. This prevents the koperasi from over-committing when it lacks funds.

### 2.6 Sustainability & Metrics
Track: **GMV per koperasi**, active farmer rate, loan disbursement volume, **NPL (non-performing loan) rate**. Natural retention via data lock-in (historical records live on-platform). Competitive edge: alternative-data credit scoring banks can't replicate + anti-fraud price-locking.

---

## 3. Technical Side

### 3.1 Architecture
```
React + Tailwind (Vercel)
        │  HTTPS / JSON
        ▼
FastAPI (Railway)  ──►  MySQL (Railway)
        │                     
        ├──► Cloudinary  (KTP/SIM photos, doc uploads)
        └──► Xendit      (split payments, QRIS/VA, disbursements)
```
Frontend and backend are separate deploys. Mobile-first PWA (managers & farmers scan QR on phones).

### 3.2 Multi-Tenancy (critical, graded)
- **Every domain row carries `koperasi_id`.** MySQL has no row-level security, so isolation is enforced in the **service/query layer**: a FastAPI dependency derives the caller's tenant from their JWT and **all queries are scoped by `koperasi_id`**. Never run a domain query without a tenant filter.
- Cross-tenant entities: `distributors`, `financing_partners`, and `users` with role `distributor`/`platform_admin`.
- Distributors browse across koperasi (marketplace) but only see published catalog data.

### 3.3 Auth & Roles
- **JWT** auth. Use a boilerplate (`fastapi-users` or `python-jose` + `passlib[bcrypt]`) — **do not hand-roll**. Token carries `user_id`, `role`, `koperasi_id`.
- Role-based dependencies guard endpoints; tenant-scope dependency guards data.

### 3.4 Payment Architecture
- **`PaymentProvider` interface** with two implementations selected by `MODE`:
  - **`MockXenditProvider`** (`MODE=dev`) — deterministic: instant "paid" invoices, fake disbursement IDs, **no QRIS cap**, simulated webhooks. Lets the full money flow be demoed offline.
  - **`XenditProvider`** (`MODE=prod`) — real Xendit.
- **Sales:** Xendit **direct + split payment** — distributor checkout settles directly; the **1–2% platform fee is split off**, remainder to the koperasi's Xendit account. No in-app custody.
- **QRIS cap:** orders ≤ **Rp 10 jt/day** use **QRIS**; larger orders fall back to **Virtual Account**.
- **Farmer payments & loan disbursements:** Xendit **Disbursement API**, mirrored in `ledger_entries` for the transparency view and audit.
- **TODO (not blocking):** finalize split mechanism — Xendit "for Platforms" managed sub-accounts vs invoice-level fees.

### 3.5 QR Codes (anti-fraud)
QR payloads are **JWT-signed** by the backend. Scanning verifies the signature → this is the "asli/palsu" check in harvest intake and pickup. Harvest QR holds commodity, farmer, weight; pickup QR holds order reference. Never trust an unsigned/expired QR.

### 3.6 Credit Scoring (no ML)
Plain SQL aggregation + weighted formula:
- total harvest weight (last 6 months),
- transaction frequency & cash inflow from koperasi,
- active arrears.
Maps to a **tier → limit**. Snapshot stored in `credit_scores`.

### 3.7 Lending (member-only, KSP basis)
Loans only to **registered members** of the borrower's koperasi → operates as **Koperasi Simpan Pinjam (KSP)** (Kementerian Koperasi), not OJK P2P. Conservative default assumptions (model 15–20% default). Collateral must be legally enforceable (fidusia/agunan), not just a ToS checkbox. Disbursed from the **Loan Pool only**.

### 3.8 Audit Trail & Portfolio Reporting
- **`audit_log`** is append-only (no UPDATE/DELETE) — drives anomaly/fraud detection for kasir transactions.
- **`data_share_grants`** scope exactly which fields/aggregates and date-range a financing partner may see — the case-study requirement. Reporting endpoints must read the grant and never exceed its `scope_json`.

---

## 4. Database Schema (MySQL, multi-tenant)

All domain tables carry `koperasi_id` (FK) and timestamps. Cross-tenant: `distributors`, `financing_partners`, and `users` (distributor/platform_admin).

| Table | Key columns |
|---|---|
| **koperasi** *(tenant root)* | id, name, type, address, region, `xendit_account_id`, created_at |
| **users** | id, `koperasi_id` (nullable), role ENUM(`farmer`,`manager`,`admin`,`distributor`,`financing_partner`,`platform_admin`), name, email (unique), phone, password_hash, status |
| **farmers** | user_id (FK), koperasi_id, nik, address, `ktp_photo_url`, credit_tier, status(`pending`/`active`), verified_by, verified_at |
| **distributors** | user_id (FK), company_name, address, phone |
| **commodities** | id, koperasi_id, name, unit(`kg`), `pihps_price`, `current_stock_kg`, cold_storage_location |
| **harvest_intakes** | id, koperasi_id, farmer_id, commodity_id, weight_kg, `qr_token`, status(`pending`/`confirmed`/`rejected`), `estimated_value`, `exceeds_pool_flag`, reject_reason, price_per_kg, total_paid, confirmed_by, confirmed_at, created_at |
| **stock_movements** | id, koperasi_id, commodity_id, direction(`in`/`out`), weight_kg, reference_type, reference_id, qr_token, created_by, created_at |
| **orders** | id, koperasi_id, distributor_id, status, fulfillment_type(`delivery`/`pickup`), delivery_address, subtotal, `platform_fee`, total, `xendit_invoice_id`, `payment_channel`(`qris`/`va`), payment_status, `pickup_qr_token`, created_at |
| **order_items** | id, order_id, commodity_id, weight_kg, price_per_kg, line_total |
| **ledger_entries** | id, koperasi_id, `pool`(`marginal_profit`/`loan`), type(`sale_settlement`/`farmer_payment`/`platform_fee`/`apbn_grant`/`loan_disbursement`/`loan_repayment`), amount, direction(`credit`/`debit`), reference_type, reference_id, `xendit_disbursement_id`, balance_after, created_at |
| **koperasi_funds** | koperasi_id (PK), `marginal_profit_pool_balance`, `loan_pool_balance`, updated_at |
| **loans** | id, koperasi_id, farmer_id, principal, purpose(`benih`/`pupuk`/`alat`), installment_months, interest_rate, status(`pending`/`active`/`past_due`/`paid`/`rejected`/`seized`), credit_score, limit_at_application, approved_by, disbursed_at, `xendit_disbursement_id`, created_at |
| **loan_installments** | id, loan_id, due_date, amount_due, amount_paid, status(`unpaid`/`paid`/`late`), paid_at |
| **loan_status_history** | id, loan_id, old_status, new_status, changed_by, reason, created_at |
| **credit_scores** | id, farmer_id, score, tier, harvest_weight_6mo, txn_count, active_arrears, computed_at |
| **audit_log** *(immutable)* | id, koperasi_id, actor_user_id, action, entity_type, entity_id, before_json, after_json, ip, created_at |
| **financing_partners** | id, name, contact_email |
| **data_share_grants** | id, koperasi_id, financing_partner_id, scope_json, date_range_start, date_range_end, status(`active`/`revoked`), granted_by, created_at |

**Pool invariant:** `apbn_grant` / `loan_disbursement` / `loan_repayment` entries only touch the `loan` pool; `sale_settlement` / `farmer_payment` / `platform_fee` only touch `marginal_profit`. `koperasi_funds` balances are derived from `ledger_entries`.

**Key indexes:** every `koperasi_id`; `users.email` unique; `harvest_intakes.qr_token` & `orders.pickup_qr_token` unique; `loan_installments(loan_id, due_date)`; `ledger_entries(koperasi_id, created_at)`.

---

## 5. Tech Stack & Hosting

| Layer | Tech | Host |
|---|---|---|
| Frontend | React + Tailwind (Vite), mobile-first PWA | **Vercel** |
| Backend | FastAPI (Python), SQLAlchemy 2.0 + Alembic, Pydantic v2 | **Railway** |
| Database | MySQL | **Railway** |
| File storage | Cloudinary (KTP/SIM photos) | — |
| Payments | Xendit (split, QRIS/VA, disbursement) | — |
| QR | backend `qrcode` + JWT signing; frontend `html5-qrcode` scan | — |

### Environment variables
| Var | Purpose |
|---|---|
| `MODE` | `dev` (mock payments) or `prod` (real Xendit) |
| `DATABASE_URL` | MySQL connection (Railway) |
| `JWT_SECRET` | token signing |
| `XENDIT_SECRET_KEY` | Xendit API (prod only) |
| `XENDIT_CALLBACK_TOKEN` | verify Xendit webhooks (prod only) |
| `CLOUDINARY_URL` | Cloudinary credentials |
| `FRONTEND_URL` | CORS allowed origin |

---

## 6. Planned Repo Structure
```
/
├── CLAUDE.md
├── context/                # planning docs (source of truth)
├── backend/                # FastAPI
│   ├── app/
│   │   ├── main.py
│   │   ├── core/           # config (MODE), security/JWT, tenant dependency
│   │   ├── models/         # SQLAlchemy
│   │   ├── schemas/        # Pydantic
│   │   ├── api/            # routers per domain
│   │   ├── services/       # business logic (pools, scoring, ledger)
│   │   └── payments/       # PaymentProvider + Xendit/Mock impls
│   ├── alembic/            # migrations
│   └── requirements.txt
└── frontend/               # React + Tailwind (Vite)
    └── src/{pages,components,api,hooks}
```
> Dev commands (install/run/migrate) to be filled in once scaffolding exists.

---

## 7. Build Roadmap (vertical slices — happy path first)
1. **Schema + migrations** (Alembic) for all tables above.
2. **Auth + roles + tenant scoping** (boilerplate).
3. **Core loop:** harvest intake → JWT-signed QR → manager confirm (with pool check + buy-decision) → pay farmer from Marginal Profit Pool → ledger entry.
4. **Marketplace:** distributor browse → checkout (Xendit split, QRIS/VA) → 1–2% fee → pickup/delivery with signed QR.
5. **Loan lifecycle:** apply → credit score → eligibility (Loan Pool check) → admin audit → disburse → installments → past-due/seize, with `loan_status_history`.
6. **Audit log + anomaly view**, **transparansi dana** (two-pool view), **portfolio reporting** via `data_share_grants`.

Build each slice end-to-end before polishing UI — a working vertical slice demos far better than half-finished features.

---

## 8. Conventions for Claude Code
- **Never query a domain table without a `koperasi_id` tenant filter.** Isolation is a graded requirement.
- **Enforce the pool invariant** in services — money for harvest comes only from Marginal Profit Pool; loans only from Loan Pool (APBN).
- **Prices are PIHPS-locked**; managers/kasir cannot edit prices — keep that path closed.
- **All money movements write a `ledger_entry`**; balances derive from the ledger, not ad-hoc updates.
- **`audit_log` is append-only** — no updates/deletes.
- **All payment calls go through `PaymentProvider`** — never call Xendit directly from a route, so `MODE=dev` mocking stays intact.
- Match existing code's style as it grows; keep business logic in `services/`, not routers.
