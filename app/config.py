from __future__ import annotations

import os
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
DATA_DIR = Path(os.environ.get("WARTUNG_DATA_DIR", ROOT_DIR / "data")).expanduser()
BACKUP_DIR = Path(os.environ.get("WARTUNG_BACKUP_DIR", ROOT_DIR / "backups")).expanduser()
TEMPLATE_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"

DB_PATH = Path(os.environ.get("WARTUNG_DB_PATH", DATA_DIR / "wartung.db")).expanduser()
LEGACY_DB_PATH = ROOT_DIR / "wartung.db"
TEAM_CODE_FILE = ROOT_DIR / "teamleiter_code.txt"

HOST = os.environ.get("WARTUNG_HOST", os.environ.get("HOST", "0.0.0.0"))
PORT = int(os.environ.get("WARTUNG_PORT", os.environ.get("PORT", "8080")))
SSL_CERT = os.environ.get("WARTUNG_SSL_CERT", "").strip()
SSL_KEY = os.environ.get("WARTUNG_SSL_KEY", "").strip()
TRUST_PROXY = os.environ.get("WARTUNG_TRUST_PROXY", "0").strip().lower() in {"1", "true", "yes", "on"}

SESSION_COOKIE = "wartung_session"
AUTH_CSRF_COOKIE = "wartung_auth_csrf"
SESSION_DAYS = 7
PASSWORD_ITERATIONS = 310_000
STATE_RECENT_LOG_LIMIT = max(100, _env_int("WARTUNG_STATE_RECENT_LOG_LIMIT", 1000))
STATE_RECENT_NOTE_LIMIT = max(100, _env_int("WARTUNG_STATE_RECENT_NOTE_LIMIT", 500))

PUBLIC_URL = os.environ.get("WARTUNG_PUBLIC_URL", "").strip().rstrip("/")
SMTP_HOST = os.environ.get("WARTUNG_SMTP_HOST", "").strip()
SMTP_PORT = _env_int("WARTUNG_SMTP_PORT", 587)
SMTP_USER = os.environ.get("WARTUNG_SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("WARTUNG_SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("WARTUNG_SMTP_FROM", SMTP_USER or "noreply@localhost").strip()
SMTP_STARTTLS = _env_bool("WARTUNG_SMTP_STARTTLS", True)
SMTP_SSL = _env_bool("WARTUNG_SMTP_SSL", False)
PASSWORD_RESET_MINUTES = max(10, _env_int("WARTUNG_PASSWORD_RESET_MINUTES", 30))
PASSWORD_RESET_DEV_OUTBOX = _env_bool("WARTUNG_RESET_DEV_OUTBOX", not TRUST_PROXY)
BOOTSTRAP_ADMIN_EMAIL = os.environ.get("WARTUNG_BOOTSTRAP_ADMIN_EMAIL", "").strip()
BOOTSTRAP_ADMIN_NAME = os.environ.get("WARTUNG_BOOTSTRAP_ADMIN_NAME", "Administrator").strip()
BOOTSTRAP_ADMIN_PASSWORD = os.environ.get("WARTUNG_BOOTSTRAP_ADMIN_PASSWORD", "")

ROLES = ("Administrator", "Mentor", "Benutzer")
ADMIN_ROLE = "Administrator"
MENTOR_ROLE = "Mentor"
USER_ROLE = "Benutzer"
