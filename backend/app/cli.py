"""Command line helpers:  python -m app.cli <command>"""
import argparse, getpass, os, secrets, sys
from datetime import datetime, timezone
from sqlalchemy import select
from . import models, audit
from .config import settings
from .database import SessionLocal
from .security import check_secret_key, hash_password, validate_password_strength


def cmd_gen_secret(_args) -> int:
    print(secrets.token_urlsafe(48))
    return 0


def cmd_init_env(_args) -> int:
    """Create backend/.env from .env.example with a freshly generated SECRET_KEY (never overwrites)."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    target, example = root / ".env", root / ".env.example"
    if target.exists():
        print(".env already exists - left untouched")
        return 0
    text = example.read_text(encoding="utf-8").replace("SECRET_KEY=", "SECRET_KEY=" + secrets.token_urlsafe(48), 1)
    target.write_text(text, encoding="utf-8")
    print("Created", target)
    return 0


def cmd_check_config(_args) -> int:
    problems = check_secret_key(settings.secret_key)
    for p in problems:
        print("PROBLEM:", p)
    if settings.environment == "production" and settings.database_url.startswith("sqlite"):
        problems.append("production should use PostgreSQL")
        print("PROBLEM: production should use PostgreSQL")
    if settings.environment == "production":
        from .config import production_placeholder_problems
        for msg in production_placeholder_problems(settings):
            if msg.endswith("(warning)"):
                print("WARNING:", msg)
            else:
                problems.append(msg)
                print("PROBLEM:", msg)
    print("Configuration OK" if not problems else "Configuration has problems")
    return 1 if problems else 0


def cmd_migrate(_args) -> int:
    from .dbcheck import migrate
    print("Database is at revision", migrate())
    return 0


def cmd_db_audit(_args) -> int:
    from .dbcheck import audit_schema
    r = audit_schema()
    print(f"Revision: {r['revision'] or 'none'}   (application needs {r['head']})")
    for key, label in (("drift", "Schema differs from the models"), ("missing_constraints", "Constraints not present"),
                       ("duplicate_student_links", "Students linked to more than one account"),
                       ("foreign_key_violations", "Foreign-key violations")):
        if r[key]:
            print(f"PROBLEM: {label}: {r[key]}")
    for name, n in r["violations"].items():
        print(f"  {name}: {n} existing row(s) violate it - correct those rows, then re-run the migration step (see docs/MIGRATIONS.md)")
    print("Database schema OK" if r["ok"] else "Database schema needs attention (nothing was changed)")
    return 0 if r["ok"] else 1


def create_account(username: str, password: str, role: str = "admin") -> models.User:
    username = username.strip().lower()
    problems = validate_password_strength(password, username)
    if problems:
        raise ValueError("; ".join(problems))
    db = SessionLocal()
    try:
        if db.scalar(select(models.User).where(models.User.username == username)):
            raise ValueError(f"User '{username}' already exists")
        u = models.User(username=username, password_hash=hash_password(password), role=role)
        db.add(u)
        audit.record(db, "cli", "user.created", username, {"role": role, "via": "cli"})
        db.commit()
        return u
    finally:
        db.close()


def cmd_create_admin(args) -> int:
    password = os.environ.get("EM_ADMIN_PASSWORD")
    if not password:
        password = getpass.getpass("New admin password (min 12 chars, letters + digits): ")
        if password != getpass.getpass("Repeat password: "):
            print("Passwords do not match")
            return 1
    try:
        create_account(args.username, password, getattr(args, "role", "admin"))
    except ValueError as exc:
        print("ERROR:", exc)
        return 1
    print(f"Account '{args.username.strip().lower()}' created with role {getattr(args, 'role', 'admin')}.")
    return 0


def cmd_unlock(args) -> int:
    db = SessionLocal()
    try:
        u = db.scalar(select(models.User).where(models.User.username == args.username.strip().lower()))
        if not u:
            print("No such user")
            return 1
        u.locked_until, u.failed_attempts = None, 0
        audit.record(db, "cli", "user.unlocked", u.username)
        db.commit()
        print("Unlocked", u.username)
        return 0
    finally:
        db.close()


def cmd_reset_password(args) -> int:
    password = os.environ.get("EM_NEW_PASSWORD")
    if not password:
        password = getpass.getpass("New password (min 12 chars, letters + digits): ")
        if password != getpass.getpass("Repeat password: "):
            print("Passwords do not match")
            return 1
    name = args.username.strip().lower()
    problems = validate_password_strength(password, name)
    if problems:
        print("ERROR:", "; ".join(problems))
        return 1
    db = SessionLocal()
    try:
        u = db.scalar(select(models.User).where(models.User.username == name))
        if not u:
            print("No such user")
            return 1
        u.password_hash = hash_password(password)
        u.token_version += 1
        u.must_change_password = False
        u.locked_until, u.failed_attempts = None, 0
        db.execute(models.AuthSession.__table__.update().where(models.AuthSession.user_id == u.id).values(revoked_at=models.utcnow()))
        audit.record(db, "cli", "user.password_reset", u.username, {"via": "cli"})
        db.commit()
        print("Password changed for", u.username)
        return 0
    finally:
        db.close()


def cmd_seed_demo(_args) -> int:
    from .seed import seed_demo
    if settings.environment == "production":
        print("Refusing to load demo data when ENVIRONMENT=production")
        return 1
    db = SessionLocal()
    try:
        print("Demo data created:", seed_demo(db))
    finally:
        db.close()
    return 0



def cmd_backup(_args) -> int:
    from .data_management import create_backup
    import json
    try:
        print(json.dumps(create_backup(), indent=2))
        return 0
    except Exception as exc:
        print("ERROR:", str(exc))
        return 1


def cmd_backup_list(_args) -> int:
    from .data_management import list_backups
    import json
    print(json.dumps(list_backups(), indent=2))
    return 0


def cmd_restore_backup(args) -> int:
    from .data_management import restore_backup
    if not args.confirm_restore:
        print("Refusing restore without --confirm-restore")
        return 2
    try:
        import json
        print(json.dumps(restore_backup(args.filename, confirmed=True), indent=2))
        return 0
    except Exception as exc:
        print("ERROR:", str(exc))
        return 1

def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("gen-secret", help="print a new random SECRET_KEY").set_defaults(fn=cmd_gen_secret)
    sub.add_parser("init-env", help="create .env with a generated SECRET_KEY").set_defaults(fn=cmd_init_env)
    sub.add_parser("check-config", help="validate settings").set_defaults(fn=cmd_check_config)
    sub.add_parser("db-audit", help="read-only schema/data-integrity report").set_defaults(fn=cmd_db_audit)
    sub.add_parser("migrate", help="create/upgrade the database schema").set_defaults(fn=cmd_migrate)
    sub.add_parser("backup", help="create a verified database and uploads backup").set_defaults(fn=cmd_backup)
    sub.add_parser("backup-list", help="list and verify available backups").set_defaults(fn=cmd_backup_list)
    rb = sub.add_parser("restore-backup", help="restore a verified backup while the application is stopped")
    rb.add_argument("filename", help="backup ZIP filename from backend/backups")
    rb.add_argument("--confirm-restore", action="store_true", help="confirm replacement; a safety backup is created first")
    rb.set_defaults(fn=cmd_restore_backup)
    a = sub.add_parser("create-admin", help="create an administrator account")
    a.add_argument("--username", default="admin")
    a.add_argument("--role", default="admin", choices=["admin", "super_admin"],
                   help="admin = Examination administrator, super_admin = Super administrator")
    a.set_defaults(fn=cmd_create_admin)
    u = sub.add_parser("unlock-user", help="clear a login lockout")
    u.add_argument("username")
    u.set_defaults(fn=cmd_unlock)
    r = sub.add_parser("reset-password", help="set a new password for an existing user")
    r.add_argument("username")
    r.set_defaults(fn=cmd_reset_password)
    sub.add_parser("seed-demo", help="load synthetic demo students/exam (no login account)").set_defaults(fn=cmd_seed_demo)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
