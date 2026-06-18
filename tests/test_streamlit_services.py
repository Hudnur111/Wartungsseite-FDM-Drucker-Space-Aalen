from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StreamlitServiceTests(unittest.TestCase):
    def test_first_registration_creates_admin_without_team_code(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            env = os.environ.copy()
            for key in list(env):
                if key.startswith("WARTUNG_") or key == "TEAMLEITER_CODE":
                    env.pop(key)
            env.update(
                {
                    "WARTUNG_DATA_DIR": str(root / "data"),
                    "WARTUNG_BACKUP_DIR": str(root / "backups"),
                    "WARTUNG_DB_PATH": str(root / "data" / "wartung.db"),
                }
            )
            script = textwrap.dedent(
                """
                from app.database import init_db
                from app.streamlit_services import register

                init_db()
                user, error = register("Admin", "admin@example.test", "Password123", "")
                print(error or "")
                print(user["role"])
                """
            )
            output = subprocess.check_output([sys.executable, "-c", script], cwd=ROOT, env=env, text=True)
        self.assertEqual(output.strip().splitlines(), ["Administrator"])

    def test_registration_repairs_setup_when_no_active_admin_exists(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            env = os.environ.copy()
            for key in list(env):
                if key.startswith("WARTUNG_") or key == "TEAMLEITER_CODE":
                    env.pop(key)
            env.update(
                {
                    "WARTUNG_DATA_DIR": str(root / "data"),
                    "WARTUNG_BACKUP_DIR": str(root / "backups"),
                    "WARTUNG_DB_PATH": str(root / "data" / "wartung.db"),
                }
            )
            script = textwrap.dedent(
                """
                from app.database import connect, init_db
                from app.security import hash_password, now_iso
                from app.streamlit_services import register

                init_db()
                with connect() as conn:
                    conn.execute(
                        "INSERT INTO users (email, display_name, password_hash, role, is_active, created_at) VALUES (?, ?, ?, 'Benutzer', 1, ?)",
                        ("user@example.test", "User", hash_password("Password123"), now_iso()),
                    )
                user, error = register("Admin", "admin@example.test", "Password123", "")
                print(error or "")
                print(user["role"])
                """
            )
            output = subprocess.check_output([sys.executable, "-c", script], cwd=ROOT, env=env, text=True)
        self.assertEqual(output.strip().splitlines(), ["Administrator"])


if __name__ == "__main__":
    unittest.main()
