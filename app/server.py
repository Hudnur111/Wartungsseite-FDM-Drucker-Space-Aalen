from __future__ import annotations

import csv
import html
import io
import json
import mimetypes
import smtplib
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from . import config
from .database import (
    audit,
    backup_inventory,
    backup_path,
    connect,
    create_backup,
    ensure_daily_backup,
    init_db,
    prune_backups,
    restore_backup,
    row,
    rows,
    set_setting,
    setting,
)
from .maintenance import due_items as build_due_items
from .maintenance import teams_payload as build_teams_payload
from .reports import csv_cell as report_csv_cell
from .reports import month_filter as report_month_filter
from .reports import pdf_bytes as build_pdf_bytes
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
from .validators import optional_int as parse_optional_int
from .validators import task_applies_to_device as task_matches_device
from .validators import valid_date as parse_valid_date
from .validators import valid_id as normalize_valid_id


def render_template(name: str, context: dict[str, str]) -> str:
    text = (config.TEMPLATE_DIR / name).read_text(encoding="utf-8")
    for key, value in context.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def html_message(message: str, kind: str) -> str:
    if not message:
        return ""
    return f'<div class="auth-message {kind}">{html.escape(message)}</div>'


OPEN_APP_USER = {
    "id": 0,
    "email": "open-mode@local",
    "display_name": "FDM Space",
    "role": config.ADMIN_ROLE,
    "csrf_token": "open-mode",
}


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
        if not config.TRUST_PROXY:
            return self.client_address[0]
        forwarded = self.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
        return forwarded or self.client_address[0]

    def is_secure_request(self) -> bool:
        if config.SSL_CERT and config.SSL_KEY:
            return True
        if not config.TRUST_PROXY:
            return False
        return self.headers.get("X-Forwarded-Proto", "").split(",", 1)[0].strip().lower() == "https"

    def security_headers(self, content_type: str) -> dict[str, str]:
        headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "same-origin",
            "Cross-Origin-Opener-Policy": "same-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        }
        if self.is_secure_request():
            headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if content_type.startswith("text/html"):
            headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "frame-ancestors 'none'; "
                "img-src 'self' data:; "
                "script-src 'self'; "
                "style-src 'self'"
            )
        return headers

    def send_bytes(self, body: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK, headers: dict[str, str] | None = None) -> None:
        extra_headers = dict(headers or {})
        cache_control = extra_headers.pop("Cache-Control", "no-store")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache_control)
        for key, value in self.security_headers(content_type).items():
            if key not in extra_headers:
                self.send_header(key, value)
        for key, value in extra_headers.items():
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
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Ungültige Anfragegröße.") from exc
        if size < 1 or size > 200_000:
            raise ValueError("Ungültige Anfragegröße.")
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
        secure = "; Secure" if self.is_secure_request() else ""
        return f"{config.SESSION_COOKIE}={token}; Path=/; Max-Age={age}; HttpOnly; SameSite=Lax{secure}"

    def auth_csrf_cookie(self, token: str) -> str:
        secure = "; Secure" if self.is_secure_request() else ""
        return f"{config.AUTH_CSRF_COOKIE}={token}; Path=/; Max-Age=1800; HttpOnly; SameSite=Lax{secure}"

    def current_user(self) -> dict | None:
        return dict(OPEN_APP_USER)

    def require_user(self, api: bool = False) -> dict | None:
        return self.current_user()

    def require_admin(self) -> dict | None:
        user = self.require_user(api=True)
        if not user:
            return None
        if not is_admin(user):
            self.send_json({"error": "Administratorrechte erforderlich."}, HTTPStatus.FORBIDDEN)
            return None
        return user

    def verify_session_csrf(self, user: dict) -> bool:
        return True

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

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/healthz":
            self.send_json({"ok": True, "service": "wartung-fdm-space"})
            return
        if path in {"/auth/login", "/auth/register", "/auth/forgot-password", "/login", "/register", "/forgot-password", "/reset-password"}:
            self.redirect("/")
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
            self.export_csv(query.get("month", [""])[0])
            return
        if path == "/api/export.pdf":
            if not self.require_user(api=True):
                return
            self.export_pdf(query.get("month", [""])[0])
            return
        if path.startswith("/api/admin/backups/") and path.endswith("/download"):
            user = self.require_admin()
            if not user:
                return
            try:
                self.download_backup(path)
            except ValueError as exc:
                message = str(exc)
                status = HTTPStatus.NOT_FOUND if "nicht gefunden" in message.lower() else HTTPStatus.BAD_REQUEST
                self.send_json({"error": message}, status)
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
        if content_type in {"text/css", "text/javascript", "application/javascript"}:
            content_type = f"{content_type}; charset=utf-8"
        self.send_bytes(path.read_bytes(), content_type, headers={"Cache-Control": "public, max-age=3600"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path.startswith("/auth/"):
                self.send_json({"ok": True, "auth": "disabled"})
                return
            if path == "/auth/login":
                self.login()
                return
            if path == "/auth/register":
                self.register()
                return
            if path == "/auth/forgot-password":
                self.request_password_reset()
                return
            if path == "/auth/reset-password":
                self.reset_password()
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
            if path == "/api/profile":
                self.update_profile(user)
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
            if path.startswith("/api/admin/backups/") and path.endswith("/restore"):
                self.restore_backup_endpoint(user, path)
                return
            if path == "/api/admin/backups/prune":
                self.prune_backups_endpoint(user)
                return
            if path == "/api/admin/notifications/due":
                self.send_due_notifications(user)
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
        if not is_mentor_or_admin(user):
            self.send_json({"error": "Mentor- oder Administratorstatus erforderlich."}, HTTPStatus.FORBIDDEN)
            return
        if len(path) == 3 and path[0] == "api" and path[1] in {"logs", "notes"}:
            table = path[1]
            try:
                item_id = int(path[2])
            except ValueError:
                self.send_json({"error": "Ungültige ID."}, HTTPStatus.BAD_REQUEST)
                return
            with connect() as conn:
                existing = row(conn, f"SELECT id FROM {table} WHERE id = ?", (item_id,))
                if not existing:
                    self.send_json({"error": "Eintrag nicht gefunden."}, HTTPStatus.NOT_FOUND)
                    return
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
                              AND (
                                  newer.done_on > current.done_on
                                  OR (newer.done_on = current.done_on AND newer.id > current.id)
                              )
                        )
                    ),
                    recent AS (
                        SELECT id
                        FROM logs
                        ORDER BY id DESC
                        LIMIT ?
                    )
                    SELECT *
                    FROM logs
                    WHERE id IN (
                        SELECT id FROM latest
                        UNION
                        SELECT id FROM recent
                    )
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
                              AND (
                                  newer.note_date > current.note_date
                                  OR (newer.note_date = current.note_date AND newer.id > current.id)
                              )
                        )
                    ),
                    recent AS (
                        SELECT id
                        FROM notes
                        ORDER BY id DESC
                        LIMIT ?
                    )
                    SELECT *
                    FROM notes
                    WHERE id IN (
                        SELECT id FROM latest
                        UNION
                        SELECT id FROM recent
                    )
                    ORDER BY id DESC
                    """,
                    (config.STATE_RECENT_NOTE_LIMIT,),
                ),
                "xlTools": rows(conn, "SELECT * FROM xl_tools ORDER BY device_id, tool_number"),
            }

    def admin_payload(self) -> dict:
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

    def month_filter(self, month: str) -> str:
        return report_month_filter(month)

    def due_items(self, conn) -> list[dict]:
        return build_due_items(conn)

    def teams_payload(self, items: list[dict]) -> dict:
        return build_teams_payload(items)

    def post_teams_webhook(self, webhook_url: str, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(webhook_url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                if response.status >= 300:
                    raise ValueError(f"Teams Webhook antwortete mit Status {response.status}.")
        except urllib.error.URLError as exc:
            raise ValueError(f"Teams Webhook konnte nicht erreicht werden: {exc.reason}") from exc

    def pdf_bytes(self, lines: list[str]) -> bytes:
        return build_pdf_bytes(lines)

    def login_limited(self, conn, email: str) -> bool:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).replace(microsecond=0).isoformat()
        conn.execute("DELETE FROM login_attempts WHERE created_at < ?", (cutoff,))
        count = conn.execute(
            "SELECT COUNT(*) FROM login_attempts WHERE email = ? AND ip_address = ? AND success = 0 AND created_at >= ?",
            (email, self.client_ip(), cutoff),
        ).fetchone()[0]
        return count >= 5

    def public_base_url(self) -> str:
        if config.PUBLIC_URL:
            return config.PUBLIC_URL
        scheme = "https" if self.is_secure_request() else "http"
        host = self.headers.get("Host", f"127.0.0.1:{config.PORT}").strip()
        return f"{scheme}://{host}".rstrip("/")

    def password_reset_limited(self, conn, user_id: int) -> bool:
        now = now_iso()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(microsecond=0).isoformat()
        conn.execute("DELETE FROM password_reset_tokens WHERE expires_at <= ? OR used_at IS NOT NULL", (now,))
        ip_count = conn.execute(
            "SELECT COUNT(*) FROM password_reset_tokens WHERE request_ip = ? AND created_at >= ?",
            (self.client_ip(), cutoff),
        ).fetchone()[0]
        user_count = conn.execute(
            "SELECT COUNT(*) FROM password_reset_tokens WHERE user_id = ? AND created_at >= ?",
            (user_id, cutoff),
        ).fetchone()[0]
        return ip_count >= 8 or user_count >= 3

    def password_reset_user(self, token: str) -> dict | None:
        token = str(token or "").strip()
        if len(token) < 20:
            return None
        with connect() as conn:
            return row(
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

    def send_password_reset_email(self, email: str, display_name: str, link: str, user_id: int) -> str:
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
            smtp_class = smtplib.SMTP_SSL if config.SMTP_SSL else smtplib.SMTP
            with smtp_class(config.SMTP_HOST, config.SMTP_PORT, timeout=12) as smtp:
                if config.SMTP_STARTTLS and not config.SMTP_SSL:
                    smtp.starttls()
                if config.SMTP_USER:
                    smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
                smtp.send_message(message)
            return "smtp"
        if config.PASSWORD_RESET_DEV_OUTBOX:
            outbox = config.DATA_DIR / "password_reset_outbox"
            outbox.mkdir(parents=True, exist_ok=True)
            stamp = now_iso().replace(":", "").replace("-", "").split("+", 1)[0]
            target = outbox / f"password-reset-{stamp}-{user_id}.txt"
            target.write_text(f"To: {email}\nSubject: {subject}\n\n{text}", encoding="utf-8")
            print(f"Passwort-Reset-Link wurde lokal gespeichert: {target}")
            return "dev_outbox"
        return "not_configured"

    def valid_date(self, value: str, label: str, allow_future: bool = False) -> str:
        return parse_valid_date(value, label, allow_future)

    def valid_id(self, value: str, label: str) -> str:
        return normalize_valid_id(value, label)

    def active_device(self, conn, device_id: str) -> dict:
        device = row(conn, "SELECT * FROM devices WHERE id = ? AND active = 1", (device_id,))
        if not device:
            raise ValueError("Gerät nicht gefunden oder deaktiviert.")
        return device

    def active_task(self, conn, task_id: str) -> dict:
        task = row(conn, "SELECT * FROM tasks WHERE id = ? AND active = 1", (task_id,))
        if not task:
            raise ValueError("Wartungspunkt nicht gefunden.")
        return task

    def task_applies_to_device(self, task: dict, device: dict) -> bool:
        return task_matches_device(task, device)

    def login(self) -> None:
        form = self.read_form()
        if not self.verify_auth_csrf(form):
            self.auth_page("login", error="Sicherheits-Token ungültig. Bitte erneut versuchen.")
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

    def request_password_reset(self) -> None:
        form = self.read_form()
        if not self.verify_auth_csrf(form):
            self.auth_page("forgot", error="Sicherheits-Token ungültig. Bitte erneut versuchen.")
            return
        email = normalize_email(form.get("email", ""))
        message = "Wenn diese E-Mail registriert ist, wurde ein Link zum Zurücksetzen versendet."
        delivery_message = ""
        if "@" not in email:
            self.auth_page("forgot", message=message)
            return
        with connect() as conn:
            user = conn.execute("SELECT id, email, display_name FROM users WHERE email = ? AND is_active = 1", (email,)).fetchone()
            if user and not self.password_reset_limited(conn, int(user["id"])):
                token = new_token()
                expires_at = (datetime.now(timezone.utc) + timedelta(minutes=config.PASSWORD_RESET_MINUTES)).replace(microsecond=0).isoformat()
                conn.execute(
                    """
                    INSERT INTO password_reset_tokens (user_id, token_hash, request_ip, user_agent, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (user["id"], hash_token(token), self.client_ip(), self.headers.get("User-Agent", "")[:300], now_iso(), expires_at),
                )
                link = f"{self.public_base_url()}/reset-password?token={quote(token)}"
                try:
                    delivery = self.send_password_reset_email(user["email"], user["display_name"], link, int(user["id"]))
                except (OSError, smtplib.SMTPException, ValueError) as exc:
                    delivery = "failed"
                    print(f"Passwort-Reset-Mail konnte nicht versendet werden: {exc}")
                if delivery == "dev_outbox":
                    delivery_message = "Lokaler Entwicklungsmodus: Der Reset-Link wurde in data/password_reset_outbox/ gespeichert."
                elif delivery == "not_configured":
                    delivery_message = "Mailversand ist noch nicht konfiguriert. Bitte SMTP-Variablen setzen."
                audit(conn, None, "request", "password_reset", str(user["id"]), {"delivery": delivery}, self.client_ip())
        self.auth_page("forgot", message=delivery_message or message)

    def reset_password(self) -> None:
        form = self.read_form()
        token = str(form.get("token", "")).strip()
        if not self.verify_auth_csrf(form):
            self.auth_page("reset", error="Sicherheits-Token ungültig. Bitte erneut versuchen.", reset_token=token)
            return
        password = str(form.get("password", ""))
        confirm = str(form.get("password_confirm", ""))
        if password != confirm:
            self.auth_page("reset", error="Die Passwörter stimmen nicht überein.", reset_token=token)
            return
        if len(password) < 8:
            self.auth_page("reset", error="Das Passwort muss mindestens 8 Zeichen haben.", reset_token=token)
            return
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
                self.auth_page("forgot", error="Der Link ist ungültig oder abgelaufen. Bitte fordere einen neuen Link an.")
                return
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), reset["user_id"]))
            conn.execute("UPDATE password_reset_tokens SET used_at = ? WHERE id = ?", (now_iso(), reset["reset_id"]))
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (reset["user_id"],))
            conn.execute("DELETE FROM login_attempts WHERE email = ?", (reset["email"],))
            audit(conn, {"id": reset["user_id"], "display_name": reset["display_name"], "email": reset["email"]}, "reset", "password", str(reset["user_id"]), ip=self.client_ip())
        self.redirect("/login?message=Passwort%20wurde%20aktualisiert.%20Bitte%20melde%20dich%20neu%20an.")

    def register(self) -> None:
        form = self.read_form()
        if not self.verify_auth_csrf(form):
            self.auth_page("register", error="Sicherheits-Token ungültig. Bitte erneut versuchen.")
            return
        display_name = form.get("display_name", "").strip()
        email = normalize_email(form.get("email", ""))
        password = form.get("password", "")
        code = form.get("team_code", "").strip()
        if len(display_name) < 2 or "@" not in email or len(password) < 8:
            self.auth_page("register", error="Bitte Name, gültige E-Mail und Passwort ab 8 Zeichen eingeben.")
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
        done_on = self.valid_date(str(payload.get("done_on", "")).strip(), "Datum")
        note = str(payload.get("note", "")).strip()[:1000]
        print_hours = self.optional_int(payload.get("print_hours"), "Druckstunden")
        if not device_id or not task_id or not done_on:
            raise ValueError("Bitte Gerät, Wartungspunkt und Datum ausfüllen.")
        with connect() as conn:
            device = self.active_device(conn, device_id)
            task = self.active_task(conn, task_id)
            if not self.task_applies_to_device(task, device):
                raise ValueError("Dieser Wartungspunkt gehört nicht zu diesem Gerät.")
            if not can_log_level(user, task["level"]):
                self.send_json({"error": "Für diesen Wartungspunkt ist Mentor- oder Administratorstatus erforderlich."}, HTTPStatus.FORBIDDEN)
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
        note_date = self.valid_date(str(payload.get("note_date", "")).strip(), "Datum")
        text = str(payload.get("text", "")).strip()[:1000]
        if not device_id or not note_date or not text:
            raise ValueError("Bitte Datum und Vermerk ausfüllen.")
        with connect() as conn:
            self.active_device(conn, device_id)
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
            self.active_device(conn, device_id)
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
        last_nozzle_change = str(payload.get("last_nozzle_change", "")).strip()[:20]
        if last_nozzle_change:
            last_nozzle_change = self.valid_date(last_nozzle_change, "Letzter Wechsel")
        with connect() as conn:
            device = self.active_device(conn, device_id)
            if device["kind"] != "xl5":
                raise ValueError("Toolheads können nur für XL 5-Tool-Geräte gepflegt werden.")
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
                    last_nozzle_change,
                    str(payload.get("issue_note", "")).strip()[:500],
                    user.get("display_name") or user["email"],
                    now_iso(),
                ),
            )
            audit(conn, user, "update", "xl_tool", f"{device_id}:{number}", payload, self.client_ip())
        self.send_json({"ok": True})

    def update_profile(self, user: dict) -> None:
        payload = self.read_json()
        display_name = str(payload.get("display_name", "")).strip()[:120]
        password = str(payload.get("password", ""))
        if len(display_name) < 2:
            raise ValueError("Bitte gib einen gültigen Namen ein.")
        if password and len(password) < 8:
            raise ValueError("Das neue Passwort muss mindestens 8 Zeichen haben.")
        with connect() as conn:
            conn.execute("UPDATE users SET display_name = ? WHERE id = ?", (display_name, user["id"]))
            if password:
                conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), user["id"]))
            audit(conn, user, "update", "profile", str(user["id"]), {"password_changed": bool(password)}, self.client_ip())
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
        device_id = self.valid_id(str(payload.get("id", "")), "Geräte-ID")
        name = str(payload.get("name", "")).strip()[:120]
        kind = str(payload.get("kind", "")).strip()
        if not device_id or not name or kind not in {"mini", "mk3_5", "xl5"}:
            raise ValueError("Bitte ID, Name und gültigen Typ angeben.")
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
        task_id = self.valid_id(str(payload.get("id", "")), "Wartungspunkt-ID")
        title = str(payload.get("title", "")).strip()[:160]
        level = str(payload.get("level", "")).strip()
        applies_to = str(payload.get("applies_to", "all")).strip()
        if not task_id or not title or level not in {"B", "E", "M"} or applies_to not in {"all", "mini", "mk3_5", "xl5"}:
            raise ValueError("Bitte ID, Titel, Gerätetyp und Level angeben.")
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks (id, applies_to, title, details, level, interval_text, cadence_days, cadence_hours, sort_order, active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 100, 1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET applies_to=excluded.applies_to, title=excluded.title, details=excluded.details, level=excluded.level, interval_text=excluded.interval_text, cadence_days=excluded.cadence_days, cadence_hours=excluded.cadence_hours, active=1, updated_at=excluded.updated_at
                """,
                (
                    task_id,
                    applies_to,
                    title,
                    str(payload.get("details", "")).strip()[:1200],
                    level,
                    str(payload.get("interval_text", "")).strip()[:160],
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
        try:
            user_id = int(path.rsplit("/", 1)[-1])
        except ValueError:
            raise ValueError("Ungültige Benutzer-ID.")
        payload = self.read_json()
        with connect() as conn:
            target = row(conn, "SELECT id, role, is_active FROM users WHERE id = ?", (user_id,))
            if not target:
                self.send_json({"error": "Benutzer nicht gefunden."}, HTTPStatus.NOT_FOUND)
                return
            new_role = str(payload["role"]) if "role" in payload else target["role"]
            if "is_active" in payload:
                new_active = 1 if int(payload["is_active"]) else 0
            else:
                new_active = int(target["is_active"])
            if not allowed_role(new_role):
                raise ValueError("Ungültige Rolle.")
            if user_id == admin_user["id"] and (new_role != config.ADMIN_ROLE or not new_active):
                raise ValueError("Du kannst deinen eigenen Administratorzugang nicht entziehen.")
            if target["role"] == config.ADMIN_ROLE and (new_role != config.ADMIN_ROLE or not new_active):
                other_admins = conn.execute(
                    "SELECT COUNT(*) FROM users WHERE id <> ? AND role = ? AND is_active = 1",
                    (user_id, config.ADMIN_ROLE),
                ).fetchone()[0]
                if other_admins < 1:
                    raise ValueError("Mindestens ein aktiver Administrator muss erhalten bleiben.")
            if "role" in payload:
                conn.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
            if "is_active" in payload:
                conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_active, user_id))
            if "password" in payload:
                password = str(payload["password"])
                if len(password) < 8:
                    raise ValueError("Das neue Passwort muss mindestens 8 Zeichen haben.")
                conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), user_id))
                conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            audit_details = {key: value for key, value in payload.items() if key != "password"}
            if "password" in payload:
                audit_details["password_changed"] = True
            audit(conn, admin_user, "update", "user", str(user_id), audit_details, self.client_ip())
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

    def download_backup(self, path: str) -> None:
        file_name = unquote(path.removeprefix("/api/admin/backups/").removesuffix("/download"))
        backup = backup_path(file_name)
        self.send_bytes(
            backup.read_bytes(),
            "application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{quote(backup.name)}"'},
        )

    def restore_backup_endpoint(self, user: dict, path: str) -> None:
        if not is_admin(user):
            self.send_json({"error": "Administratorrechte erforderlich."}, HTTPStatus.FORBIDDEN)
            return
        file_name = unquote(path.removeprefix("/api/admin/backups/").removesuffix("/restore"))
        safety = restore_backup(file_name, user.get("display_name") or user["email"])
        with connect() as conn:
            audit(conn, user, "restore", "backup", file_name, {"safety_backup": safety.name}, self.client_ip())
        self.send_json({"ok": True, "safety_backup": safety.name})

    def prune_backups_endpoint(self, user: dict) -> None:
        if not is_admin(user):
            self.send_json({"error": "Administratorrechte erforderlich."}, HTTPStatus.FORBIDDEN)
            return
        payload = self.read_json()
        keep = self.optional_int(payload.get("keep"), "Anzahl") or 20
        removed = prune_backups(keep)
        with connect() as conn:
            audit(conn, user, "prune", "backup", "backups", {"keep": keep, "removed": removed}, self.client_ip())
        self.send_json({"ok": True, "removed": removed})

    def send_due_notifications(self, user: dict) -> None:
        if not is_admin(user):
            self.send_json({"error": "Administratorrechte erforderlich."}, HTTPStatus.FORBIDDEN)
            return
        with connect() as conn:
            webhook_url = setting(conn, "teams_webhook_url")
            if not webhook_url:
                raise ValueError("Bitte zuerst eine Teams Webhook URL speichern.")
            items = self.due_items(conn)
            self.post_teams_webhook(webhook_url, self.teams_payload(items))
            set_setting(conn, "teams_last_due_notification", now_iso())
            audit(conn, user, "send", "notification", "teams_due", {"items": len(items)}, self.client_ip())
        self.send_json({"ok": True, "sent": len(items)})

    def save_settings(self, user: dict) -> None:
        if not is_admin(user):
            self.send_json({"error": "Administratorrechte erforderlich."}, HTTPStatus.FORBIDDEN)
            return
        payload = self.read_json()
        with connect() as conn:
            if "teams_webhook_url" in payload:
                webhook_url = str(payload["teams_webhook_url"]).strip()[:500]
                parsed = urlparse(webhook_url)
                if webhook_url and (parsed.scheme not in {"http", "https"} or not parsed.netloc):
                    raise ValueError("Teams Webhook URL muss mit http:// oder https:// beginnen.")
                set_setting(conn, "teams_webhook_url", webhook_url)
                audit(conn, user, "update", "setting", "teams_webhook_url", {"configured": bool(webhook_url)}, self.client_ip())
        self.send_json({"ok": True})

    def export_csv(self, month: str = "") -> None:
        month = self.month_filter(month)
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
        writer.writerows([{key: self.csv_cell(value) for key, value in item.items()} for item in data])
        body = output.getvalue().encode("utf-8-sig")
        suffix = f"_{month}" if month else ""
        self.send_bytes(body, "text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="wartung_fdm_space{suffix}.csv"'})

    def export_pdf(self, month: str = "") -> None:
        month = self.month_filter(month)
        with connect() as conn:
            due = self.due_items(conn)
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
        suffix = f"_{month}" if month else ""
        self.send_bytes(
            self.pdf_bytes(lines),
            "application/pdf",
            headers={"Content-Disposition": f'attachment; filename="wartung_fdm_space{suffix}.pdf"'},
        )

    def csv_cell(self, value):
        return report_csv_cell(value)

    def optional_int(self, value, label: str) -> int | None:
        return parse_optional_int(value, label)


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
    print(f"Wartung FDM Space läuft auf {scheme}://{host_label}:{config.PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
