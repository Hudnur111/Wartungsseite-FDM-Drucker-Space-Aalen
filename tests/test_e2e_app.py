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
import urllib.parse
import urllib.request
from datetime import date
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
        db = self.root / "data" / "wartung.db"
        conn = sqlite3.connect(db)
        try:
            conn.execute(
                """
                INSERT INTO users (email, display_name, password_hash, role, is_active, created_at)
                VALUES (?, ?, ?, 'Administrator', 1, ?)
                """,
                ("admin@example.test", "Admin", password_hash("Password123"), date.today().isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

    def request(self, path: str, data: bytes | None = None, headers: dict[str, str] | None = None):
        request = urllib.request.Request(f"{self.base}{path}", data=data, headers=headers or {})
        return self.opener.open(request, timeout=5)

    def login(self) -> str:
        login_page = self.request("/login").read().decode("utf-8")
        marker = 'name="csrf_token" value="'
        csrf = login_page.split(marker, 1)[1].split('"', 1)[0]
        body = urllib.parse.urlencode({"email": "admin@example.test", "password": "Password123", "csrf_token": csrf}).encode()
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


if __name__ == "__main__":
    unittest.main()
