# Windows operation

- First-time setup: double-click `install.bat` and follow the secure administrator password prompts.
- Start: `start.bat`; website `http://127.0.0.1:8000`, API docs `http://127.0.0.1:8000/docs`.
- Stop: `stop.bat`.
- Automated tests (only when intentionally requested): `test.bat`.
- Backup: `backup.bat`; verify/list with `backup_list.bat`; restore offline with `restore_backup.bat`. Archives are written to `backend/backups`. See `docs/PHASE82_DATA_MANAGEMENT.md`..

The installer creates `backend/.venv`, creates a random local `SECRET_KEY` in `backend/.env` if absent, installs backend dependencies and applies Alembic migrations. It does not overwrite an existing `.env` or database. Administrator creation is interactive so no default password is embedded in source.

The local server binds to loopback only. To use the Android emulator, configure `http://10.0.2.2:8000/`. A physical Android device needs a reachable LAN address and a deliberate firewall/network configuration. Do not expose the development server directly to the public internet.
