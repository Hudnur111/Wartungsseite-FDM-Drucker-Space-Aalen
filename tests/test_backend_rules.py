from __future__ import annotations

import os
import subprocess
import sys
import unittest
from datetime import date, timedelta

from app import config
from app.maintenance import teams_payload
from app.reports import csv_cell, month_filter
from app.server import WartungHandler
from app.validators import optional_int, task_applies_to_device, valid_date, valid_id


class BackendRuleTests(unittest.TestCase):
    def test_valid_id_normalizes_safe_ids(self) -> None:
        self.assertEqual(valid_id(" Mini-Alpha_1 ", "ID"), "mini-alpha_1")

    def test_valid_id_rejects_paths_and_special_chars(self) -> None:
        with self.assertRaises(ValueError):
            valid_id("../mini", "ID")
        with self.assertRaises(ValueError):
            valid_id("mini alpha", "ID")

    def test_valid_date_rejects_future_dates(self) -> None:
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        with self.assertRaises(ValueError):
            valid_date(tomorrow, "Datum")

    def test_task_must_apply_to_device_kind(self) -> None:
        self.assertTrue(task_applies_to_device({"applies_to": "all"}, {"kind": "mini"}))
        self.assertTrue(task_applies_to_device({"applies_to": "xl5"}, {"kind": "xl5"}))
        self.assertFalse(task_applies_to_device({"applies_to": "xl5"}, {"kind": "mini"}))

    def test_csv_cells_are_formula_safe(self) -> None:
        self.assertEqual(csv_cell("=1+1"), "'=1+1")
        self.assertEqual(csv_cell("normal"), "normal")
        self.assertEqual(csv_cell(None), "")

    def test_legacy_handler_wrappers_still_delegate(self) -> None:
        self.assertEqual(WartungHandler.valid_id(None, " Mini-Alpha_1 ", "ID"), "mini-alpha_1")
        self.assertEqual(WartungHandler.optional_int(None, "12", "Druckstunden"), 12)

    def test_month_filter_and_optional_int_reject_invalid_values(self) -> None:
        self.assertEqual(month_filter("2026-06"), "2026-06")
        with self.assertRaises(ValueError):
            month_filter("06/2026")
        with self.assertRaises(ValueError):
            optional_int("-1", "Druckstunden")

    def test_proxy_headers_are_not_trusted_by_default(self) -> None:
        self.assertFalse(config.TRUST_PROXY)

    def test_railway_defaults_use_proxy_public_url_and_volume(self) -> None:
        env = os.environ.copy()
        for key in list(env):
            if key.startswith("WARTUNG_") or key.startswith("RAILWAY_"):
                env.pop(key)
        env.update(
            {
                "RAILWAY_ENVIRONMENT_NAME": "production",
                "RAILWAY_PUBLIC_DOMAIN": "example.up.railway.app",
                "RAILWAY_VOLUME_MOUNT_PATH": "/data",
            }
        )
        output = subprocess.check_output(
            [
                sys.executable,
                "-c",
                (
                    "from app import config; "
                    "print(config.TRUST_PROXY); "
                    "print(config.PUBLIC_URL); "
                    "print(config.DATA_DIR.as_posix()); "
                    "print(config.BACKUP_DIR.as_posix()); "
                    "print(config.DB_PATH.as_posix())"
                ),
            ],
            env=env,
            text=True,
        )
        self.assertEqual(
            output.strip().splitlines(),
            ["True", "https://example.up.railway.app", "/data", "/data/backups", "/data/wartung.db"],
        )

    def test_teams_payload_uses_professional_umlauts(self) -> None:
        payload = teams_payload([])
        self.assertIn("fällig", payload["text"])


if __name__ == "__main__":
    unittest.main()
