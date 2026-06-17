from __future__ import annotations

import os
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


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

ROLES = ("Administrator", "Mentor", "Benutzer")
ADMIN_ROLE = "Administrator"
MENTOR_ROLE = "Mentor"
USER_ROLE = "Benutzer"
