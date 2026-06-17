from __future__ import annotations

import unittest
from datetime import date, timedelta

from app.server import WartungHandler


class BackendRuleTests(unittest.TestCase):
    def test_valid_id_normalizes_safe_ids(self) -> None:
        self.assertEqual(WartungHandler.valid_id(None, " Mini-Alpha_1 ", "ID"), "mini-alpha_1")

    def test_valid_id_rejects_paths_and_special_chars(self) -> None:
        with self.assertRaises(ValueError):
            WartungHandler.valid_id(None, "../mini", "ID")
        with self.assertRaises(ValueError):
            WartungHandler.valid_id(None, "mini alpha", "ID")

    def test_valid_date_rejects_future_dates(self) -> None:
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        with self.assertRaises(ValueError):
            WartungHandler.valid_date(None, tomorrow, "Datum")

    def test_task_must_apply_to_device_kind(self) -> None:
        self.assertTrue(WartungHandler.task_applies_to_device(None, {"applies_to": "all"}, {"kind": "mini"}))
        self.assertTrue(WartungHandler.task_applies_to_device(None, {"applies_to": "xl5"}, {"kind": "xl5"}))
        self.assertFalse(WartungHandler.task_applies_to_device(None, {"applies_to": "xl5"}, {"kind": "mini"}))

    def test_csv_cells_are_formula_safe(self) -> None:
        self.assertEqual(WartungHandler.csv_cell(None, "=1+1"), "'=1+1")
        self.assertEqual(WartungHandler.csv_cell(None, "normal"), "normal")
        self.assertEqual(WartungHandler.csv_cell(None, None), "")


if __name__ == "__main__":
    unittest.main()
