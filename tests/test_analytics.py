from __future__ import annotations

import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.analytics import build_connection, load_csv_table, run_query, run_query_file


class AnalyticsTests(unittest.TestCase):
    def test_load_csv_table_infers_numeric_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "features.csv"
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["market_hash_name", "opportunity_score"])
                writer.writeheader()
                writer.writerow({"market_hash_name": "A", "opportunity_score": "0.75"})

            conn = sqlite3.connect(":memory:")
            try:
                count = load_csv_table(conn, "features", str(path))
                rows = run_query(conn, "SELECT market_hash_name, opportunity_score FROM features")
            finally:
                conn.close()

        self.assertEqual(count, 1)
        self.assertEqual(rows[0]["market_hash_name"], "A")
        self.assertEqual(rows[0]["opportunity_score"], 0.75)

    def test_build_connection_loads_multiple_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            features_path = Path(tmpdir) / "features.csv"
            recs_path = Path(tmpdir) / "recommendations.csv"
            for path, table_name in ((features_path, "features"), (recs_path, "recommendations")):
                with path.open("w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=["market_hash_name", "source_table"])
                    writer.writeheader()
                    writer.writerow({"market_hash_name": "A", "source_table": table_name})

            conn = build_connection(
                {
                    "features": str(features_path),
                    "recommendations": str(recs_path),
                }
            )
            try:
                rows = run_query(
                    conn,
                    "SELECT COUNT(*) AS n FROM features UNION ALL SELECT COUNT(*) AS n FROM recommendations",
                )
            finally:
                conn.close()

        self.assertEqual([row["n"] for row in rows], [1, 1])

    def test_run_query_file_returns_dict_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            features_path = Path(tmpdir) / "features.csv"
            query_path = Path(tmpdir) / "query.sql"
            with features_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["market_hash_name", "opportunity_score"])
                writer.writeheader()
                writer.writerow({"market_hash_name": "A", "opportunity_score": "0.75"})
            query_path.write_text(
                "SELECT market_hash_name FROM features WHERE opportunity_score > 0.5",
                encoding="utf-8",
            )

            rows = run_query_file(
                str(query_path),
                table_sources={"features": str(features_path)},
            )

        self.assertEqual(rows, [{"market_hash_name": "A"}])


if __name__ == "__main__":
    unittest.main()
