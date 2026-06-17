from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import config
from app.database import audit, connect, init_db
from app.security import hash_password, normalize_email, now_iso


def reset_admin_password(email: str, display_name: str, password: str) -> tuple[int, bool]:
    email = normalize_email(email)
    display_name = display_name.strip()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValueError("Bitte eine gültige E-Mail-Adresse angeben.")
    if len(display_name) < 2:
        raise ValueError("Bitte einen Anzeigenamen mit mindestens 2 Zeichen angeben.")
    if len(password) < 8:
        raise ValueError("Das Passwort muss mindestens 8 Zeichen haben.")

    init_db()
    with connect() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        password_hash = hash_password(password)
        if existing:
            user_id = int(existing["id"])
            conn.execute(
                """
                UPDATE users
                SET display_name = ?, password_hash = ?, role = ?, is_active = 1
                WHERE id = ?
                """,
                (display_name, password_hash, config.ADMIN_ROLE, user_id),
            )
            created = False
        else:
            cursor = conn.execute(
                """
                INSERT INTO users (email, display_name, password_hash, role, is_active, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
                """,
                (email, display_name, password_hash, config.ADMIN_ROLE, now_iso()),
            )
            user_id = int(cursor.lastrowid)
            created = True

        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM login_attempts WHERE email = ?", (email,))
        audit(
            conn,
            None,
            "create" if created else "reset",
            "admin_password",
            str(user_id),
            {"email": email, "sessions_cleared": True, "login_attempts_cleared": True},
        )
    return user_id, created


def prompt_password() -> str:
    password = getpass.getpass("Neues Passwort: ")
    confirm = getpass.getpass("Passwort wiederholen: ")
    if password != confirm:
        raise ValueError("Die Passwörter stimmen nicht überein.")
    return password


def main() -> int:
    parser = argparse.ArgumentParser(description="Administratorzugang reparieren oder Passwort zurücksetzen.")
    parser.add_argument("--email", default="", help="E-Mail-Adresse des Administrators")
    parser.add_argument("--name", default="", help="Anzeigename des Administrators")
    parser.add_argument("--password", default="", help="Nur für Automatisierung. Interaktive Eingabe ist sicherer.")
    args = parser.parse_args()

    email = args.email.strip() or input("Admin-E-Mail: ").strip()
    name = args.name.strip() or input("Anzeigename: ").strip()
    password = args.password or prompt_password()

    try:
        user_id, created = reset_admin_password(email, name, password)
    except ValueError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    action = "erstellt" if created else "aktualisiert"
    print(f"Administrator {action}: {normalize_email(email)} (ID {user_id})")
    print(f"Datenbank: {config.DB_PATH}")
    print("Sitzungen und Login-Sperren für diesen Benutzer wurden gelöscht.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
