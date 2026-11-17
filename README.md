# Exam Monitor Ultimate — VSB Karur final release (Phases 1–12)

> Version identifiers inside the code are unchanged from the earlier phases: the API reports `0.7.0` (`backend/app/main.py`) and the Android app `versionName 0.8.1`. Database head revision: `0013` (additive VSB tables `0012`, `0013`; always run `python -m app.cli migrate`).

An independent examination-management platform (FastAPI + SQLAlchemy + Alembic, SQLite by default) with a responsive single-page web interface. It is **not** an official institutional portal. Use synthetic or institution-authorised data only.

## What it does
Role-based web application for examinations and subjects, academic years and terms, students, seat allocation (preview → administrator approval → commit, corrections, history), seating plans and reports (CSV/XLSX/PDF/print), official timetable PDF upload with OCR review and confirmed import, seating-allotment PDF import, user accounts and permissions, security dashboard, audit history, announcements, and student/invigilator portals.

| Role | Sees |
|---|---|
| Super administrator / Examination administrator | Everything, including accounts, results publication, security dashboard, audit history, approval and import steps |
| Department staff | Examinations, subjects, students (their department), allocation preview/manual seats, reports, halls (read), document upload/extraction, announcements |
| Invigilator | Read-only hall rosters and seating charts, announcements |
| Student | Own seats, published timetable, own published results, announcements |
| Public (not signed in) | Register-number lookup, published timetable, announcements, sign-in / registration |

**Hiding a menu item is never the security boundary.** Every action calls an API endpoint that enforces the role on the server (see `docs/PHASE4_SECURITY.md`); the UI shows server errors verbatim.

## Install and start
Requirements: Python 3.12+ (tested with 3.12). Optional: Tesseract for OCR of scanned PDFs (`docs/OCR.md`).

**Windows:** run `install.bat` (checks Python, creates `backend/.venv`, installs dependencies, generates a local secret, runs the configuration wizard, migrates and prompts for the first administrator), then `start.bat` and open <http://127.0.0.1:8000>. The launcher checks `/api/ready`; logs are in `backend/logs/`. Use `stop.bat` to stop the managed server. See [Windows installation](docs/WINDOWS_INSTALLATION.md) and [Windows user guide](docs/WINDOWS_USER_GUIDE.md).

**Production Docker:** configure `backend/.env.production` from its example, install a valid TLS certificate in `deploy/certs/`, update the Nginx hostname, run the `check-config` and `migrate` steps (start-up does not migrate), then follow [production deployment](docs/PRODUCTION_DEPLOYMENT.md) and [Docker guide](docs/DOCKER.md). PostgreSQL, uploads and backups use persistent named volumes. No production deployment is claimed by this source package.

**Linux / macOS:**
```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt            # add -r requirements-dev.txt for tests, -r requirements-ocr.txt for OCR
cp .env.example .env                       # then set SECRET_KEY (python -c "import secrets;print(secrets.token_urlsafe(48))")
python -m app.cli migrate                  # the app refuses to start on an unmigrated database
python -m app.cli create-admin --username <name>   # first administrator (prompts for a password)
uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Open <http://127.0.0.1:8000>. API docs: `/docs` (when `ENABLE_DOCS=true`).

## Tests
```bash
cd backend && python -m pytest                      # backend + front-end contract tests (requires requirements-dev.txt; test.bat installs it on demand)
# optional DOM-level UI test (Node 18+ and jsdom, NOT a real browser):
cd tests/e2e_jsdom && npm install && cd ../.. && python tests/e2e_jsdom/run_e2e.py
```
Results and what was *not* verified: `docs/TEST_REPORT.md`. Implementation status per feature: `docs/PHASE_STATUS.md`. Front-end design and routes: `docs/FRONTEND.md`. History of all phases: `PHASE_PROGRESS.md`.

## Other documentation
[installation](docs/INSTALLATION.md) · [Windows installation](docs/WINDOWS_INSTALLATION.md) · [Windows user guide](docs/WINDOWS_USER_GUIDE.md) · [production deployment](docs/PRODUCTION_DEPLOYMENT.md) · [Docker](docs/DOCKER.md) · [deployment troubleshooting](docs/TROUBLESHOOTING_DEPLOYMENT.md) · [configuration](docs/CONFIGURATION.md) · [database](docs/DATABASE.md) · [administrator guide](docs/ADMIN_GUIDE.md) · [student guide](docs/STUDENT_GUIDE.md) · [backup/recovery](docs/BACKUP_RECOVERY.md) · [troubleshooting](docs/TROUBLESHOOTING.md) · [security](docs/SECURITY.md) · [Phase 4 security](docs/PHASE4_SECURITY.md) · [architecture](docs/ARCHITECTURE.md) · [upgrading](docs/UPGRADING.md) · [OCR](docs/OCR.md)

## Upgrading from Phase 4 (historical note)
No database migration was required for Phase 5 (head was `0008` at that time; the current head is `0013`, so always run `python -m app.cli migrate`). Two additive API endpoints were added; the old multi-script UI (`app.js`, `phase2-4.js`, `style.css`) was replaced by `static/js/*` and `static/css/app.css`. Existing records, APIs and migrations are unchanged.

## Remaining limitations (honest list)
* The UI was exercised with jsdom (DOM-level) and static contract tests only. **No real browser testing** (Chrome/Firefox/Safari), **no visual/responsive check on real devices**, and **no automated accessibility audit** (axe/Lighthouse or screen reader) was possible here.
* File-picker upload and the PDF page-image preview were not driven through the UI test (jsdom has no file chooser / image decoding); the API behind them is covered by backend tests.
* The Android app (`android/`, Phase 7) is fully implemented in source but **has never been compiled or run with the Android toolchain** (no SDK/Maven access here); see `android/README.md` for exactly what was verified. Windows `.bat` scripts were not executed on Windows. PostgreSQL, load testing, MFA, SMS and real SMTP delivery are untested/not implemented.
* OCR/parsers are tuned on synthetic PDFs only; real college PDFs need human review (which the workflow enforces).
* Rate limiting is in-process; use a shared limiter for multi-worker deployments. Department scope applies to the endpoints listed in `docs/PHASE4_SECURITY.md`.
* Results can be created/published but not edited or deleted through the API (unchanged backend behaviour); the UI therefore offers publish/unpublish only.


## Phase 6 - Notifications & e-mail
In-app notification centre, preferences, SMTP delivery with retries, reminders and an administrator Communications page. See `docs/PHASE6_NOTIFICATIONS.md`. Set SMTP_* in `backend/.env`; run `python -m app.cli migrate` after upgrading.


## Phase 8.3 database administration

The Phase 8.3 database console and migration/index updates are documented in `docs/PHASE83_DATABASE_ADMIN.md`. Apply migrations from `backend` with `python -m app.cli migrate`. Restore remains an offline CLI maintenance operation. Phase 8.3 tests were intentionally not rerun for this delivery.


## Phase 11 — integrated workflows

The signed-in **Workflow centre** composes live data from the existing examination, eligibility, campus, seat-allocation, results, PDF/OCR and notification modules. It provides a permission-scoped system overview and an examination readiness checklist with links into the existing approval workflows. The Android Retrofit client exposes the same workflow summary/readiness endpoints and the student's own analytics endpoint through its repository container. No database migration is required. See [Phase 11 Integration](docs/PHASE11_INTEGRATION.md).

Phase 11 implementation was packaged without running tests, audits, builds or verification, as requested. Do not treat historical reports as Phase 11 verification.

## Phase 10 — Analytics & intelligence

The administrator/staff dashboard now includes a live examination intelligence panel. Open **Reports & plans** for filters, academic-year/semester comparisons, trend insights, at-risk screening, hall utilization and CSV/Excel/PDF performance exports.

Key API endpoints:
- `GET /api/analytics/dashboard`
- `GET /api/analytics/comparisons`
- `GET /api/analytics/insights`
- `GET /api/analytics/allocation`
- `GET /api/analytics/students/{register_number}`
- `GET /api/analytics/students/at-risk`
- `GET /api/analytics/me` (student's own published results)
- `GET /api/analytics/reports/performance?format=csv|xlsx|pdf|json`

See [Phase 10 Analytics Guide](docs/PHASE10_ANALYTICS.md) for filters, permissions, formulas, screening rules and report instructions. All performance calculations use published result records. Attendance is explicitly unavailable because this project schema does not yet contain attendance records. Unverified or missing hall capacity is not estimated.


## Phase 12 release package

See [release package and operator checklist](docs/RELEASE_PACKAGE.md) for production configuration, Windows deployment, Docker/PostgreSQL setup, Android release signing inputs, and migration instructions. Browse the [documentation index](docs/README.md) for the complete guide catalogue. This archive is a source release: Android APK/AAB artifacts and production secrets are intentionally not included.


## Release corrections

This archive supersedes `Exam_Monitor_Ultimate_FINAL_RELEASE.zip`. Packaging and configuration fixes are listed in [docs/RELEASE_FIXES.md](docs/RELEASE_FIXES.md). The SHA-256 inventory is `RELEASE_MANIFEST_SHA256.txt`; it records file hashes only and is not a build, test or audit report.

## Official VSB integration
The app links to and can fetch PDFs from the college's official Controller of Examinations page (https://vsbec.edu.in/controller-of-examination/):
staff page **VSB official notices**, public home-page card, `/api/vsb/*`, migration 0012. Downloaded PDFs flow into the existing
Timetable PDFs review and Seating PDF import. See `docs/VSB_INTEGRATION.md`.

**VSB hall and seat allocation** (migration 0013, `/api/vsb-allocation/*`, staff page *VSB allocation*, student page *My VSB seat*): hall-allotment and
seating-allotment PDFs are parsed into **draft** batches linked to student records; an administrator corrects, approves, previews and publishes them.
Nothing is published automatically, and students see only approved, published seats. See `docs/VSB_ALLOCATION.md`.

### Quick start for V.S.B. Engineering College, Karur
1. Windows: `install.bat` → `start.bat` → <http://127.0.0.1:8000>; sign in with the administrator you created.
2. Set `COLLEGE_NAME=V.S.B. Engineering College, Karur` in `backend/.env` (stop first with `stop.bat`).
3. Staff → **VSB official notices** → *Check official page now* to list the PDFs; download and *Process* the hall and seating PDFs.
4. Staff → **VSB allocation** → build a batch, resolve flagged issues, approve, preview, publish.
5. Use only institution-authorised data. Scheduled discovery stays off unless you set `VSB_AUTO_DISCOVER_ENABLED=true`.
