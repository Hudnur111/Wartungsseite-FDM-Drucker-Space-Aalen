from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


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
                urllib.request.urlopen(f"{self.base}/healthz", timeout=0.25).close()
                break
            except OSError:
                time.sleep(0.05)
        else:
            self.fail("Server did not start")
        self.opener = urllib.request.build_opener()

    def tearDown(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)
        time.sleep(0.1)
        self.tmp.cleanup()

    def request(self, path: str, data: bytes | None = None, headers: dict[str, str] | None = None):
        request = urllib.request.Request(f"{self.base}{path}", data=data, headers=headers or {})
        return self.opener.open(request, timeout=5)

    def test_healthz_and_static_cache_headers(self) -> None:
        health = self.request("/healthz")
        payload = json.loads(health.read().decode("utf-8"))
        self.assertEqual(payload, {"ok": True, "service": "wartung-fdm-space"})
        self.assertEqual(health.headers["Cache-Control"], "no-store")

        styles = self.request("/static/styles.css")
        self.assertIn("text/css", styles.headers["Content-Type"])
        self.assertEqual(styles.headers["Cache-Control"], "public, max-age=3600")
        self.assertEqual(styles.headers["X-Content-Type-Options"], "nosniff")

    def test_legacy_access_pages_redirect_to_open_dashboard(self) -> None:
        page = self.request("/login").read().decode("utf-8")
        self.assertIn("FDM Wartung", page)
        self.assertNotIn("/forgot-password", page)

    def test_open_mode_state_uses_internal_admin_context(self) -> None:
        state = json.loads(self.request("/api/state").read().decode("utf-8"))
        self.assertEqual(state["user"]["role"], "Administrator")
        self.assertEqual(state["csrfToken"], "open-mode")
        self.assertGreaterEqual(len(state["devices"]), 1)

    def test_open_mode_create_log_backup_and_pdf_export_without_csrf(self) -> None:
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
            {"Content-Type": "application/json"},
        )
        self.assertEqual(response.status, 201)

        backup = self.request(
            "/api/admin/backups",
            json.dumps({"reason": "e2e"}).encode("utf-8"),
            {"Content-Type": "application/json"},
        )
        self.assertEqual(json.loads(backup.read().decode("utf-8"))["ok"], True)

        pdf = self.request("/api/export.pdf").read()
        self.assertTrue(pdf.startswith(b"%PDF-"))

    def test_invalid_backup_download_path_returns_json_error(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("/api/admin/backups/%2e%2e%2Fwartung.db/download").read()
        self.assertEqual(caught.exception.code, 400)
        payload = json.loads(caught.exception.read().decode("utf-8"))
        self.assertIn("error", payload)

    def test_open_admin_can_log_mentor_tasks(self) -> None:
        payload = {
            "device_id": "mini-alpha-1",
            "task_id": "plate-ipa",
            "done_on": date.today().isoformat(),
            "print_hours": "12",
            "note": "Open admin can log mentor task",
        }
        response = self.request(
            "/api/logs",
            json.dumps(payload).encode("utf-8"),
            {"Content-Type": "application/json"},
        )
        self.assertEqual(response.status, 201)

    def test_state_keeps_latest_log_by_date_outside_recent_window(self) -> None:
        db = self.root / "data" / "wartung.db"
        old_day = (date.today() - timedelta(days=60)).isoformat()
        today = date.today().isoformat()
        with sqlite3.connect(db) as conn:
            conn.execute(
                """
                INSERT INTO logs (device_id, task_id, done_on, print_hours, user_name, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("mini-alpha-1", "bed-scraps", today, 1, "FDM Space", "latest-by-date", today),
            )
            for index in range(105):
                conn.execute(
                    """
                    INSERT INTO logs (device_id, task_id, done_on, print_hours, user_name, note, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("mini-alpha-1", "bed-scraps", old_day, index + 2, "FDM Space", f"older-{index}", old_day),
                )
        state = json.loads(self.request("/api/state").read().decode("utf-8"))
        self.assertTrue(any(item["note"] == "latest-by-date" for item in state["logs"]))

    def test_xl_tool_change_rejects_future_date(self) -> None:
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
                {"Content-Type": "application/json"},
            ).read()
        self.assertEqual(caught.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
