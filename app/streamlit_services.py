from __future__ import annotations

import csv
import io
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

from . import config
from .database import (
    audit,
    backup_inventory,
    backup_path,
    connect,
    create_backup,
    prune_backups,
    restore_backup,
    row,
    rows,
    set_setting,
    setting,
)
from .maintenance import due_items as build_due_items
from .maintenance import teams_payload as build_teams_payload
from .reports import csv_cell, month_filter, pdf_bytes
from .security import (
    allowed_role,
    can_log_level,
    env_or_file_team_code,
    hash_password,
    hash_secret,
    hash_token,
    is_admin,
    is_mentor_or_admin,
    new_token,
    normalize_email,
    now_iso,
    safe_compare,
    verify_password,
    verify_secret,
)
from .validators import optional_int, task_applies_to_device, valid_date, valid_id


STREAMLIT_IP = "streamlit"


def public_user(user: dict) -> dict:
    return {key: user[key] for key in ("id", "email", "display_name", "role")}


def team_code_is_configured() -> bool:
    with connect() as conn:
        return bool(setting(conn, "team_code_hash") or env_or_file_team_code())


def verify_team_code(conn, code: str) -> bool:
    stored_hash = setting(conn, "team_code_hash")
    if stored_hash:
        return verify_secret(code, stored_hash)
    configured = env_or_file_team_code()
    return bool(configured and safe_compare(code, configured))


def login_limited(conn, email: str) -> bool:
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).replace(microsecond=0).isoformat()
    conn.execute("DELETE FROM login_attempts WHERE created_at < ?", (cutoff,))
    count = conn.execute(
        """
        SELECT COUNT(*)
        FROM login_attempts
        WHERE email = ? AND ip_address = ? AND success = 0 AND created_at >= ?
        """,
        (email, STREAMLIT_IP, cutoff),
    ).fetchone()[0]
    return count >= 5


def authenticate(email: str, password: str) -> tuple[dict | None, str]:
    email = normalize_email(email)
    with connect() as conn:
        if login_limited(conn, email):
            return None, "Zu viele Fehlversuche. Bitte 15 Minuten warten."
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        ok = bool(user and user["is_active"] and verify_password(password, user["password_hash"]))
        conn.execute(
            "INSERT INTO login_attempts (email, ip_address, success, created_at) VALUES (?, ?, ?, ?)",
            (email, STREAMLIT_IP, 1 if ok else 0, now_iso()),
        )
        if not ok:
            audit(conn, None, "login_failed", "user", email, ip=STREAMLIT_IP)
            return None, "E-Mail oder Passwort ist falsch."
        conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now_iso(), user["id"]))
        audit(conn, {"id": user["id"], "display_name": user["display_name"], "email": user["email"]}, "login", "user", str(user["id"]), ip=STREAMLIT_IP)
        return public_user(dict(user)), ""


def register(display_name: str, email: str, password: str, team_code: str) -> tuple[dict | None, str]:
    display_name = display_name.strip()[:120]
    email = normalize_email(email)
    if len(display_name) < 2 or "@" not in email or email.startswith("@") or email.endswith("@"):
        return None, "Bitte Name und gültige E-Mail eingeben."
    if len(password) < 8:
        return None, "Das Passwort muss mindestens 8 Zeichen haben."

    with connect() as conn:
        if not verify_team_code(conn, team_code.strip()):
            return None, "Der Teamleiter-Code ist falsch oder noch nicht gesetzt."
        try:
            cursor = conn.execute(
                """
                INSERT INTO users (email, display_name, password_hash, role, is_active, created_at)
                VALUES (?, ?, ?, 'Benutzer', 1, ?)
                """,
                (email, display_name, hash_password(password), now_iso()),
            )
        except Exception:
            return None, "Diese E-Mail ist bereits registriert."
        user_id = int(cursor.lastrowid)
        audit(conn, {"id": user_id, "display_name": display_name, "email": email}, "register", "user", str(user_id), ip=STREAMLIT_IP)
        return {"id": user_id, "email": email, "display_name": display_name, "role": config.USER_ROLE}, ""


def password_reset_limited(conn, user_id: int) -> bool:
    now = now_iso()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(microsecond=0).isoformat()
    conn.execute("DELETE FROM password_reset_tokens WHERE expires_at <= ? OR used_at IS NOT NULL", (now,))
    user_count = conn.execute(
        "SELECT COUNT(*) FROM password_reset_tokens WHERE user_id = ? AND created_at >= ?",
        (user_id, cutoff),
    ).fetchone()[0]
    return user_count >= 3


def send_password_reset_email(email: str, display_name: str, link: str, user_id: int) -> str:
    subject = "Passwort zurücksetzen - Wartung FDM Space"
    text = (
        f"Hallo {display_name},\n\n"
        "für deinen Zugang zur Wartungs-App wurde ein Passwort-Reset angefordert.\n"
        f"Öffne diesen Link innerhalb von {config.PASSWORD_RESET_MINUTES} Minuten:\n\n"
        f"{link}\n\n"
        "Wenn du das nicht warst, kannst du diese E-Mail ignorieren.\n"
    )
    if config.SMTP_HOST:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = config.SMTP_FROM
        message["To"] = email
        message.set_content(text)
        if config.SMTP_SSL:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=context, timeout=10) as server:
                if config.SMTP_USER:
                    server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.send_message(message)
        else:
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as server:
                if config.SMTP_STARTTLS:
                    server.starttls(context=ssl.create_default_context())
                if config.SMTP_USER:
                    server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                server.send_message(message)
        return "smtp"

    if config.PASSWORD_RESET_DEV_OUTBOX:
        outbox = config.DATA_DIR / "password_reset_outbox"
        outbox.mkdir(parents=True, exist_ok=True)
        stamp = now_iso().replace(":", "").replace("-", "").split("+", 1)[0]
        path = outbox / f"password-reset-{stamp}-{user_id}.txt"
        path.write_text(f"{subject}\n\n{text}", encoding="utf-8")
        return "dev_outbox"

    return "not_configured"


def request_password_reset(email: str) -> str:
    email = normalize_email(email)
    generic = "Wenn diese E-Mail registriert ist, wurde ein Link zum Zurücksetzen versendet."
    if "@" not in email:
        return generic

    with connect() as conn:
        user = conn.execute("SELECT id, email, display_name FROM users WHERE email = ? AND is_active = 1", (email,)).fetchone()
        if not user or password_reset_limited(conn, int(user["id"])):
            return generic
        token = new_token()
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=config.PASSWORD_RESET_MINUTES)).replace(microsecond=0).isoformat()
        conn.execute(
            """
            INSERT INTO password_reset_tokens (user_id, token_hash, request_ip, user_agent, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user["id"], hash_token(token), STREAMLIT_IP, "streamlit", now_iso(), expires_at),
        )
        base_url = config.PUBLIC_URL.rstrip("/")
        link = f"{base_url}/?reset_token={token}" if base_url else f"?reset_token={token}"
        try:
            delivery = send_password_reset_email(user["email"], user["display_name"], link, int(user["id"]))
        except (OSError, smtplib.SMTPException, ValueError) as exc:
            delivery = "failed"
            print(f"Passwort-Reset-Mail konnte nicht versendet werden: {exc}")
        audit(conn, None, "request", "password_reset", str(user["id"]), {"delivery": delivery}, STREAMLIT_IP)

    if delivery == "dev_outbox":
        return "Lokaler Entwicklungsmodus: Der Reset-Link wurde in data/password_reset_outbox/ gespeichert."
    if delivery == "not_configured":
        return "Mailversand ist noch nicht konfiguriert. Bitte SMTP-Secrets setzen oder einen Admin bitten, das Passwort zu ändern."
    if delivery == "failed":
        return "Reset-Link konnte nicht versendet werden. Bitte Admin kontaktieren."
    return generic


def reset_password(token: str, password: str, confirm: str) -> str:
    token = str(token or "").strip()
    if password != confirm:
        return "Die Passwörter stimmen nicht überein."
    if len(password) < 8:
        return "Das Passwort muss mindestens 8 Zeichen haben."
    with connect() as conn:
        reset = row(
            conn,
            """
            SELECT r.id AS reset_id, u.id AS user_id, u.email, u.display_name
            FROM password_reset_tokens r
            JOIN users u ON u.id = r.user_id
            WHERE r.token_hash = ?
              AND r.used_at IS NULL
              AND r.expires_at > ?
              AND u.is_active = 1
            """,
            (hash_token(token), now_iso()),
        )
        if not reset:
            return "Der Link ist ungültig oder abgelaufen. Bitte fordere einen neuen Link an."
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), reset["user_id"]))
        conn.execute("UPDATE password_reset_tokens SET used_at = ? WHERE id = ?", (now_iso(), reset["reset_id"]))
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (reset["user_id"],))
        conn.execute("DELETE FROM login_attempts WHERE email = ?", (reset["email"],))
        audit(conn, {"id": reset["user_id"], "display_name": reset["display_name"], "email": reset["email"]}, "reset", "password", str(reset["user_id"]), ip=STREAMLIT_IP)
    return ""


def load_state() -> dict:
    with connect() as conn:
        return {
            "devices": rows(conn, "SELECT * FROM devices WHERE active = 1 ORDER BY sort_order, name"),
            "tasks": rows(conn, "SELECT * FROM tasks WHERE active = 1 ORDER BY sort_order, title"),
            "logs": rows(
                conn,
                """
                WITH latest AS (
                    SELECT current.id
                    FROM logs current
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM logs newer
                        WHERE newer.device_id = current.device_id
                          AND newer.task_id = current.task_id
                          AND (newer.done_on > current.done_on OR (newer.done_on = current.done_on AND newer.id > current.id))
                    )
                ),
                recent AS (
                    SELECT id FROM logs ORDER BY id DESC LIMIT ?
                )
                SELECT *
                FROM logs
                WHERE id IN (SELECT id FROM latest UNION SELECT id FROM recent)
                ORDER BY id DESC
                """,
                (config.STATE_RECENT_LOG_LIMIT,),
            ),
            "notes": rows(
                conn,
                """
                WITH latest AS (
                    SELECT current.id
                    FROM notes current
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM notes newer
                        WHERE newer.device_id = current.device_id
                          AND (newer.note_date > current.note_date OR (newer.note_date = current.note_date AND newer.id > current.id))
                    )
                ),
                recent AS (
                    SELECT id FROM notes ORDER BY id DESC LIMIT ?
                )
                SELECT *
                FROM notes
                WHERE id IN (SELECT id FROM latest UNION SELECT id FROM recent)
                ORDER BY id DESC
                """,
                (config.STATE_RECENT_NOTE_LIMIT,),
            ),
            "xlTools": rows(conn, "SELECT * FROM xl_tools ORDER BY device_id, tool_number"),
            "due": build_due_items(conn),
        }


def load_admin_state() -> dict:
    with connect() as conn:
        return {
            "users": rows(conn, "SELECT id, email, display_name, role, is_active, created_at, last_login_at FROM users ORDER BY display_name"),
            "devices": rows(conn, "SELECT * FROM devices ORDER BY sort_order, name"),
            "tasks": rows(conn, "SELECT * FROM tasks ORDER BY sort_order, title"),
            "audit": rows(conn, "SELECT * FROM audit_log ORDER BY id DESC LIMIT 80"),
            "backups": backup_inventory(conn),
            "settings": {
                "team_code_configured": bool(setting(conn, "team_code_hash") or env_or_file_team_code()),
                "teams_webhook_url": setting(conn, "teams_webhook_url"),
            },
        }


def active_device(conn, device_id: str) -> dict:
    device = row(conn, "SELECT * FROM devices WHERE id = ? AND active = 1", (device_id,))
    if not device:
        raise ValueError("Gerät nicht gefunden oder deaktiviert.")
    return device


def active_task(conn, task_id: str) -> dict:
    task = row(conn, "SELECT * FROM tasks WHERE id = ? AND active = 1", (task_id,))
    if not task:
        raise ValueError("Wartungspunkt nicht gefunden.")
    return task


def create_log(user: dict, device_id: str, task_id: str, done_on: str, print_hours, note: str) -> None:
    done_on = valid_date(str(done_on), "Datum")
    print_hours = optional_int(print_hours, "Druckstunden")
    note = str(note or "").strip()[:1000]
    with connect() as conn:
        device = active_device(conn, device_id)
        task = active_task(conn, task_id)
        if not task_applies_to_device(task, device):
            raise ValueError("Dieser Wartungspunkt gehört nicht zu diesem Gerät.")
        if not can_log_level(user, task["level"]):
            raise ValueError("Für diesen Wartungspunkt ist Mentor- oder Administratorstatus erforderlich.")
        conn.execute(
            "INSERT INTO logs (device_id, task_id, done_on, print_hours, user_name, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (device_id, task_id, done_on, print_hours, user.get("display_name") or user["email"], note, now_iso()),
        )
        if print_hours is not None:
            conn.execute("UPDATE devices SET current_print_hours = ?, updated_at = ? WHERE id = ?", (print_hours, now_iso(), device_id))
        audit(conn, user, "create", "log", task_id, {"device_id": device_id, "done_on": done_on}, STREAMLIT_IP)


def create_note(user: dict, device_id: str, note_date: str, text: str) -> None:
    note_date = valid_date(str(note_date), "Datum")
    text = str(text or "").strip()[:1000]
    if not text:
        raise ValueError("Bitte Vermerk ausfüllen.")
    with connect() as conn:
        active_device(conn, device_id)
        conn.execute(
            "INSERT INTO notes (device_id, note_date, user_name, text, created_at) VALUES (?, ?, ?, ?, ?)",
            (device_id, note_date, user.get("display_name") or user["email"], text, now_iso()),
        )
        audit(conn, user, "create", "note", device_id, {"note_date": note_date}, STREAMLIT_IP)


def delete_entry(user: dict, table: str, item_id: int) -> None:
    if table not in {"logs", "notes"}:
        raise ValueError("Ungültiger Eintragstyp.")
    if not is_mentor_or_admin(user):
        raise ValueError("Mentor- oder Administratorstatus erforderlich.")
    with connect() as conn:
        existing = row(conn, f"SELECT id FROM {table} WHERE id = ?", (int(item_id),))
        if not existing:
            raise ValueError("Eintrag nicht gefunden.")
        conn.execute(f"DELETE FROM {table} WHERE id = ?", (int(item_id),))
        audit(conn, user, "delete", table, str(item_id), ip=STREAMLIT_IP)


def update_hours(user: dict, device_id: str, hours) -> None:
    if not is_mentor_or_admin(user):
        raise ValueError("Mentor- oder Administratorstatus erforderlich.")
    parsed = optional_int(hours, "Druckstunden")
    if parsed is None:
        raise ValueError("Bitte Druckstunden angeben.")
    with connect() as conn:
        active_device(conn, device_id)
        conn.execute("UPDATE devices SET current_print_hours = ?, updated_at = ? WHERE id = ?", (parsed, now_iso(), device_id))
        audit(conn, user, "update", "device_hours", device_id, {"current_print_hours": parsed}, STREAMLIT_IP)


def update_xl_tool(user: dict, device_id: str, tool_number: int, nozzle_type: str, material: str, last_nozzle_change: str, issue_note: str) -> None:
    if not is_mentor_or_admin(user):
        raise ValueError("Mentor- oder Administratorstatus erforderlich.")
    number = int(tool_number)
    if number < 1 or number > 5:
        raise ValueError("Tool muss zwischen 1 und 5 liegen.")
    last_nozzle_change = str(last_nozzle_change or "").strip()[:20]
    if last_nozzle_change:
        last_nozzle_change = valid_date(last_nozzle_change, "Letzter Wechsel")
    with connect() as conn:
        device = active_device(conn, device_id)
        if device["kind"] != "xl5":
            raise ValueError("Toolheads können nur für XL 5-Tool-Geräte gepflegt werden.")
        payload = {
            "tool_number": number,
            "nozzle_type": str(nozzle_type or "").strip()[:120],
            "material": str(material or "").strip()[:120],
            "last_nozzle_change": last_nozzle_change,
            "issue_note": str(issue_note or "").strip()[:500],
        }
        conn.execute(
            """
            INSERT INTO xl_tools (device_id, tool_number, nozzle_type, material, last_nozzle_change, issue_note, updated_by, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id, tool_number) DO UPDATE SET
                nozzle_type=excluded.nozzle_type,
                material=excluded.material,
                last_nozzle_change=excluded.last_nozzle_change,
                issue_note=excluded.issue_note,
                updated_by=excluded.updated_by,
                updated_at=excluded.updated_at
            """,
            (
                device_id,
                number,
                payload["nozzle_type"],
                payload["material"],
                payload["last_nozzle_change"],
                payload["issue_note"],
                user.get("display_name") or user["email"],
                now_iso(),
            ),
        )
        audit(conn, user, "update", "xl_tool", f"{device_id}:{number}", payload, STREAMLIT_IP)


def update_profile(user: dict, display_name: str, password: str = "") -> dict:
    display_name = str(display_name or "").strip()[:120]
    if len(display_name) < 2:
        raise ValueError("Bitte gib einen gültigen Namen ein.")
    if password and len(password) < 8:
        raise ValueError("Das neue Passwort muss mindestens 8 Zeichen haben.")
    with connect() as conn:
        conn.execute("UPDATE users SET display_name = ? WHERE id = ?", (display_name, user["id"]))
        if password:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), user["id"]))
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
        audit(conn, user, "update", "profile", str(user["id"]), {"password_changed": bool(password)}, STREAMLIT_IP)
    updated = dict(user)
    updated["display_name"] = display_name
    return updated


def set_team_code(user: dict, code: str) -> None:
    if not is_admin(user):
        raise ValueError("Administratorrechte erforderlich.")
    code = str(code or "").strip()
    if len(code) < 6:
        raise ValueError("Der Teamleiter-Code muss mindestens 6 Zeichen haben.")
    with connect() as conn:
        set_setting(conn, "team_code_hash", hash_secret(code))
        audit(conn, user, "update", "setting", "team_code_hash", {"changed": True}, STREAMLIT_IP)


def save_device(user: dict, device_id: str, kind: str, name: str, mentors: str, active: bool = True) -> None:
    if not is_admin(user):
        raise ValueError("Administratorrechte erforderlich.")
    device_id = valid_id(str(device_id or ""), "Geräte-ID")
    name = str(name or "").strip()[:120]
    kind = str(kind or "").strip()
    if not name or kind not in {"mini", "mk3_5", "xl5"}:
        raise ValueError("Bitte ID, Name und gültigen Typ angeben.")
    type_label = {"mini": "MINI+", "mk3_5": "MK3.5", "xl5": "XL 5-Tool"}[kind]
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO devices (id, kind, name, mentors, type_label, source_page, sort_order, active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 100, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                kind=excluded.kind,
                name=excluded.name,
                mentors=excluded.mentors,
                type_label=excluded.type_label,
                source_page=excluded.source_page,
                active=excluded.active,
                updated_at=excluded.updated_at
            """,
            (device_id, kind, name, str(mentors or "").strip(), type_label, type_label, 1 if active else 0, now_iso(), now_iso()),
        )
        if kind == "xl5":
            for number in range(1, 6):
                conn.execute("INSERT OR IGNORE INTO xl_tools (device_id, tool_number, updated_at) VALUES (?, ?, ?)", (device_id, number, now_iso()))
        audit(conn, user, "upsert", "device", device_id, {"kind": kind, "name": name, "active": active}, STREAMLIT_IP)


def save_task(user: dict, task_id: str, applies_to: str, title: str, details: str, level: str, interval_text: str, cadence_days, cadence_hours, active: bool = True) -> None:
    if not is_admin(user):
        raise ValueError("Administratorrechte erforderlich.")
    task_id = valid_id(str(task_id or ""), "Wartungspunkt-ID")
    title = str(title or "").strip()[:160]
    applies_to = str(applies_to or "all").strip()
    level = str(level or "").strip()
    if not title or level not in {"B", "E", "M"} or applies_to not in {"all", "mini", "mk3_5", "xl5"}:
        raise ValueError("Bitte ID, Titel, Gerätetyp und Level angeben.")
    payload = {
        "applies_to": applies_to,
        "title": title,
        "details": str(details or "").strip()[:1200],
        "level": level,
        "interval_text": str(interval_text or "").strip()[:160],
        "cadence_days": optional_int(cadence_days, "Tage"),
        "cadence_hours": optional_int(cadence_hours, "Stunden"),
        "active": bool(active),
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO tasks (id, applies_to, title, details, level, interval_text, cadence_days, cadence_hours, sort_order, active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 100, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                applies_to=excluded.applies_to,
                title=excluded.title,
                details=excluded.details,
                level=excluded.level,
                interval_text=excluded.interval_text,
                cadence_days=excluded.cadence_days,
                cadence_hours=excluded.cadence_hours,
                active=excluded.active,
                updated_at=excluded.updated_at
            """,
            (
                task_id,
                payload["applies_to"],
                payload["title"],
                payload["details"],
                payload["level"],
                payload["interval_text"],
                payload["cadence_days"],
                payload["cadence_hours"],
                1 if active else 0,
                now_iso(),
                now_iso(),
            ),
        )
        audit(conn, user, "upsert", "task", task_id, payload, STREAMLIT_IP)


def update_user(admin_user: dict, user_id: int, role: str | None = None, is_active: bool | None = None, password: str = "") -> None:
    if not is_admin(admin_user):
        raise ValueError("Administratorrechte erforderlich.")
    with connect() as conn:
        target = row(conn, "SELECT id, role, is_active FROM users WHERE id = ?", (int(user_id),))
        if not target:
            raise ValueError("Benutzer nicht gefunden.")
        new_role = role if role is not None else target["role"]
        new_active = int(is_active) if is_active is not None else int(target["is_active"])
        if not allowed_role(new_role):
            raise ValueError("Ungültige Rolle.")
        if int(user_id) == int(admin_user["id"]) and (new_role != config.ADMIN_ROLE or not new_active):
            raise ValueError("Du kannst deinen eigenen Administratorzugang nicht entziehen.")
        if target["role"] == config.ADMIN_ROLE and (new_role != config.ADMIN_ROLE or not new_active):
            other_admins = conn.execute(
                "SELECT COUNT(*) FROM users WHERE id <> ? AND role = ? AND is_active = 1",
                (int(user_id), config.ADMIN_ROLE),
            ).fetchone()[0]
            if other_admins < 1:
                raise ValueError("Mindestens ein aktiver Administrator muss erhalten bleiben.")
        conn.execute("UPDATE users SET role = ?, is_active = ? WHERE id = ?", (new_role, new_active, int(user_id)))
        details = {"role": new_role, "is_active": bool(new_active)}
        if password:
            if len(password) < 8:
                raise ValueError("Das neue Passwort muss mindestens 8 Zeichen haben.")
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), int(user_id)))
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (int(user_id),))
            details["password_changed"] = True
        audit(conn, admin_user, "update", "user", str(user_id), details, STREAMLIT_IP)


def set_teams_webhook(user: dict, webhook_url: str) -> None:
    if not is_admin(user):
        raise ValueError("Administratorrechte erforderlich.")
    webhook_url = str(webhook_url or "").strip()[:500]
    with connect() as conn:
        set_setting(conn, "teams_webhook_url", webhook_url)
        audit(conn, user, "update", "setting", "teams_webhook_url", {"configured": bool(webhook_url)}, STREAMLIT_IP)


def create_manual_backup(user: dict, reason: str = "manual") -> str:
    if not is_admin(user):
        raise ValueError("Administratorrechte erforderlich.")
    path = create_backup(str(reason or "manual"), user.get("display_name") or user["email"])
    with connect() as conn:
        audit(conn, user, "create", "backup", path.name, ip=STREAMLIT_IP)
    return path.name


def restore_backup_file(user: dict, file_name: str) -> str:
    if not is_admin(user):
        raise ValueError("Administratorrechte erforderlich.")
    safety = restore_backup(file_name, user.get("display_name") or user["email"])
    with connect() as conn:
        audit(conn, user, "restore", "backup", file_name, {"safety_backup": safety.name}, STREAMLIT_IP)
    return safety.name


def prune_backup_files(user: dict, keep: int) -> list[str]:
    if not is_admin(user):
        raise ValueError("Administratorrechte erforderlich.")
    removed = prune_backups(keep)
    with connect() as conn:
        audit(conn, user, "prune", "backup", "backups", {"keep": keep, "removed": removed}, STREAMLIT_IP)
    return removed


def backup_bytes(file_name: str) -> bytes:
    return backup_path(file_name).read_bytes()


def export_csv_bytes(month: str = "") -> bytes:
    month = month_filter(month)
    month_clause_logs = "WHERE substr(l.done_on, 1, 7) = ?" if month else ""
    month_clause_notes = "WHERE substr(n.note_date, 1, 7) = ?" if month else ""
    params = (month, month) if month else ()
    with connect() as conn:
        data = rows(
            conn,
            f"""
            SELECT 'wartung' AS typ, d.name AS gerät, l.done_on AS datum, t.title AS eintrag,
                   l.print_hours AS druckstunden, l.user_name AS benutzer, l.note AS vermerk, l.created_at AS erstellt
            FROM logs l JOIN devices d ON d.id = l.device_id JOIN tasks t ON t.id = l.task_id
            {month_clause_logs}
            UNION ALL
            SELECT 'vermerk', d.name, n.note_date, 'Allgemeiner Vermerk', NULL, n.user_name, n.text, n.created_at
            FROM notes n JOIN devices d ON d.id = n.device_id
            {month_clause_notes}
            ORDER BY gerät, erstellt
            """,
            params,
        )
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["typ", "gerät", "datum", "eintrag", "druckstunden", "benutzer", "vermerk", "erstellt"], delimiter=";")
    writer.writeheader()
    writer.writerows([{key: csv_cell(value) for key, value in item.items()} for item in data])
    return output.getvalue().encode("utf-8-sig")


def export_pdf_bytes(month: str = "") -> bytes:
    month = month_filter(month)
    with connect() as conn:
        due = build_due_items(conn)
        if month:
            entries = rows(
                conn,
                """
                SELECT d.name AS gerät, l.done_on AS datum, t.title AS titel, l.user_name AS benutzer, l.note AS note
                FROM logs l JOIN devices d ON d.id = l.device_id JOIN tasks t ON t.id = l.task_id
                WHERE substr(l.done_on, 1, 7) = ?
                ORDER BY d.name, l.done_on
                """,
                (month,),
            )
        else:
            entries = rows(
                conn,
                """
                SELECT d.name AS gerät, l.done_on AS datum, t.title AS titel, l.user_name AS benutzer, l.note AS note
                FROM logs l JOIN devices d ON d.id = l.device_id JOIN tasks t ON t.id = l.task_id
                ORDER BY d.name, l.done_on DESC
                LIMIT 120
                """,
            )
    title = f"Wartung FDM Space Bericht {month}" if month else "Wartung FDM Space Bericht"
    lines = [title, f"Erstellt: {now_iso()}", "", "Fälligkeiten:"]
    if due:
        for item in due[:30]:
            lines.append(f"- {item['status']}: {item['device']} - {item['task']} ({item['detail']})")
    else:
        lines.append("- Keine offenen Fälligkeiten")
    lines.extend(["", "Wartungseinträge:"])
    if entries:
        for item in entries[:120]:
            note = f" - {item['note']}" if item["note"] else ""
            lines.append(f"- {item['datum']} | {item['gerät']} | {item['titel']} | {item['benutzer']}{note}")
    else:
        lines.append("- Keine Einträge im gewählten Zeitraum")
    return pdf_bytes(lines)


def teams_notification_payload() -> dict:
    with connect() as conn:
        return build_teams_payload(build_due_items(conn))


def data_path_label() -> str:
    return str(Path(config.DB_PATH))
