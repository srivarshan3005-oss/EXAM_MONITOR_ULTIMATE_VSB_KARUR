# Windows installation guide

Requirements: Windows 10/11, **Python 3.12 or newer from python.org** (the Microsoft Store "python" stub does not count). Optional: Tesseract OCR for scanned PDFs (see OCR.md).

1. Extract the ZIP to a path you control (e.g. `C:\ExamMonitor`).
2. Double-click `install.bat` (or run it in a terminal). It tries the `py -3` launcher, then `python`, and accepts only 3.12+; otherwise it stops with instructions. It then creates `backend\.venv`, installs dependencies, creates `backend\.env` with a generated `SECRET_KEY`, restricts that file's permissions (`scripts\configure_windows.ps1`), runs migrations (head 0013) and asks you to create the administrator.
3. Start with `start.bat` (also `run_windows.bat`). It runs the configuration check, applies migrations, starts uvicorn hidden on `127.0.0.1:8000`, records the PID in `backend\.run.pid` and waits for `/api/ready`.
4. Stop with `stop.bat`.
5. `backup.bat`, `backup_list.bat`, `restore_backup.bat`, `test.bat` as documented in BACKUP_RECOVERY.md and TEST_REPORT.md.

## Process safety (start.bat / stop.bat)
Both scripts use `scripts\managed_server.ps1`. A PID file is honoured only when the PID is purely numeric, the process exists, its image is `python.exe`/`pythonw.exe` **and** its command line contains both `uvicorn` and `app.main:app`. If any test fails (stale file, reused PID, unrelated process) nothing is terminated and the file is treated as stale. When it matches, `taskkill /T /F` ends that process tree only.

## Verification status
Static review only; **the scripts have not been executed on Windows** (no Windows host was available). The same CLI steps (`init-env`, `check-config`, `migrate`, `db-audit`, `create-admin`) were run on Linux. First run on a real Windows machine: `install.bat`, `start.bat`, open `http://127.0.0.1:8000`, `stop.bat`, then confirm no python process remains and that an unrelated `python.exe` is never stopped.
