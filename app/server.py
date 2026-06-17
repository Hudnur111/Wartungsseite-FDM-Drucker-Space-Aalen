from __future__ import annotations

import csv
import html
import io
import json
import mimetypes
import ssl
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from . import config
from .database import audit, connect, create_backup, ensure_daily_backup, init_db, row, rows, set_setting, setting
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
    session_expiry_iso,
    verify_password,
    verify_secret,
)


def render_template(name: str, context: dict[str, str]) -> str:
    text = (config.TEMPLATE_DIR / name).read_text(encoding="utf-8")
    for key, value in context.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def html_message(message: str, kind: str) -> str:
    if not message:
        return ""
    return f'<div class="auth-message {kind}">{html.escape(message)}</div>'


def team_code_is_configured(conn) -> bool:
    return bool(setting(conn, "team_code_hash") or env_or_file_team_code())


def verify_team_code(conn, code: str) -> bool:
    stored_hash = setting(conn, "team_code_hash")
    if stored_hash:
        return verify_secret(code, stored_hash)
    configured = env_or_file_team_code()
    return bool(configured and safe_compare(code, configured))


class WartungHandler(BaseHTTPRequestHandler):
    server_version = "WartungFDM/2.0"

    def log_message(self, fmt: str, *args) -> None:
        print("%s - - [%s] %s" % (self.address_string(), self.log_date_time_string(), fmt % args))

    def client_ip(self) -> str:
        forwarded = self.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
        return forwarded or self.client_address[0]

    def send_bytes(self, body: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK, headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, body: str, content_type: str = "text/plain; charset=utf-8", status: HTTPStatus = HTTPStatus.OK, headers: dict[str, str] | None = None) -> None:
        self.send_bytes(body.encode("utf-8"), content_type, status, headers)

    def send_json(self, payload: dict | list, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_text(json.dumps(payload, ensure_ascii=False), "application/json; charset=utf-8", status)

    def redirect(self, location: str, cookie: str | None = None) -> None:
        headers = {"Location": location}
        if cookie:
            headers["Set-Cookie"] = cookie
        self.send_bytes(b"", "text/plain; charset=utf-8", HTTPStatus.SEE_OTHER, headers)

    def read_body(self) -> bytes:
        size = int(self.headers.get("Content-Length", "0"))
        if size < 1 or size > 200_000:
            raise ValueError("Ungueltige Anfragegroesse.")
        return self.rfile.read(size)

    def read_json(self) -> dict:
        return json.loads(self.read_body().decode("utf-8"))

    def read_form(self) -> dict[str, str]:
        parsed = parse_qs(self.read_body().decode("utf-8"), keep_blank_values=True)
        return {key: values[0] for key, values in parsed.items()}

    def cookie_value(self, name: str) -> str:
        cookie = SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        morsel = cookie.get(name)
        return morsel.value if morsel else ""

    def session_cookie(self, token: str, max_age: int | None = None) -> str:
        age = max_age if max_age is not None else config.SESSION_DAYS * 24 * 60 * 60
        return f"{config.SESSION_COOKIE}={token}; Path=/; Max-Age={age}; HttpOnly; SameSite=Lax"

    def auth_csrf_cookie(self, token: str) -> str:
        return f"{config.AUTH_CSRF_COOKIE}={token}; Path=/; Max-Age=1800; HttpOnly; SameSite=Lax"

    def current_user(self) -> dict | None:
        token = self.cookie_value(config.SESSION_COOKIE)
        if not token:
            return None
        token_hash = hash_token(token)
        with connect() as conn:
            item = conn.execute(
                """
                SELECT u.id, u.email, u.display_name, u.role, u.is_active, s.csrf_token, s.expires_at
                FROM sessions s JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = ? AND s.expires_at > ?
                """,
                (token_hash, now_iso()),
            ).fetchone()
            if not item or not item["is_active"]:
                return None
            conn.execute("UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?", (now_iso(), token_hash))
            return {
                "id": item["id"],
                "email": item["email"],
                "display_name": item["display_name"],
                "role": item["role"],
                "csrf_token": item["csrf_token"],
            }

    def require_user(self, api: bool = False) -> dict | None:
        user = self.current_user()
        if user:
            return user
        if api:
            self.send_json({"error": "Nicht angemeldet."}, HTTPStatus.UNAUTHORIZED)
        else:
            self.redirect("/login")
        return None

    def require_admin(self) -> dict | None:
        user = self.require_user(api=True)
        if not is_admin(user):
            self.send_json({"error": "Administratorrechte erforderlich."}, HTTPStatus.FORBIDDEN)
            return None
        return user

    def verify_session_csrf(self, user: dict) -> bool:
        token = self.headers.get("X-CSRF-Token", "")
        if token and safe_compare(token, user.get("csrf_token", "")):
            return True
        self.send_json({"error": "CSRF-Token ungueltig."}, HTTPStatus.FORBIDDEN)
        return False

    def verify_auth_csrf(self, form: dict[str, str]) -> bool:
        cookie_token = self.cookie_value(config.AUTH_CSRF_COOKIE)
        form_token = form.get("csrf_token", "")
        return bool(cookie_token and form_token and safe_compare(cookie_token, form_token))

    def create_session(self, user_id: int) -> str:
        token = new_token()
        csrf_token = new_token()
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (token_hash, csrf_token, user_id, expires_at, created_at, last_seen_at, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (hash_token(token), csrf_token, user_id, session_expiry_iso(), now_iso(), now_iso(), self.headers.get("User-Agent", "")[:300]),
            )
            conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now_iso(), user_id))
        return token

    def auth_page(self, mode: str, message: str = "", error: str = "") -> None:
        csrf = new_token()
        with connect() as conn:
            hint = "Registrierung ist freigeschaltet." if team_code_is_configured(conn) else "Registrierung ist gesperrt, bis ein Teamleiter-Code gesetzt wurde."
        body = render_template(
            "auth.html",
            {
                "TITLE": "Registrieren - Wartung FDM Space" if mode == "register" else "Anmelden - Wartung FDM Space",
                "LOGIN_ACTIVE": "active" if mode == "login" else "",
                "REGISTER_ACTIVE": "active" if mode == "register" else "",
                "MESSAGE_BLOCK": html_message(message, "success") + html_message(error, "error"),
                "CSRF_TOKEN": html.escape(csrf),
                "REGISTER_HINT": html.escape(hint),
            },
        )
        self.send_text(body, "text/html; charset=utf-8", headers={"Set-Cookie": self.auth_csrf_cookie(csrf)})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path in {"/login", "/register"}:
            if self.current_user():
                self.redirect("/")
                return
            self.auth_page("register" if path == "/register" else "login", query.get("message", [""])[0], query.get("error", [""])[0])
            return
        if path == "/":
            if not self.require_user():
                return
            self.send_text(render_template("app.html", {}), "text/html; charset=utf-8")
            return
        if path.startswith("/static/"):
            self.serve_static(path.removeprefix("/static/"))
            return
        if path == "/api/state":
            user = self.require_user(api=True)
            if not user:
                return
            self.send_json(self.state_payload(user))
            return
        if path == "/api/admin/state":
            user = self.require_admin()
            if not user:
                return
            self.send_json(self.admin_payload())
            return
        if path == "/api/export.csv":
            if not self.require_user(api=True):
                return
            self.export_csv()
            return
        self.send_text("Nicht gefunden.", status=HTTPStatus.NOT_FOUND)

    def serve_static(self, relative: str) -> None:
        safe = Path(unquote(relative))
        if safe.is_absolute() or ".." in safe.parts:
            self.send_text("Nicht gefunden.", status=HTTPStatus.NOT_FOUND)
            return
        path = config.STATIC_DIR / safe
        if not path.exists() or not path.is_file():
            self.send_text("Nicht gefunden.", status=HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_bytes(path.read_bytes(), content_type)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/auth/login":
                self.login()
                return
            if path == "/auth/register":
                self.register()
                return
            if path == "/auth/logout":
                user = self.require_user(api=True)
                if user and self.verify_session_csrf(user):
                    self.logout()
                return
            user = self.require_user(api=True)
            if not user or not self.verify_session_csrf(user):
                return
            if path == "/api/logs":
                self.create_log(user)
                return
            if path == "/api/notes":
                self.create_note(user)
                return
            if path.startswith("/api/devices/") and path.endswith("/hours"):
                self.update_hours(user, path)
                return
            if path.startswith("/api/devices/") and path.endswith("/xl-tools"):
                self.update_xl_tool(user, path)
                return
            if path == "/api/admin/team-code":
                self.set_team_code(user)
                return
            if path == "/api/admin/devices":
                self.save_device(user)
                return
            if path == "/api/admin/tasks":
                self.save_task(user)
                return
            if path.startswith("/api/admin/users/"):
                self.update_user(user, path)
                return
            if path == "/api/admin/backups":
                self.manual_backup(user)
                return
            if path == "/api/admin/settings":
                self.save_settings(user)
                return
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self.send_text("Nicht gefunden.", status=HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path.strip("/").split("/")
        user = self.require_user(api=True)
        if not user or not self.verify_session_csrf(user):
            return
        if len(path) == 3 and path[0] == "api" and path[1] in {"logs", "notes"}:
            table = path[1]
            item_id = int(path[2])
            with connect() as conn:
                conn.execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
                audit(conn, user, "delete", table, str(item_id), ip=self.client_ip())
            self.send_json({"ok": True})
            return
        self.send_text("Nicht gefunden.", status=HTTPStatus.NOT_FOUND)

    def state_payload(self, user: dict) -> dict:
        with connect() as conn:
            public_user = {key: user[key] for key in ("id", "email", "display_name", "role")}
            return {
                "user": public_user,
                "csrfToken": user["csrf_token"],
                "devices": rows(conn, "SELECT * FROM devices WHERE active = 1 ORDER BY sort_order, name"),
                "tasks": rows(conn, "SELECT * FROM tasks WHERE active = 1 ORDER BY sort_order, title"),
                "logs": rows(conn, "SELECT * FROM logs ORDER BY id DESC"),
                "notes": rows(conn, "SELECT * FROM notes ORDER BY id DESC"),
                "xlTools": rows(conn, "SELECT * FROM xl_tools ORDER BY device_id, tool_number"),
            }

    def admin_payload(self) -> dict:
        with connect() as conn:
            return {
                "users": rows(conn, "SELECT id, email, display_name, role, is_active, created_at, last_login_at FROM users ORDER BY display_name"),
                "devices": rows(conn, "SELECT * FROM devices ORDER BY sort_order, name"),
                "tasks": rows(conn, "SELECT * FROM tasks ORDER BY sort_order, title"),
                "audit": rows(conn, "SELECT * FROM audit_log ORDER BY id DESC LIMIT 80"),
                "backups": rows(conn, "SELECT * FROM backup_log ORDER BY id DESC LIMIT 20"),
                "settings": {
                    "team_code_configured": bool(setting(conn, "team_code_hash") or env_or_file_team_code()),
                    "teams_webhook_url": setting(conn, "teams_webhook_url"),
                },
            }

    def login_limited(self, conn, email: str) -> bool:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).replace(microsecond=0).isoformat()
        conn.execute("DELETE FROM login_attempts WHERE created_at < ?", (cutoff,))
        count = conn.execute(
            "SELECT COUNT(*) FROM login_attempts WHERE email = ? AND ip_address = ? AND success = 0 AND created_at >= ?",
            (email, self.client_ip(), cutoff),
        ).fetchone()[0]
        return count >= 5

    def login(self) -> None:
        form = self.read_form()
        if not self.verify_auth_csrf(form):
            self.auth_page("login", error="Sicherheits-Token ungueltig. Bitte erneut versuchen.")
            return
        email = normalize_email(form.get("email", ""))
        password = form.get("password", "")
        with connect() as conn:
            if self.login_limited(conn, email):
                self.auth_page("login", error="Zu viele Fehlversuche. Bitte 15 Minuten warten.")
                return
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            ok = bool(user and user["is_active"] and verify_password(password, user["password_hash"]))
            conn.execute(
                "INSERT INTO login_attempts (email, ip_address, success, created_at) VALUES (?, ?, ?, ?)",
                (email, self.client_ip(), 1 if ok else 0, now_iso()),
            )
            if not ok:
                audit(conn, None, "login_failed", "user", email, ip=self.client_ip())
                self.auth_page("login", error="E-Mail oder Passwort ist falsch.")
                return
        token = self.create_session(user["id"])
        with connect() as conn:
            audit(conn, {"id": user["id"], "display_name": user["display_name"], "email": user["email"]}, "login", "user", str(user["id"]), ip=self.client_ip())
        self.redirect("/", self.session_cookie(token))

    def register(self) -> None:
        form = self.read_form()
        if not self.verify_auth_csrf(form):
            self.auth_page("register", error="Sicherheits-Token ungueltig. Bitte erneut versuchen.")
            return
        display_name = form.get("display_name", "").strip()
        email = normalize_email(form.get("email", ""))
        password = form.get("password", "")
        code = form.get("team_code", "").strip()
        if len(display_name) < 2 or "@" not in email or len(password) < 8:
            self.auth_page("register", error="Bitte Name, gueltige E-Mail und Passwort ab 8 Zeichen eingeben.")
            return
        with connect() as conn:
            if not verify_team_code(conn, code):
                self.auth_page("register", error="Der Teamleiter-Code ist falsch oder noch nicht gesetzt.")
                return
            try:
                cursor = conn.execute(
                    "INSERT INTO users (email, display_name, password_hash, role, is_active, created_at) VALUES (?, ?, ?, 'Benutzer', 1, ?)",
                    (email, display_name, hash_password(password), now_iso()),
                )
            except Exception:
                self.auth_page("register", error="Diese E-Mail ist bereits registriert.")
                return
            user_id = cursor.lastrowid
            audit(conn, {"id": user_id, "display_name": display_name, "email": email}, "register", "user", str(user_id), ip=self.client_ip())
        token = self.create_session(user_id)
        self.redirect("/", self.session_cookie(token))

    def logout(self) -> None:
        token = self.cookie_value(config.SESSION_COOKIE)
        if token:
            with connect() as conn:
                conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))
        self.send_text(
            json.dumps({"ok": True}, ensure_ascii=False),
            "application/json; charset=utf-8",
            headers={"Set-Cookie": self.session_cookie("", max_age=0)},
        )

    def create_log(self, user: dict) -> None:
        payload = self.read_json()
        device_id = str(payload.get("device_id", "")).strip()
        task_id = str(payload.get("task_id", "")).strip()
        done_on = str(payload.get("done_on", "")).strip()
        note = str(payload.get("note", "")).strip()[:1000]
        print_hours = self.optional_int(payload.get("print_hours"), "Druckstunden")
        if not device_id or not task_id or not done_on:
            raise ValueError("Bitte Geraet, Wartungspunkt und Datum ausfuellen.")
        with connect() as conn:
            task = row(conn, "SELECT * FROM tasks WHERE id = ? AND active = 1", (task_id,))
            if not task:
                raise ValueError("Wartungspunkt nicht gefunden.")
            if not can_log_level(user, task["level"]):
                self.send_json({"error": "Fuer diesen Wartungspunkt ist Mentor- oder Administratorstatus erforderlich."}, HTTPStatus.FORBIDDEN)
                return
            conn.execute(
                "INSERT INTO logs (device_id, task_id, done_on, print_hours, user_name, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (device_id, task_id, done_on, print_hours, user.get("display_name") or user["email"], note, now_iso()),
            )
            if print_hours is not None:
                conn.execute("UPDATE devices SET current_print_hours = ?, updated_at = ? WHERE id = ?", (print_hours, now_iso(), device_id))
            audit(conn, user, "create", "log", task_id, {"device_id": device_id, "done_on": done_on}, self.client_ip())
        self.send_json({"ok": True}, HTTPStatus.CREATED)

    def create_note(self, user: dict) -> None:
        payload = self.read_json()
        device_id = str(payload.get("device_id", "")).strip()
        note_date = str(payload.get("note_date", "")).strip()
        text = str(payload.get("text", "")).strip()[:1000]
        if not device_id or not note_date or not text:
            raise ValueError("Bitte Datum und Vermerk ausfuellen.")
        with connect() as conn:
            conn.execute(
                "INSERT INTO notes (device_id, note_date, user_name, text, created_at) VALUES (?, ?, ?, ?, ?)",
                (device_id, note_date, user.get("display_name") or user["email"], text, now_iso()),
            )
            audit(conn, user, "create", "note", device_id, {"note_date": note_date}, self.client_ip())
        self.send_json({"ok": True}, HTTPStatus.CREATED)

    def update_hours(self, user: dict, path: str) -> None:
        if not is_mentor_or_admin(user):
            self.send_json({"error": "Mentor- oder Administratorstatus erforderlich."}, HTTPStatus.FORBIDDEN)
            return
        device_id = unquote(path.removeprefix("/api/devices/").removesuffix("/hours"))
        payload = self.read_json()
        hours = self.optional_int(payload.get("current_print_hours"), "Druckstunden")
        if hours is None:
            raise ValueError("Bitte Druckstunden angeben.")
        with connect() as conn:
            conn.execute("UPDATE devices SET current_print_hours = ?, updated_at = ? WHERE id = ?", (hours, now_iso(), device_id))
            audit(conn, user, "update", "device_hours", device_id, {"current_print_hours": hours}, self.client_ip())
        self.send_json({"ok": True})

    def update_xl_tool(self, user: dict, path: str) -> None:
        if not is_mentor_or_admin(user):
            self.send_json({"error": "Mentor- oder Administratorstatus erforderlich."}, HTTPStatus.FORBIDDEN)
            return
        device_id = unquote(path.removeprefix("/api/devices/").removesuffix("/xl-tools"))
        payload = self.read_json()
        number = int(payload.get("tool_number", 0))
        if number < 1 or number > 5:
            raise ValueError("Tool muss zwischen 1 und 5 liegen.")
        with connect() as conn:
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
                    str(payload.get("nozzle_type", "")).strip()[:120],
                    str(payload.get("material", "")).strip()[:120],
                    str(payload.get("last_nozzle_change", "")).strip()[:20],
                    str(payload.get("issue_note", "")).strip()[:500],
                    user.get("display_name") or user["email"],
                    now_iso(),
                ),
            )
            audit(conn, user, "update", "xl_tool", f"{device_id}:{number}", payload, self.client_ip())
        self.send_json({"ok": True})

    def set_team_code(self, user: dict) -> None:
        if not is_admin(user):
            self.send_json({"error": "Administratorrechte erforderlich."}, HTTPStatus.FORBIDDEN)
            return
        payload = self.read_json()
        code = str(payload.get("team_code", "")).strip()
        if len(code) < 6:
            raise ValueError("Der Teamleiter-Code muss mindestens 6 Zeichen haben.")
        with connect() as conn:
            set_setting(conn, "team_code_hash", hash_secret(code))
            audit(conn, user, "update", "setting", "team_code_hash", {"changed": True}, self.client_ip())
        self.send_json({"ok": True})

    def save_device(self, user: dict) -> None:
        if not is_admin(user):
            self.send_json({"error": "Administratorrechte erforderlich."}, HTTPStatus.FORBIDDEN)
            return
        payload = self.read_json()
        device_id = str(payload.get("id", "")).strip()
        name = str(payload.get("name", "")).strip()
        kind = str(payload.get("kind", "")).strip()
        if not device_id or not name or kind not in {"mini", "mk3_5", "xl5"}:
            raise ValueError("Bitte ID, Name und gueltigen Typ angeben.")
        type_label = {"mini": "MINI+", "mk3_5": "MK3.5", "xl5": "XL 5-Tool"}[kind]
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO devices (id, kind, name, mentors, type_label, source_page, sort_order, active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 100, 1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET kind=excluded.kind, name=excluded.name, mentors=excluded.mentors, type_label=excluded.type_label, source_page=excluded.source_page, active=1, updated_at=excluded.updated_at
                """,
                (device_id, kind, name, str(payload.get("mentors", "")).strip(), type_label, type_label, now_iso(), now_iso()),
            )
            if kind == "xl5":
                for number in range(1, 6):
                    conn.execute("INSERT OR IGNORE INTO xl_tools (device_id, tool_number, updated_at) VALUES (?, ?, ?)", (device_id, number, now_iso()))
            audit(conn, user, "upsert", "device", device_id, payload, self.client_ip())
        self.send_json({"ok": True})

    def save_task(self, user: dict) -> None:
        if not is_admin(user):
            self.send_json({"error": "Administratorrechte erforderlich."}, HTTPStatus.FORBIDDEN)
            return
        payload = self.read_json()
        task_id = str(payload.get("id", "")).strip()
        title = str(payload.get("title", "")).strip()
        level = str(payload.get("level", "")).strip()
        if not task_id or not title or level not in {"B", "E", "M"}:
            raise ValueError("Bitte ID, Titel und Level angeben.")
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks (id, applies_to, title, details, level, interval_text, cadence_days, cadence_hours, sort_order, active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 100, 1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET applies_to=excluded.applies_to, title=excluded.title, details=excluded.details, level=excluded.level, interval_text=excluded.interval_text, cadence_days=excluded.cadence_days, cadence_hours=excluded.cadence_hours, active=1, updated_at=excluded.updated_at
                """,
                (
                    task_id,
                    str(payload.get("applies_to", "all")).strip(),
                    title,
                    str(payload.get("details", "")).strip(),
                    level,
                    str(payload.get("interval_text", "")).strip(),
                    self.optional_int(payload.get("cadence_days"), "Tage"),
                    self.optional_int(payload.get("cadence_hours"), "Stunden"),
                    now_iso(),
                    now_iso(),
                ),
            )
            audit(conn, user, "upsert", "task", task_id, payload, self.client_ip())
        self.send_json({"ok": True})

    def update_user(self, admin_user: dict, path: str) -> None:
        if not is_admin(admin_user):
            self.send_json({"error": "Administratorrechte erforderlich."}, HTTPStatus.FORBIDDEN)
            return
        user_id = int(path.rsplit("/", 1)[-1])
        payload = self.read_json()
        with connect() as conn:
            if "role" in payload:
                role = str(payload["role"])
                if not allowed_role(role):
                    raise ValueError("Ungueltige Rolle.")
                conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
            if "is_active" in payload:
                conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (1 if int(payload["is_active"]) else 0, user_id))
            audit(conn, admin_user, "update", "user", str(user_id), payload, self.client_ip())
        self.send_json({"ok": True})

    def manual_backup(self, user: dict) -> None:
        if not is_admin(user):
            self.send_json({"error": "Administratorrechte erforderlich."}, HTTPStatus.FORBIDDEN)
            return
        payload = self.read_json()
        path = create_backup(str(payload.get("reason", "manual")), user.get("display_name") or user["email"])
        with connect() as conn:
            audit(conn, user, "create", "backup", path.name, ip=self.client_ip())
        self.send_json({"ok": True, "file": path.name})

    def save_settings(self, user: dict) -> None:
        if not is_admin(user):
            self.send_json({"error": "Administratorrechte erforderlich."}, HTTPStatus.FORBIDDEN)
            return
        payload = self.read_json()
        with connect() as conn:
            if "teams_webhook_url" in payload:
                set_setting(conn, "teams_webhook_url", str(payload["teams_webhook_url"]).strip())
                audit(conn, user, "update", "setting", "teams_webhook_url", {"configured": bool(payload["teams_webhook_url"])}, self.client_ip())
        self.send_json({"ok": True})

    def export_csv(self) -> None:
        with connect() as conn:
            data = rows(
                conn,
                """
                SELECT 'wartung' AS typ, d.name AS geraet, l.done_on AS datum, t.title AS eintrag,
                       l.print_hours AS druckstunden, l.user_name AS benutzer, l.note AS vermerk, l.created_at AS erstellt
                FROM logs l JOIN devices d ON d.id = l.device_id JOIN tasks t ON t.id = l.task_id
                UNION ALL
                SELECT 'vermerk', d.name, n.note_date, 'Allgemeiner Vermerk', NULL, n.user_name, n.text, n.created_at
                FROM notes n JOIN devices d ON d.id = n.device_id
                ORDER BY geraet, erstellt
                """,
            )
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["typ", "geraet", "datum", "eintrag", "druckstunden", "benutzer", "vermerk", "erstellt"], delimiter=";")
        writer.writeheader()
        writer.writerows(data)
        body = output.getvalue().encode("utf-8-sig")
        self.send_bytes(body, "text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="wartung_fdm_space.csv"'})

    def optional_int(self, value, label: str) -> int | None:
        if value in (None, ""):
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} muss eine ganze Zahl sein.") from exc
        if parsed < 0:
            raise ValueError(f"{label} darf nicht negativ sein.")
        return parsed


def main() -> None:
    init_db()
    ensure_daily_backup()
    server = ThreadingHTTPServer((config.HOST, config.PORT), WartungHandler)
    scheme = "http"
    if config.SSL_CERT and config.SSL_KEY:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(config.SSL_CERT, config.SSL_KEY)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        scheme = "https"
    host_label = "127.0.0.1" if config.HOST in {"", "0.0.0.0"} else config.HOST
    print(f"Wartung FDM Space laeuft auf {scheme}://{host_label}:{config.PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
