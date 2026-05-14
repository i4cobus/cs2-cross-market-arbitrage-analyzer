from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from app.dataset_builder import load_watchlist


class DatasetBuilderTests(unittest.TestCase):
    def test_load_watchlist_handles_quoted_commas(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "watchlist.csv"
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["base_name", "wear", "category", "uu_keyword"])
                writer.writerow(["Music Kit | Skog, Metal", "", "normal", "Skog"])

            items = load_watchlist(str(path))

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].base_name, "Music Kit | Skog, Metal")
        self.assertIsNone(items[0].wear)
        self.assertEqual(items[0].category, "normal")
        self.assertEqual(items[0].uu_keyword, "Skog")

    def test_load_watchlist_requires_base_name_and_keyword(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "watchlist.csv"
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["base_name", "wear", "category", "uu_keyword"])
                writer.writerow(["", "ft", "normal", "夜行衣"])

            with self.assertRaises(ValueError):
                load_watchlist(str(path))


if __name__ == "__main__":
    unittest.main()
