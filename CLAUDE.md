# KOPERALINK — Koperasi Tani Platform

> Guidance for Claude Code and the team building this project. Business + technical reference.
> Source-of-truth planning docs live in `context/` — this file summarizes and operationalizes them. Do not duplicate hackathon rules here; see `context/case study.md` and `context/guidebook.md`.

---

## 1. Project Overview

**KOPERALINK** is a multi-tenant digital platform for Indonesian farmer cooperatives (koperasi tani). It replaces the error-prone Excel bookkeeping that loses stock data, and adds a B2B marketplace, member lending, and anti-fraud auditing.

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
FastAPI (Railway)  ──►  PostgreSQL (Supabase)
        │                     
        ├──► Cloudinary  (KTP/SIM photos, doc uploads)
        └──► Xendit      (split payments, QRIS/VA, disbursements)
```
Frontend and backend are separate deploys. Mobile-first PWA (managers & farmers scan QR on phones).

### 3.2 Multi-Tenancy (critical, graded)
- **Every domain row carries `koperasi_id`.** Isolation is enforced in the **service/query layer**: a FastAPI dependency derives the caller's tenant from their JWT and **all queries are scoped by `koperasi_id`**. Never run a domain query without a tenant filter. (PostgreSQL has native RLS but we do not rely on it — service-layer scoping is the enforced boundary.)
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

## 4. Database Schema (PostgreSQL / Supabase, multi-tenant)

All domain tables carry `koperasi_id` (FK) and timestamps. Cross-tenant: `distributors`, `financing_partners`, and `users` (distributor/financing_partner/platform_admin).

### Type & money conventions (mandatory — fintech correctness)
- **Money** = `DECIMAL(18,2)` (SQLAlchemy `Numeric(18,2, asdecimal=True)`). **Never `FLOAT`.** Applies to every amount/balance/price/fee column.
- **Weight** = `DECIMAL(10,3)` (gram precision). Scores/rates = `DECIMAL(5,2)`.
- **Timestamps** = `TIMESTAMP WITH TIME ZONE` (`TIMESTAMPTZ`) stored in **UTC** (SQLAlchemy `DateTime(timezone=True)`); convert to WIB in the frontend only. Calendar-only fields (e.g. `due_date`) = `DATE`.
- **IDs** = `BIGINT`. **`nik`** = `VARCHAR(16)` `UNIQUE` (`CHECK (nik ~ '^[0-9]{16}$')`). **QR tokens** = `TEXT` (no 255-char limit needed on PostgreSQL).
- Enums use PostgreSQL native `ENUM` types via SQLAlchemy `Enum` (adding a value needs an Alembic migration with `op.execute("ALTER TYPE ...")`). No minimum version requirement — `CHECK` constraints are enforced on all modern PostgreSQL.

| Table | Key columns |
|---|---|
| **koperasi** *(tenant root)* | id, name, type, address, region, `xendit_account_id`, created_at |
| **users** | id, `koperasi_id` (FK, nullable), role ENUM(`farmer`,`manager`,`admin`,`distributor`,`financing_partner`,`platform_admin`), name, email (**unique**), phone, password_hash, status. *`koperasi_id` is set for **manager/admin only**; for farmers it is null (koperasi comes from `farmers.koperasi_id` — single source of truth); null for distributor/financing_partner/platform_admin* |
| **farmers** | user_id (FK, **unique**), **koperasi_id (FK — canonical tenant for a farmer)**, `nik` (unique), address, `ktp_photo_url`, credit_tier, status(`pending`/`active`), verified_by, verified_at |
| **distributors** | user_id (FK, **unique**), company_name, address *(phone removed — use `users.phone`)* |
| **commodities** | id, koperasi_id, name, unit(`kg`), `pihps_price`, `current_stock_kg` *(cached from `stock_movements`; update in same txn)*, cold_storage_location |
| **harvest_intakes** | id, koperasi_id, farmer_id, commodity_id, weight_kg, `qr_token` (unique), status(`pending`/`confirmed`/`rejected`/`cancelled`), `estimated_value`, `exceeds_pool_flag`, reject_reason, price_per_kg *(system-set from `commodities.pihps_price` at confirm — never from request)*, total_paid, confirmed_by, confirmed_at, created_at |
| **stock_movements** | id, koperasi_id, commodity_id, direction(`in`/`out`), weight_kg, reference_type, reference_id, qr_token, created_by, created_at |
| **orders** | id, koperasi_id, distributor_id, status(`pending`/`paid`/`fulfilled`/`cancelled`), fulfillment_type(`delivery`/`pickup`), delivery_address, subtotal, `platform_fee`, total, `xendit_invoice_id` (**unique**), `payment_channel`(`qris`/`va`), payment_status, `pickup_qr_token` (unique, `VARCHAR(512)`), created_at |
| **order_items** | id, order_id (FK), **koperasi_id (FK — tenant-safe direct queries)**, commodity_id, weight_kg, price_per_kg, line_total. *Service must assert `commodity.koperasi_id == orders.koperasi_id`* |
| **ledger_entries** | id, koperasi_id, `pool`(`marginal_profit`/`loan`), type(`sale_settlement`/`farmer_payment`/`platform_fee`/`apbn_grant`/`loan_disbursement`/`loan_repayment`/`refund`), amount, direction(`credit`/`debit`), reference_type, reference_id, `xendit_disbursement_id` (unique-where-not-null), **`external_idempotency_key` VARCHAR(128) (unique-where-not-null)**, balance_after *(display snapshot only — never the source of truth for checks)*, created_at. **`CHECK chk_pool_type`** binds `pool`↔`type` (see invariant) |
| **koperasi_funds** | koperasi_id (PK, FK), `marginal_profit_pool_balance`, `loan_pool_balance`, updated_at. *Authoritative cached balance; every read for a sufficiency check uses `SELECT … FOR UPDATE` inside the ledger-write txn* |
| **loans** | id, koperasi_id, farmer_id, principal, purpose(`benih`/`pupuk`/`alat`), installment_months, interest_rate, status(`pending`/`active`/`past_due`/`paid`/`rejected`/`seized`), credit_score, limit_at_application, approved_by, disbursed_at, `xendit_disbursement_id` (**unique**), created_at |
| **loan_installments** | id, loan_id (FK), **koperasi_id (FK)**, due_date (`DATE`), amount_due, amount_paid, status(`unpaid`/`paid`/`late`), `ledger_entry_id` (FK, nullable — links repayment), paid_at |
| **loan_status_history** | id, loan_id (FK), **koperasi_id (FK)**, old_status, new_status, changed_by, reason, created_at |
| **credit_scores** | id, farmer_id (FK), **koperasi_id (FK)**, score, tier, harvest_weight_6mo, txn_count, active_arrears, computed_at |
| **audit_log** *(append-only)* | id, koperasi_id, actor_user_id, action, entity_type, entity_id, before_json, after_json, ip, created_at. *Enforced append-only: app DB role has INSERT/SELECT only + `BEFORE UPDATE/DELETE` trigger raises `RAISE EXCEPTION` (PL/pgSQL)* |
| **financing_partners** | id, **`user_id` (FK→users, unique — login bridge for report auth)**, name, contact_email |
| **data_share_grants** | id, koperasi_id, financing_partner_id (FK), scope_json *(validated against a Pydantic allow-list — never trusted raw)*, date_range_start, date_range_end, status(`active`/`revoked`), granted_by, created_at |
| **xendit_webhook_events** *(idempotency inbox)* | id, `event_id` VARCHAR(128) (**unique**), event_type, reference_type, reference_id, payload JSON, status(`received`/`processed`/`duplicate`), received_at, processed_at |
| **notifications** | id, koperasi_id, user_id (FK), type(`intake_flagged`/`intake_confirmed`/`intake_rejected`/`loan_status`), reference_type, reference_id, message, is_read (default false), created_at |

**Pool invariant (DB-enforced):** `apbn_grant`/`loan_disbursement`/`loan_repayment` entries only touch the `loan` pool; `sale_settlement`/`farmer_payment`/`platform_fee`/`refund` only touch `marginal_profit`. Enforced by `ledger_entries.chk_pool_type` CHECK + service layer. `koperasi_funds` is the authoritative cached balance; a daily reconcile job recomputes from `ledger_entries` and alerts on drift.

**Concurrency rule:** any pool sufficiency check (harvest confirm against Marginal Profit Pool; loan disburse against Loan Pool) must `SELECT … FOR UPDATE` the `koperasi_funds` row, check, write the `ledger_entry`, and update the balance — all in **one transaction**. This serializes per-koperasi and prevents overdraft.

**Idempotency rule:** every Xendit webhook lands in `xendit_webhook_events` first (`INSERT … ON CONFLICT (event_id) DO NOTHING`); skip if already present. Ledger writes from webhooks carry `external_idempotency_key` so a replay can't double-post.

**Key indexes:** every `koperasi_id`; `users.email` unique; `farmers.nik` unique; `harvest_intakes.qr_token` & `orders.pickup_qr_token` unique; `orders.xendit_invoice_id` unique; `loans.xendit_disbursement_id` unique; `ledger_entries.external_idempotency_key` unique-where-not-null; `xendit_webhook_events.event_id` unique; `loan_installments(loan_id, due_date)`; `credit_scores(farmer_id, computed_at DESC)`; `ledger_entries(koperasi_id, created_at)`.

---

## 5. Tech Stack & Hosting

| Layer | Tech | Host |
|---|---|---|
| Frontend | React + Tailwind (Vite), mobile-first PWA | **Vercel** |
| Backend | FastAPI (Python), SQLAlchemy 2.0 async (`asyncpg`) + Alembic, Pydantic v2 | **Railway** |
| Database | PostgreSQL | **Supabase** |
| File storage | Cloudinary (KTP/SIM photos) | — |
| Payments | Xendit (split, QRIS/VA, disbursement) | — |
| QR | backend `qrcode` + JWT signing; frontend `html5-qrcode` scan | — |

### Environment variables
| Var | Purpose |
|---|---|
| `MODE` | `dev` (mock payments) or `prod` (real Xendit) |
| `DATABASE_URL` | PostgreSQL connection string (Supabase) — format: `postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DBNAME` |
| `JWT_SECRET` | token signing |
| `XENDIT_SECRET_KEY` | Xendit API (prod only) |
| `XENDIT_CALLBACK_TOKEN` | verify Xendit webhooks (prod only) |
| `CLOUDINARY_URL` | Cloudinary credentials |
| `FRONTEND_URL` | CORS allowed origin |

---

## 6. Repo Structure
```
/
├── CLAUDE.md
├── .env.example            # template — real .env is gitignored, never commit secrets
├── context/                # planning docs (source of truth)
├── backend/                # FastAPI
│   ├── app/
│   │   ├── main.py             # app factory, router registration, health check
│   │   ├── core/              # config (MODE/settings), security/JWT, deps (tenant scope, RBAC)
│   │   ├── db/                # engine, session, Base
│   │   ├── models/            # SQLAlchemy models (one module per domain)
│   │   ├── schemas/           # Pydantic request/response models
│   │   ├── api/               # routers per domain (auth, koperasi, farmers, commodities,
│   │   │                      #   intakes, orders, loans, ledger, reports)
│   │   ├── services/          # business logic — pools, ledger, credit scoring, scoring guards
│   │   └── payments/          # PaymentProvider interface + XenditProvider + MockXenditProvider
│   ├── alembic/               # migrations
│   ├── tests/
│   └── requirements.txt
└── frontend/               # React + Tailwind (Vite), mobile-first PWA — ONE unified app
    └── src/
        ├── routes/
        │   ├── farmer/        # /app/farmer/*       — intake, my-status, loans
        │   ├── manager/       # /app/manager/*      — confirm queue, stock, pickup scan
        │   ├── admin/         # /app/admin/*        — signup validation, loan audit, funds
        │   └── marketplace/   # /marketplace/*      — distributor: browse, checkout, orders
        ├── components/        # shared: QRScanner, MoneyDisplay, DataTable, StatusBadge…
        ├── layouts/           # RoleLayout selects nav/shell by JWT role
        ├── guards/            # RequireRole route guard (UX gate only — backend is the real boundary)
        ├── api/               # shared API client (auth header, tenant context)
        └── hooks/
```
**Frontend decision:** one unified app with **role-scoped route groups**, not separate apps per actor. Role gating in the UI is UX only — authorization is always enforced server-side (tenant scoping in `core/deps`). Distributor/marketplace routes sit under their own top-level group so a future public/ops split is a clean lift.

> Dev commands (install/run/migrate) to be filled in once scaffolding exists.

---

## 7. Backend Build Timeline — 15 Phases

Ordered by **dependency + ascending complexity** (easiest first). Each phase should be independently runnable and demoable. Don't start a phase until the previous one is green.

| # | Phase | Goal / Deliverables | Tables / Modules | Done when |
|---|---|---|---|---|
| 1 | **Scaffold & config** | FastAPI app factory, settings loading `MODE`, CORS, `/health` endpoint, requirements.txt | `main.py`, `core/config.py` | `GET /health` returns 200; `MODE` read from env |
| 2 | **DB & migrations setup** | `create_async_engine` + `AsyncSession` (`DateTime(timezone=True)`, UTC), `Base`, Alembic init (sync URL for migrations), Supabase PostgreSQL connection. Provision a **restricted app DB role** in Supabase (no UPDATE/DELETE on `audit_log` — set in phase 15) | `db/`, `alembic/` | empty migration runs; `SELECT version()` confirms PostgreSQL |
| 3 | **Core models + first migration** | `koperasi`, `users`, `farmers`, `financing_partners` (**with `user_id` FK**), `koperasi_funds`, base enums. **All money cols `Numeric(18,2)`, weights `Numeric(10,3)`, `nik VARCHAR(16) UNIQUE`** — verify before migrating. `users.koperasi_id` for manager/admin only | `models/` | tables exist with correct DECIMAL types; no FLOAT money cols |
| 4 | **Auth** | JWT signup/login, password hashing (bcrypt), role enum on token | `core/security.py`, `api/auth.py` | login returns a JWT with role + koperasi_id |
| 5 | **Tenant scoping + RBAC** | `get_current_user`, tenant-scope dependency (farmer tenant = `farmers.koperasi_id`), role guards | `core/deps.py` | cross-tenant access blocked; no domain query runs unscoped |
| 6 | **Koperasi & farmer onboarding** | koperasi CRUD; farmer signup with KTP photo → **Cloudinary**; admin manual validation; **`notifications` table** (used from phase 11) | `api/koperasi.py`, `api/farmers.py`, `services/storage.py` | farmer signs up, KTP uploads, admin approves → `active` |
| 7 | **Commodities & catalog** | commodity CRUD, PIHPS price, `current_stock_kg` (updated in same txn as stock movements) | `api/commodities.py` | koperasi manages its own catalog (tenant-scoped) |
| 8 | **Ledger & two-pool funds** | `ledger_entries` (+ **`chk_pool_type` CHECK**, `external_idempotency_key` unique) + `koperasi_funds`; **`SELECT … FOR UPDATE` helper** for pool checks; `apbn_grant` credits Loan Pool; reconcile = ledger sum | `models/ledger.py`, `services/ledger.py` | APBN grant credits Loan Pool only; CHECK rejects wrong pool/type; concurrent debits can't overdraft |
| 9 | **Payment provider abstraction** | `PaymentProvider` interface + `MockXenditProvider` (instant paid, fake disbursement, no QRIS cap); `XenditProvider` stub | `payments/` | mock returns deterministic results; selected by `MODE` |
| 10 | **Harvest intake + signed QR** | intake create, **JWT-signed QR**, `estimated_value`, status `pending`; farmer sees live status | `api/intakes.py`, `services/qr.py` | farmer creates intake, gets signed QR, status visible |
| 11 | **Manager confirm + buy-decision** | re-weigh confirm/reject; **pool check via `FOR UPDATE`** + over-pool alert → **write `notification`**; `price_per_kg` system-set from PIHPS; stock movement (in); pay farmer via provider + ledger entry — **all one txn** | `services/intake.py`, `models/stock_movements.py` | confirm pays farmer atomically from Marginal Profit Pool; over-pool intake flags + notifies; reject sets status |
| 12 | **Marketplace orders + checkout** | order/`order_items` (**both carry `koperasi_id`**), Xendit **split payment**, **QRIS ≤10jt → VA fallback**, 1–2% platform fee, **`xendit_webhook_events` idempotency inbox** (`xendit_invoice_id` unique); webhook mock-simulated in dev | `api/orders.py`, `services/orders.py`, `payments/` | checkout records split fee; a replayed webhook does NOT double-post |
| 13 | **Fulfillment + pickup QR** | delivery vs pickup; **signed pickup QR** scan validation (asli/palsu); stock movement (out); `cancelled`/`refund` path | `services/fulfillment.py` | manager scans valid pickup QR → goods released, stock reduced |
| 14 | **Loans + credit scoring** | credit score (SQL aggregation, indexed `credit_scores`); tier/limit; eligibility (**Loan Pool check via `FOR UPDATE`**); admin audit; disburse via provider (idempotent); installments + `loan_status_history` (**both carry `koperasi_id`**); past-due/seize | `api/loans.py`, `services/credit.py`, `services/loans.py` | full lifecycle works; loans only from Loan Pool; no concurrent over-disburse |
| 15 | **Audit, anomaly & reporting** | **append-only `audit_log`** (revoke UPDATE/DELETE from app user + BEFORE UPDATE/DELETE trigger); kasir anomaly/fraud detection; **portfolio reporting scoped by `data_share_grants`** (auth: `JWT.user_id → financing_partners → grant`; fields whitelisted from `scope_json`) | `services/audit.py`, `api/reports.py` | audit rows can't be updated/deleted; partner sees ONLY granted scope |

> **Cross-cutting (applies from the phase each table appears):** money is `DECIMAL`; every pool check locks `koperasi_funds` `FOR UPDATE` in the same txn as the ledger write; every Xendit webhook is idempotent via `xendit_webhook_events` + `external_idempotency_key`. See §8.

> Build the matching frontend slice right after each backend phase where it makes sense — but a working vertical slice always beats half-finished features (graded on low-bug + real implementation).

---

## 8. Conventions for Claude Code
- **Never query a domain table without a `koperasi_id` tenant filter.** Isolation is a graded requirement. A farmer's canonical tenant is `farmers.koperasi_id` (not `users.koperasi_id`).
- **Money = `DECIMAL`, never `FLOAT`.** All amounts/weights use the type conventions in §4. Verify every SQLAlchemy model before the first migration.
- **Pool sufficiency checks lock first:** `SELECT … FOR UPDATE` the `koperasi_funds` row, check, write `ledger_entry`, update balance — one transaction. Never read a pool balance and write in separate statements.
- **Enforce the pool invariant** — harvest only from Marginal Profit Pool; loans only from Loan Pool (APBN). Backed by the `chk_pool_type` CHECK; don't rely on it alone.
- **All money movements write a `ledger_entry`**; `koperasi_funds` is the cached balance, `balance_after` is display-only — never the source of truth for checks.
- **Xendit webhooks are idempotent:** land every event in `xendit_webhook_events` first; ledger writes carry `external_idempotency_key`. A replay must never double-post.
- **Prices are PIHPS-locked**; `price_per_kg` is system-set from `commodities.pihps_price` at confirm — never accepted from a request payload.
- **`audit_log` is append-only** — enforced by DB-user privileges (INSERT/SELECT only) + a BEFORE UPDATE/DELETE trigger, not just convention.
- **Financing-partner report auth** resolves `JWT.user_id → financing_partners.user_id → data_share_grants`; never serve report fields outside the grant's `scope_json`.
- **All payment calls go through `PaymentProvider`** — never call Xendit directly from a route, so `MODE=dev` mocking stays intact.
- Match existing code's style as it grows; keep business logic in `services/`, not routers.
