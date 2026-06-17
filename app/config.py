from __future__ import annotations

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
DATA_DIR = ROOT_DIR / "data"
BACKUP_DIR = ROOT_DIR / "backups"
TEMPLATE_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"

DB_PATH = DATA_DIR / "wartung.db"
LEGACY_DB_PATH = ROOT_DIR / "wartung.db"
TEAM_CODE_FILE = ROOT_DIR / "teamleiter_code.txt"

HOST = os.environ.get("WARTUNG_HOST", "0.0.0.0")
PORT = int(os.environ.get("WARTUNG_PORT", "8080"))
SSL_CERT = os.environ.get("WARTUNG_SSL_CERT", "").strip()
SSL_KEY = os.environ.get("WARTUNG_SSL_KEY", "").strip()

SESSION_COOKIE = "wartung_session"
AUTH_CSRF_COOKIE = "wartung_auth_csrf"
SESSION_DAYS = 7
PASSWORD_ITERATIONS = 310_000

ROLES = ("Administrator", "Mentor", "Benutzer")
ADMIN_ROLE = "Administrator"
MENTOR_ROLE = "Mentor"
USER_ROLE = "Benutzer"

