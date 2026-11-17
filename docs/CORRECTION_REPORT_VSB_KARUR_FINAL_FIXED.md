# Correction report — Exam_Monitor_Ultimate_VSB_KARUR_FINAL_FIXED

Continues `Exam_Monitor_Ultimate_VSB_INTEGRATED`; nothing recreated. Migration `0013` is additive (4 new tables); Phase 1–12 tables, routes and records are untouched.

## Done
| # | Item | Where |
|---|---|---|
| 1–5 | Dedicated hall parser and seating parser (coordinate-based seat↔register mapping, compressed lists/ranges, wrapped lines, non-standard numbers); duplicate / conflicting-hall / missing-student / total / OCR checks | `app/vsb_alloc/` |
| 6–10 | Draft batches linked to `students`; admin correct/approve/preview/publish/withdraw; student `my` + lookup show only approved+published; optional bridge into `allotments` via `check_placement`; nothing auto-published | `routers/vsb_alloc.py`, `doc_models.py`, migration 0013, `pages-vsb-alloc.js` |
| 11–14 | Official page URL preserved and tested; revert-to-earlier-content handling; two live links for one type/date/session flagged; staged drafts after discovery; scheduler flags `VSB_STAGE_DRAFTS_ON_SCHEDULE`, `VSB_PUBLIC_LOOKUP`; how-to in docs | `vsb_sources.py`, `routers/vsb.py`, `scheduler.py`, `config.py`, `.env.example` |
| 15 | Real defects fixed: the new router had to be registered in `main.py`; hall/seat PDFs were being run through the timetable extractor (junk rows, forced "needs review") and offered the generic seating import, which cannot read VSB layouts. Static checker found no other broken page links, API paths or model references | `docproc.py`, `pages-vsb.js`, `scripts/check_references.py` |
| 16 | Tests: parser 30, crawler 6, workflow 12, references 1 | `backend/tests/` |
| 17 | `docs/VSB_ALLOCATION.md`, `VSB_INTEGRATION.md`, `RELEASE_MANIFEST_SHA256.txt` regenerated | |

## What was actually run (in the build sandbox)
Executed and passing: the 30 parser/reconcile tests (pure Python, incl. a reportlab-drawn PDF read back with pdfplumber), the 6 crawler tests (heavy imports stubbed), `compileall` of app/migrations/tests, `scripts/check_references.py`, and a JS parse of every frontend file.

## NOT verified — please run before relying on it
* **Backend runtime**: the sandbox had no FastAPI, SQLAlchemy, pytest, PyMuPDF or network. Migration 0013, `routers/vsb_alloc.py`, `service.py`, scheduler/discovery hooks, the 12 workflow tests and the existing Phase 1–12 suite were **not executed**. Run `test_windows.bat` / `pytest` and `alembic upgrade head` first.
* **Real PDF binaries**: I examined only the *text layer* of the official `14.11.26-FN-HALL.pdf` / `14.11.26-FN-SEAT.pdf` (via a fetch tool). Seat mapping from word boxes is proven only on synthetic PDFs; the PyMuPDF word reader (`pdfwords.py`) never ran. If real boxes differ, expect flags (never silent wrong seats) — send me a real PDF to tune.
* AN-session files, other dates and scanned/OCR PDFs were not examined. `MB III` is kept as part of the printed hall label (e.g. `MB III 02`); its meaning is unconfirmed.
* Hall directory: if a hall exists but is unverified, `check_placement` blocks bridging; halls such as `MB III 02` must be added/verified first.
* Department for a seat-only student is inferred from the register-number programme code learned in the same PDF and flagged.
* UI was syntax-checked only, not exercised in a browser.
* Official PDFs' legal/robots permission for scheduled downloads is the institution's to confirm.
