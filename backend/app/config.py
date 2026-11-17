"""Application settings (read from environment variables or backend/.env)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    college_name: str = "Your College Name"
    environment: str = "development"  # development | production | test
    # No default on purpose: the app refuses to start without a strong key.
    secret_key: str = ""
    database_url: str = "sqlite:///./exam_monitor.db"
    # Phase 8.1: connection tuning (all optional; the defaults are safe for a single-college deployment)
    db_pool_size: int = 5                 # PostgreSQL only
    db_max_overflow: int = 10             # PostgreSQL only
    db_pool_timeout_seconds: int = 30     # PostgreSQL only: wait for a free connection
    db_pool_recycle_seconds: int = 1800   # PostgreSQL only: recycle idle connections
    db_statement_timeout_ms: int = 0      # PostgreSQL only: 0 = no limit
    sqlite_busy_timeout_ms: int = 15000   # SQLite: how long a writer waits for the write lock
    migration_snapshot: bool = True       # SQLite file: copy the database next to itself before upgrading it
    backup_schedule_enabled: bool = False  # scheduled verified backups run in the application scheduler
    backup_interval_hours: int = 24
    backup_retention_count: int = 14       # keep newest N verified backup archives; 0 disables pruning
    sqlite_wal: bool = True               # SQLite file databases: WAL journal (readers never block the writer)
    access_token_minutes: int = 60
    pbkdf2_rounds: int = 310_000

    # Demo data (synthetic students/exams only; never creates a login account).
    seed_demo: bool = False

    # HTTP
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    enable_docs: bool = True
    trust_proxy: bool = False  # only true behind a reverse proxy you control

    # Privacy switches for the public search
    public_show_names: bool = False
    public_results_enabled: bool = False

    # Phase 3: official document storage (never inside the static/public directory)
    document_storage_dir: str = ""          # blank = backend/uploads
    max_upload_mb: int = 25
    ocr_default_language: str = "eng"

    # Login protection
    login_max_failures: int = 5
    login_lockout_minutes: int = 15
    login_ip_max_attempts: int = 20  # per 15 minutes per client IP

    # Public lookup protection (per client IP)
    public_lookup_per_minute: int = 60
    public_lookup_miss_limit: int = 30  # unknown register numbers per 15 min

    # Phase 4: sessions, tokens, mail
    session_idle_minutes: int = 30            # a session unused for this long is rejected
    max_sessions_per_user: int = 5            # oldest sessions are revoked beyond this
    reset_token_minutes: int = 30
    activation_token_hours: int = 48
    forgot_password_per_hour: int = 5         # per client IP
    register_per_hour: int = 10               # per client IP
    allow_self_registration: bool = True      # students only; needs activation
    password_max_age_days: int = 0            # 0 = never force a change
    public_base_url: str = "http://localhost:8000"
    # Outgoing mail (optional). Without SMTP_HOST, development writes messages to backend/outbox/,
    # production only logs that delivery is not configured (reset links are never shown in API responses).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "no-reply@exam-monitor.local"
    smtp_starttls: bool = True                # legacy switch; SMTP_SECURITY wins when set
    # Phase 6: mail transport and notification engine
    smtp_security: str = ""                   # starttls | ssl | none  (blank = starttls unless SMTP_STARTTLS=false)
    smtp_timeout_seconds: int = 15
    smtp_from_name: str = "Exam Monitor"
    mail_max_attempts: int = 3                # delivery attempts for queued notification e-mail
    mail_retry_backoff_seconds: int = 120     # doubles after every failed attempt
    app_timezone: str = "Asia/Kolkata"        # exam dates/times are local to this IANA zone (reminders use it)
    scheduler_enabled: bool = True            # background worker: reminders, scheduled announcements, e-mail queue
    scheduler_interval_seconds: int = 60
    reminders_enabled: bool = True
    reminder_exam_hours: str = "24"           # comma list, e.g. "72,24,2" = reminders that long before the exam
    test_email_per_hour: int = 5

    # Official V.S.B. Engineering College source integration (see docs/VSB_INTEGRATION.md)
    vsb_coe_page_url: str = "https://vsbec.edu.in/controller-of-examination/"   # confirmed official page; must stay on the allowed hosts
    vsb_auto_discover_enabled: bool = False      # scheduled discovery + download (never auto-processes); manual runs always work
    vsb_discover_interval_hours: int = 6
    vsb_http_timeout_seconds: int = 20
    vsb_request_delay_seconds: float = 1.0       # pause between requests to the college server
    vsb_max_downloads_per_run: int = 40
    vsb_stage_drafts_on_schedule: bool = False   # scheduled runs may also parse new hall/seat PDFs into DRAFT batches (never publishes)
    vsb_public_lookup: bool = True               # include PUBLISHED, approved VSB seats in the public register-number lookup
    vsb_max_retries: int = 2                     # network errors / HTTP 5xx only

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def reminder_hours(self) -> list[int]:
        out = []
        for part in self.reminder_exam_hours.split(","):
            part = part.strip()
            if part.isdigit() and 0 < int(part) <= 24 * 30:
                out.append(int(part))
        return sorted(set(out), reverse=True)

    @property
    def smtp_security_mode(self) -> str:
        m = (self.smtp_security or "").strip().lower()
        if m in ("starttls", "ssl", "none"):
            return m
        return "starttls" if self.smtp_starttls else "none"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]



_PLACEHOLDER_MARKERS = ("example.edu", "example.com", "replace_with", "set_a_long", "set_postgres", "set_your_domain", "your college")


def production_placeholder_problems(s: "Settings") -> list[str]:
    """Placeholder values copied from the example files must never reach a production deployment (preflight only)."""
    out = []
    checks = {"PUBLIC_BASE_URL": s.public_base_url, "CORS_ORIGINS": s.cors_origins, "DATABASE_URL": s.database_url}
    for name, value in checks.items():
        if any(m in (value or "").lower() for m in _PLACEHOLDER_MARKERS):
            out.append(f"{name} still contains a placeholder value from the example file")
    if not s.smtp_host:
        out.append("SMTP_HOST is not set: activation and password-reset e-mail will not be delivered (warning)")
    return out


settings = Settings()
