from __future__ import annotations

import http.cookiejar
import hashlib
import json
import os
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

    def login(self, email: str = "admin@example.test", password: str = "Password123") -> str:
        login_page = self.request("/login").read().decode("utf-8")
        marker = 'name="csrf_token" value="'
        csrf = login_page.split(marker, 1)[1].split('"', 1)[0]
        body = urllib.parse.urlencode({"email": email, "password": password, "csrf_token": csrf}).encode()
        self.request("/auth/login", body, {"Content-Type": "application/x-www-form-urlencoded"}).read()
        state = json.loads(self.request("/api/state").read().decode("utf-8"))
        return state["csrfToken"]

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


if __name__ == "__main__":
    unittest.main()
