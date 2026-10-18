# VISTA – VIT Integrated Smart Transit & Accommodation System

**Smart Hostel & Accommodation Management System** – Software Engineering Lab Assessment VI (BCSE301P).

VISTA is a working web application for hostel life at VIT: accommodation, complaints with automatic
escalation, visitor approval, sick-meal and room-cleaning requests, notices and notifications,
emergency SOS, a community marketplace, notes sharing, a private document vault, gate food/parcel
booking, and the project's unique **peer-to-peer inter-hostel delivery** (fixed ₹10 fee with OTP or
QR + photo handover).

> All people, rooms and phone numbers in the demo data are fictional. Payments are **demo records
> only** (no money moves). The SOS feature is **not connected to any real emergency service**.

---

## 1. What is in this repository

| Folder / file | Contents |
|---|---|
| `backend/` | FastAPI application (`app/`), SQLAlchemy models, seed data, API tests (`tests/`) |
| `frontend/` | React 18 + TypeScript + Vite + Tailwind CSS single-page app, Vitest unit tests |
| `e2e/` | Playwright end-to-end tests (functional, security, accessibility, responsive, mobile) |
| `perf/load-test.js` | k6 load-test script (50 / 150 / 300 concurrent users) |
| `database/schema.sql` | PostgreSQL schema generated from the models (the app also creates it itself) |
| `scripts/` | Test pipeline, non-functional runner, result collector, report generator, DB setup, backup/restore |
| `reports/` | Generated PDFs, Excel workbooks, defect log, machine-readable results |
| `test-results/` | Raw outputs of every tool, plus `run1-initial/` (evidence of first-run failures) |
| `docs/screenshots/` | Screenshots of the running application |
| `Dockerfile`, `render.yaml` | Container image and one-click Render deployment blueprint |
| `.env.example` | Every environment variable the code reads (no real secrets) |

### Technology stack and why

| Layer | Choice | Reason |
|---|---|---|
| Frontend | React 18, TypeScript (strict), Vite 5, Tailwind CSS 3, React Router 6 | As requested; typed, fast build, consistent design system |
| Backend | FastAPI (Python 3.11+), Pydantic v2, SQLAlchemy 2 | Server-side validation by schema, automatic OpenAPI docs at `/api/docs`, easy Pytest testing |
| Database | PostgreSQL 14+ (Supabase / Render / Neon all work) | Persistent relational data, row locks and advisory locks for race-free workflows |
| Auth | JWT bearer tokens (HS256) + bcrypt password hashes, token revocation on logout, lockout after 5 failed logins | Stateless, simple to deploy, roles enforced on the backend |
| Tests | Pytest + httpx, Vitest + Testing Library, Playwright + axe-core, k6 | Covers API, unit, browser, accessibility and load testing |
| Reports | ReportLab (PDF), openpyxl (Excel) | Generated from executed results |

**Single-service deployment:** in production the FastAPI server also serves the built React files, so
one web service plus one PostgreSQL database is all you need. (The frontend can still be hosted
separately on Vercel/Netlify – see §8.)

---

## 2. Features and implementation status

| Module (Lab VI requirement) | Status |
|---|---|
| Registration of students (FR01) and of wardens / staff / admins by the admin (FR02, FR03) | ✅ Implemented |
| Secure login, role-based access for Student, Warden, Chief Warden, Staff (maintenance / cleaning / mess / security), Admin (FR04) | ✅ Implemented – enforced in the API, not only in the UI |
| Student profile and roommate preferences (FR05), roommate finder (FR09) | ✅ Implemented |
| Hostels, blocks, rooms, room allocation with capacity/gender rules (FR06–FR08) | ✅ Implemented |
| Complaints: electrical, plumbing, carpentry, washroom, water, other; auto-forwarding to the least-loaded staff member (FR10, FR11) | ✅ Implemented |
| Escalation to the chief warden when unresolved after 24 h (HIGH) / 48 h (MEDIUM) / 72 h (LOW), checked every 5 minutes + manual "Run escalation check" (FR12) | ✅ Implemented |
| Washroom/water complaints always HIGH priority (FR23); complaint history and audit log (NFR12) | ✅ Implemented |
| Visitor registration, warden approval/rejection with reason, student notification (FR13, FR14) | ✅ Implemented |
| Sick-meal (FR15) and room-cleaning (FR16) requests with staff queues | ✅ Implemented |
| Dashboards for every role with live statistics (FR17, FR19) | ✅ Implemented |
| Lost & found (FR18), mess feedback (FR21), document vault (FR24), notes sharing (FR25), marketplace (FR26) | ✅ Implemented (file uploads: PDF/PNG/JPEG/TXT ≤ 2 MB, type checked by content) |
| Hostel map of blocks, mess halls, gates and service points (FR20) | ✅ Implemented (schematic SVG map, not GPS) |
| Emergency SOS with confirmation, warden + security alert, acknowledge / resolve, timestamps (FR22) | ✅ Implemented – in-app alerts only (no SMS/phone call) |
| Food delivery booking to the hostel gate (FR27) and parcel reservation with courier name + gate OTP (FR31) | ✅ Implemented |
| P2P inter-hostel delivery, fixed ₹10 fee (FR28) | ✅ Implemented – **demo payment record** (receipt `RCPT-DEMO-…`), no payment gateway |
| Handover by OTP: 6 digits, bcrypt-hashed, 10-minute expiry, 3 attempts then locked, max 3 OTPs per delivery (FR30) | ✅ Implemented |
| Handover by QR code + parcel photo + receiver name/reg. no./room/block (FR29) | ✅ Implemented – camera scanning uses the browser's BarcodeDetector where available, otherwise the QR value is typed/pasted |
| In-app messaging (FR32) and notifications (FR33), notice publishing (FR34) | ✅ Implemented (notifications refresh every 30 s; no push/SMS/e-mail channel) |
| Reports with CSV export (FR35) | ✅ Implemented |
| Encryption of personal data at rest (NFR06) | ❌ Not implemented – see defect DEF-04 |
| Real payments, SMS/e-mail, campus transport | ⛔ Not in this version (outside the demo scope) |

---

## 3. Prerequisites

* **Python 3.11 or newer** (tested with 3.13)
* **Node.js 20 or newer** (tested with 22) and npm
* **PostgreSQL 14 or newer** (tested with 16) – local install, Docker, or a free Supabase/Neon database
* Optional: **k6** (load tests), **Docker** (container build)

---

## 4. Run the application locally

### Quickest way (no PostgreSQL needed)

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000
```

Open <http://localhost:8000>. When `DATABASE_URL` is not set, VISTA uses a local SQLite file (`backend/vista.db`)
and creates the tables and demo users automatically on first start. Use PostgreSQL (below) for the test suites and deployment.


### 4.1 Create the databases (once)

```bash
# needs a PostgreSQL superuser, e.g. the default 'postgres'
PGUSER=postgres PGPASSWORD=yourpassword ./scripts/setup_databases.sh
```

This creates the role `vista` (password `vista_dev_pw`, local development only) and four databases:
`vista` (app), `vista_test` (pytest), `vista_e2e` (Playwright) and `vista_perf` (load tests).
On Windows, run the same SQL in pgAdmin or psql:

```sql
CREATE ROLE vista LOGIN PASSWORD 'vista_dev_pw' CREATEDB;
CREATE DATABASE vista OWNER vista;
CREATE DATABASE vista_test OWNER vista;
CREATE DATABASE vista_e2e OWNER vista;
CREATE DATABASE vista_perf OWNER vista;
```

### 4.2 Configure environment variables

```bash
cp .env.example .env
# edit .env: set DATABASE_URL=postgresql+psycopg://vista:vista_dev_pw@localhost:5432/vista
#            and a long random JWT_SECRET
```

### 4.3 Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.seed                 # creates tables + fictional demo data (use --reset to start over)
uvicorn app.main:app --reload --port 8000
```

API docs: <http://localhost:8000/api/docs> · Health check: <http://localhost:8000/api/health>

### 4.4 Frontend

**Option A – development server with hot reload** (calls the API through the Vite proxy):

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

**Option B – production build served by FastAPI** (one URL for everything):

```bash
cd frontend && npm install && npm run build
# restart uvicorn – it now serves the app at http://localhost:8000
```

### 4.5 Demo accounts (fictional)

| Role | Email | Password |
|---|---|---|
| Student (Ladies Hostel East, G-101) | `priya.sharma@vista.demo` | `Student@123` |
| Student (Men's Hostel North, Q-101) | `rahul.verma@vista.demo` | `Student@123` |
| Student (Men's Hostel South, K-102) | `arjun.nair@vista.demo` | `Student@123` |
| Other students | `ananya.iyer`, `kavya.reddy`, `sneha.das`, `vikram.singh`, `meera.pillai` `@vista.demo`; `student2001…2048@vista.demo` | `Student@123` |
| Warden (Ladies Hostel East) | `warden.lh@vista.demo` | `Warden@123` |
| Warden (Men's Hostel North) | `warden.mh@vista.demo` | `Warden@123` |
| Chief Warden | `chief.warden@vista.demo` | `Warden@123` |
| Maintenance staff | `maint1@vista.demo`, `maint2@vista.demo` | `Staff@123` |
| Cleaning / Mess / Security staff | `cleaning1@`, `mess1@`, `security1@vista.demo` | `Staff@123` |
| Administrator | `admin@vista.demo` | `Admin@123` |

The login page has one-click buttons for these accounts. **Change or remove them before any public use.**

**Try the P2P delivery:** log in as Rahul → Deliveries → *Send an item* to `24BCE1001` (Priya) → log in as
Arjun in another browser/private window → *Available to carry* → Accept → Mark picked up → log in as Priya
→ open the delivery to see the OTP and QR → back as Arjun, enter the OTP.

---

## 5. Running the tests

| Suite | Command | Database |
|---|---|---|
| Backend API, security and integrity tests (61) | `cd backend && pytest` | `TEST_DATABASE_URL` (default `vista_test`, reset + seeded automatically) |
| Frontend unit tests (14) | `cd frontend && npx vitest run` | none |
| Lint / types / build | `cd frontend && npm run lint && npm run typecheck && npm run build`; `cd backend && ruff check app tests` | none |
| End-to-end browser tests (23 + 2 cross-browser) | `cd e2e && npm install && npx playwright install chromium && npx playwright test` | `vista_e2e` (reset + seeded, server started automatically on port 8001) |
| Firefox + WebKit too | `cd e2e && npx playwright install firefox webkit && npm run test:all-browsers` | `vista_e2e` |
| Load tests | `k6 run -e BASE_URL=http://localhost:8002 -e VUS=300 -e LABEL=peak-300vus perf/load-test.js` (start a server on 8002 against `vista_perf` first) | `vista_perf` |
| Non-functional runner | `python3 scripts/nft_runner.py` (all) or `python3 scripts/nft_runner.py NFT-04 NFT-24` | `vista_perf` |
| **Everything + reports** | `./scripts/run_all_tests.sh` (add `SKIP_LOAD=1` to skip k6, `ALL_BROWSERS=1` for Firefox/WebKit) | all of the above |

The E2E suite needs the frontend to be built (`npm run build`) because the test server serves `frontend/dist`.

### Generating the reports

```bash
python3 scripts/collect_results.py     # merges all tool outputs → test-results/test-results.json + .xml
python3 scripts/generate_reports.py    # → reports/*.pdf, *.xlsx, defect-log.*
```

`generate_reports.py` needs `reportlab` and `openpyxl` (in `backend/requirements.txt`). Fonts are bundled in
`scripts/fonts/` so the ₹ sign renders correctly. Excel summary sheets use live formulas (COUNTIF), so if you
change a Status cell the totals update.

### What was actually executed (latest run in this package)

The numbers below are copied from `reports/test-results.json`, produced by `./scripts/run_all_tests.sh`:

| | Total | Executed | Passed | Failed | Blocked | Not Run | Pass % (passed ÷ executed) |
|---|---|---|---|---|---|---|---|
| Functional test cases (FT) | 43 | 43 | 43 | 0 | 0 | 0 | 100.0% |
| Non-functional test cases (NFT) | 34 | 30 | 28 | 2 | 2 | 2 | 93.3% |

Automated tests behind them: **61/61 pytest**, **14/14 Vitest**, **23/25 Playwright** (2 blocked: Firefox and WebKit could not be downloaded), **4 k6 load runs**, **8 non-functional runner checks** (1 failed).

| Load (k6, 60 s) | Requests | Failed | Average | p95 |
|---|---|---|---|---|
| 50 concurrent users | 9,966 | 0.00 % | 54 ms | 92 ms |
| 150 concurrent users | 12,919 | 0.00 % | 509 ms | 781 ms |
| 300 concurrent users | 12,713 | 0.00 % | 1363 ms | 1921 ms |

Failing cases (genuine, still open): **NFT-06** Performance degradation as load increases (DEF-05); **NFT-34** Personal data encrypted in transit and at rest (DEF-04).
Defects found and fixed during testing: DEF-01 duplicate submissions race, DEF-02 mobile layout overflow, DEF-03 database connection exhaustion at 300 users, DEF-08 filter drop-down layout (found by manual review).

**Executed vs. included:** every Pass/Fail in the reports comes from a test that really ran against the
running application. *Blocked* = could not run in the build environment (Firefox/WebKit downloads were blocked
by its network policy). *Not Run* = included in the plan but needs things that were not available (a usability
study with real students; 30 days of production uptime monitoring). The `test-results/run1-initial/` folder keeps
the first-run outputs, including the genuine failures that led to fixes (see the defect log).

---

## 6. Generated deliverables

| File | Description |
|---|---|
| `reports/Functional_Testing_Report.pdf` | 43 functional test cases in the format of the reference sheet + summary + key takeaways |
| `reports/Non_Functional_Testing_Report.pdf` | 34 non-functional test cases, load-test measurements, related defects |
| `reports/Combined_Testing_Report.pdf` | Both reports + overall summary, execution history, requirement traceability, defect log, limitations |
| `reports/Functional_Test_Cases.xlsx`, `reports/Non_Functional_Test_Cases.xlsx` | Editable sheets (Status drop-downs, colour rules, formula-based Summary sheet, Load Tests sheet) |
| `reports/defect-log.xlsx`, `reports/defect-log.csv` | Defect ID, severity, module, reproduction steps, expected, actual, status, resolution |
| `reports/test-results.json`, `reports/test-results.xml` | Machine-readable results (per automated test and per test case; JUnit XML) |
| `test-results/playwright-html/index.html` | Interactive Playwright report |

---

## 7. Environment variables

See `.env.example` for the full list with comments. The important ones:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL URL (`postgresql+psycopg://…`; `postgres://…` from Render/Heroku is accepted) |
| `JWT_SECRET` | Token signing secret – **required** when `ENVIRONMENT=production` |
| `ENVIRONMENT` | `development` or `production` (production adds HSTS and refuses to start without `JWT_SECRET`) |
| `CORS_ORIGINS` | Allowed frontend origins (comma-separated) when the frontend is hosted on a different domain |
| `UPLOAD_DIR`, `MAX_UPLOAD_BYTES` | Where uploads are stored and the size limit |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` | Connections per server worker. Keep `workers × (pool + overflow)` below PostgreSQL `max_connections` |
| `VITE_API_URL` | Frontend build-time API base URL (only when frontend and API are on different domains) |

Uploaded files are stored on local disk. On hosts with an ephemeral filesystem (Render free tier) they are lost
on redeploy – attach a persistent disk or use object storage for real use.

---

## 8. Deployment

> The application was **not deployed** from the build environment (no hosting account was available).
> The steps below are what you need to do; nothing here claims a live URL exists.

### Option A – Render (recommended, uses `render.yaml`)

1. Push this folder to a GitHub repository.
2. In Render: **New → Blueprint**, select the repository. Render creates the `vista-db` PostgreSQL database and the
   `vista` web service from the `Dockerfile`, generates `JWT_SECRET`, and wires `DATABASE_URL`.
3. After the first deploy, set `CORS_ORIGINS` to your service URL (e.g. `https://vista-xxxx.onrender.com`) and redeploy.
4. Open `https://<your-service>.onrender.com/api/health` → `{"status":"ok","database":true}`.
5. The container runs `python -m app.seed` on start: it creates the tables and loads the fictional demo data only
   when the database is empty. Change the demo passwords (or delete the demo accounts) before sharing the link.

### Option B – Supabase database + Render/Railway web service (manual)

1. Create a Supabase project → *Project Settings → Database → Connection string (URI)*; use the **session pooler**
   URI and prefix it with `postgresql+psycopg://`.
2. Create a web service from the `Dockerfile` with environment variables `DATABASE_URL`, `JWT_SECRET`
   (32+ random characters), `ENVIRONMENT=production`, `CORS_ORIGINS`, `DB_POOL_SIZE=5`, `DB_MAX_OVERFLOW=2`.
3. Health-check path: `/api/health`.

### Option C – Frontend on Vercel/Netlify, API elsewhere

1. Deploy the API as in A or B and note its URL.
2. Frontend project root `frontend/`, build command `npm run build`, output `dist`, environment variable
   `VITE_API_URL=https://your-api.example.com`. Add a SPA rewrite of all paths to `/index.html`.
3. Set the API's `CORS_ORIGINS` to the Vercel/Netlify URL.

### Option D – Docker anywhere

```bash
docker build -t vista .
docker run -p 8000:8000 -e DATABASE_URL=... -e JWT_SECRET=... -e CORS_ORIGINS=http://localhost:8000 vista
```

### Backups (NFR09)

`scripts/backup_db.sh` (pg_dump, keeps 14 days) and `scripts/restore_db.sh`. Schedule the backup daily, e.g.
`30 2 * * * DATABASE_URL=... /path/to/scripts/backup_db.sh`. Managed databases (Render, Supabase) also offer
automatic daily backups.

---

## 9. Security notes

* Passwords: bcrypt. OTPs: bcrypt-hashed; the plain OTP is shown only to the receiver while it is active and is
  cleared after use, lock or expiry.
* Every protected endpoint requires a valid token and checks the role on the server (tested for all routes).
* Brute-force protection: 5 failed logins → 15-minute lockout (HTTP 429).
* Input validated with Pydantic; database access through the SQLAlchemy ORM (parameterised); React escapes output;
  Content-Security-Policy `script-src 'self'`, `X-Frame-Options: DENY`, `nosniff`, HSTS in production.
* Uploads: type checked by file signature, size-limited, stored under random names, served only to permitted users.
* Known gap: personal data is not encrypted at rest (DEF-04). Use a managed database with storage encryption and
  `sslmode=require`, and add column-level encryption before handling real student data.

---

## 10. Known limitations

* Load tests ran on a 2-vCPU container shared by the API, PostgreSQL and the load generator; response time rose
  from ~0.1 s (50 users) to ~2 s (300 users) at p95 (DEF-05). Re-test on the real hosting plan.
* Cross-browser testing covered Chromium and mobile-viewport emulation only (DEF-06).
* No real payment gateway, SMS, e-mail or push notifications; SOS is in-app only.
* Notifications refresh by polling (every 30 s; SOS board every 10 s) rather than WebSockets.

---

## 11. Troubleshooting

| Problem | Fix |
|---|---|
| `connection refused` on start | PostgreSQL is not running or `DATABASE_URL` is wrong |
| `remaining connection slots are reserved` | Too many server workers/connections – lower `DB_POOL_SIZE` or workers |
| Login returns 429 | Account locked after 5 wrong passwords – wait 15 minutes (or set `LOGIN_LOCKOUT_MINUTES`) |
| Blank page at `localhost:8000` | Build the frontend (`npm run build`) or use `npm run dev` on port 5173 |
| Playwright: "Executable doesn't exist" | Run `npx playwright install chromium` (and `firefox webkit` for all browsers) in `e2e/` |
| Pytest cannot connect | Create `vista_test` or set `TEST_DATABASE_URL` |
