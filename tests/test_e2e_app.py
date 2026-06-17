from __future__ import annotations

import http.cookiejar
import hashlib
import json
import os
import re
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}"


class AppE2ETests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.tmp.name)
        self.port = free_port()
        env = os.environ.copy()
        env.update(
            {
                "WARTUNG_HOST": "127.0.0.1",
                "WARTUNG_PORT": str(self.port),
                "WARTUNG_DATA_DIR": str(self.root / "data"),
                "WARTUNG_BACKUP_DIR": str(self.root / "backups"),
                "WARTUNG_DB_PATH": str(self.root / "data" / "wartung.db"),
                "WARTUNG_STATE_RECENT_LOG_LIMIT": "100",
                "WARTUNG_STATE_RECENT_NOTE_LIMIT": "100",
                "WARTUNG_RESET_DEV_OUTBOX": "1",
                "WARTUNG_BOOTSTRAP_ADMIN_EMAIL": "bootstrap@example.test",
                "WARTUNG_BOOTSTRAP_ADMIN_NAME": "Bootstrap Admin",
                "WARTUNG_BOOTSTRAP_ADMIN_PASSWORD": "Bootstrap123",
                "TEAMLEITER_CODE": "test-team-code",
            }
        )
        self.process = subprocess.Popen(
            [sys.executable, "run.py"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.base = f"http://127.0.0.1:{self.port}"
        for _ in range(80):
            try:
                urllib.request.urlopen(f"{self.base}/login", timeout=0.25).close()
                break
            except OSError:
                time.sleep(0.05)
        else:
            self.fail("Server did not start")
        self.create_admin()
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def tearDown(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        time.sleep(0.1)
        self.tmp.cleanup()

    def create_admin(self) -> None:
        self.create_user("admin@example.test", "Admin", "Administrator")

    def create_user(self, email: str, display_name: str, role: str) -> None:
        db = self.root / "data" / "wartung.db"
        conn = sqlite3.connect(db)
        try:
            conn.execute(
                """
                INSERT INTO users (email, display_name, password_hash, role, is_active, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
                """,
                (email, display_name, password_hash("Password123"), role, date.today().isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

    def request(self, path: str, data: bytes | None = None, headers: dict[str, str] | None = None):
        request = urllib.request.Request(f"{self.base}{path}", data=data, headers=headers or {})
        return self.opener.open(request, timeout=5)

    def auth_csrf(self, path: str) -> str:
        page = self.request(path).read().decode("utf-8")
        marker = 'name="csrf_token" value="'
        return page.split(marker, 1)[1].split('"', 1)[0]

    def login(self, email: str = "admin@example.test", password: str = "Password123") -> str:
        csrf = self.auth_csrf("/login")
        body = urllib.parse.urlencode({"email": email, "password": password, "csrf_token": csrf}).encode()
        self.request("/auth/login", body, {"Content-Type": "application/x-www-form-urlencoded"}).read()
        state = json.loads(self.request("/api/state").read().decode("utf-8"))
        return state["csrfToken"]

    def test_healthz_and_static_cache_headers(self) -> None:
        health = self.request("/healthz")
        payload = json.loads(health.read().decode("utf-8"))
        self.assertEqual(payload, {"ok": True, "service": "wartung-fdm-space"})
        self.assertEqual(health.headers["Cache-Control"], "no-store")

        styles = self.request("/static/styles.css")
        self.assertIn("text/css", styles.headers["Content-Type"])
        self.assertEqual(styles.headers["Cache-Control"], "public, max-age=3600")
        self.assertEqual(styles.headers["X-Content-Type-Options"], "nosniff")

    def test_auth_get_endpoints_redirect_to_pages(self) -> None:
        login_page = self.request("/auth/login").read().decode("utf-8")
        self.assertIn("Anmelden", login_page)
        register_page = self.request("/auth/register").read().decode("utf-8")
        self.assertIn("Registrieren", register_page)

    def test_bootstrap_admin_can_login(self) -> None:
        csrf = self.login("bootstrap@example.test", "Bootstrap123")
        self.assertTrue(csrf)

    def test_login_create_log_backup_and_pdf_export(self) -> None:
        csrf = self.login()
        payload = {
            "device_id": "mini-alpha-1",
            "task_id": "bed-scraps",
            "done_on": date.today().isoformat(),
            "print_hours": "12",
            "note": "E2E smoke",
        }
        response = self.request(
            "/api/logs",
            json.dumps(payload).encode("utf-8"),
            {"Content-Type": "application/json", "X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status, 201)

        backup = self.request(
            "/api/admin/backups",
            json.dumps({"reason": "e2e"}).encode("utf-8"),
            {"Content-Type": "application/json", "X-CSRF-Token": csrf},
        )
        self.assertEqual(json.loads(backup.read().decode("utf-8"))["ok"], True)

        pdf = self.request("/api/export.pdf").read()
        self.assertTrue(pdf.startswith(b"%PDF-"))

    def test_invalid_backup_download_path_returns_json_error(self) -> None:
        self.login()
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("/api/admin/backups/%2e%2e%2Fwartung.db/download").read()
        self.assertEqual(caught.exception.code, 400)
        payload = json.loads(caught.exception.read().decode("utf-8"))
        self.assertIn("error", payload)

    def test_password_reset_flow_updates_password_and_clears_locks(self) -> None:
        db = self.root / "data" / "wartung.db"
        with sqlite3.connect(db) as conn:
            conn.execute(
                "INSERT INTO login_attempts (email, ip_address, success, created_at) VALUES (?, ?, 0, ?)",
                ("admin@example.test", "127.0.0.1", date.today().isoformat()),
            )

        csrf = self.auth_csrf("/forgot-password")
        body = urllib.parse.urlencode({"email": "admin@example.test", "csrf_token": csrf}).encode()
        page = self.request("/auth/forgot-password", body, {"Content-Type": "application/x-www-form-urlencoded"}).read().decode("utf-8")
        self.assertIn("password_reset_outbox", page)

        outbox = self.root / "data" / "password_reset_outbox"
        files = sorted(outbox.glob("password-reset-*.txt"))
        self.assertTrue(files)
        message = files[-1].read_text(encoding="utf-8")
        token = re.search(r"/reset-password\?token=([A-Za-z0-9_-]+)", message).group(1)

        csrf = self.auth_csrf(f"/reset-password?token={token}")
        body = urllib.parse.urlencode(
            {
                "token": token,
                "password": "Password456",
                "password_confirm": "Password456",
                "csrf_token": csrf,
            }
        ).encode()
        self.request("/auth/reset-password", body, {"Content-Type": "application/x-www-form-urlencoded"}).read()

        with sqlite3.connect(db) as conn:
            attempts = conn.execute("SELECT COUNT(*) FROM login_attempts WHERE email = ?", ("admin@example.test",)).fetchone()[0]
            used = conn.execute("SELECT COUNT(*) FROM password_reset_tokens WHERE used_at IS NOT NULL").fetchone()[0]
        self.assertEqual(attempts, 0)
        self.assertEqual(used, 1)
        self.assertTrue(self.login(password="Password456"))

    def test_write_api_rejects_missing_csrf_token(self) -> None:
        self.login()
        payload = {
            "device_id": "mini-alpha-1",
            "task_id": "bed-scraps",
            "done_on": date.today().isoformat(),
            "print_hours": "12",
            "note": "Missing csrf",
        }
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("/api/logs", json.dumps(payload).encode("utf-8"), {"Content-Type": "application/json"}).read()
        self.assertEqual(caught.exception.code, 403)

    def test_regular_user_cannot_log_mentor_tasks(self) -> None:
        self.create_user("user@example.test", "User", "Benutzer")
        csrf = self.login("user@example.test")
        payload = {
            "device_id": "mini-alpha-1",
            "task_id": "plate-ipa",
            "done_on": date.today().isoformat(),
            "print_hours": "12",
            "note": "Should be forbidden",
        }
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request(
                "/api/logs",
                json.dumps(payload).encode("utf-8"),
                {"Content-Type": "application/json", "X-CSRF-Token": csrf},
            ).read()
        self.assertEqual(caught.exception.code, 403)

    def test_state_keeps_latest_log_by_date_outside_recent_window(self) -> None:
        self.login()
        db = self.root / "data" / "wartung.db"
        old_day = (date.today() - timedelta(days=60)).isoformat()
        today = date.today().isoformat()
        with sqlite3.connect(db) as conn:
            conn.execute(
                """
                INSERT INTO logs (device_id, task_id, done_on, print_hours, user_name, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("mini-alpha-1", "bed-scraps", today, 1, "Admin", "latest-by-date", today),
            )
            for index in range(105):
                conn.execute(
                    """
                    INSERT INTO logs (device_id, task_id, done_on, print_hours, user_name, note, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("mini-alpha-1", "bed-scraps", old_day, index + 2, "Admin", f"older-{index}", old_day),
                )
        state = json.loads(self.request("/api/state").read().decode("utf-8"))
        self.assertTrue(any(item["note"] == "latest-by-date" for item in state["logs"]))

    def test_xl_tool_change_rejects_future_date(self) -> None:
        csrf = self.login()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        payload = {
            "tool_number": 1,
            "nozzle_type": "0.4 brass",
            "material": "PLA",
            "last_nozzle_change": tomorrow,
            "issue_note": "future date should fail",
        }
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request(
                "/api/devices/xl-5-tool/xl-tools",
                json.dumps(payload).encode("utf-8"),
                {"Content-Type": "application/json", "X-CSRF-Token": csrf},
            ).read()
        self.assertEqual(caught.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
