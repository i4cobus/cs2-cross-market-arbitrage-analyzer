from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_FEATURES_PATH = "data/opportunity_features.csv"
DEFAULT_RECOMMENDATIONS_PATH = "data/recommendations.csv"
DEFAULT_QUERY_PATH = "sql/top_opportunities.sql"

TABLE_SOURCES = {
    "features": DEFAULT_FEATURES_PATH,
    "recommendations": DEFAULT_RECOMMENDATIONS_PATH,
}


def _to_number(value: Any) -> Any:
    if value in (None, "", "null"):
        return None
    text = str(value).strip()
    if text.lower() in {"true", "false"}:
        return 1 if text.lower() == "true" else 0
    try:
        if "." not in text:
            return int(text)
        return float(text)
    except ValueError:
        return value


def _sqlite_type(values: Iterable[Any]) -> str:
    has_float = False
    for value in values:
        converted = _to_number(value)
        if converted is None:
            continue
        if isinstance(converted, int):
            continue
        if isinstance(converted, float):
            has_float = True
            continue
        return "TEXT"
    return "REAL" if has_float else "INTEGER"


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def load_csv_table(conn: sqlite3.Connection, table_name: str, csv_path: str) -> int:
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return 0

    columns = list(rows[0].keys())
    column_defs = []
    for column in columns:
        column_defs.append(
            f"{_quote_identifier(column)} {_sqlite_type(row.get(column) for row in rows)}"
        )

    conn.execute(f"DROP TABLE IF EXISTS {_quote_identifier(table_name)}")
    conn.execute(f"CREATE TABLE {_quote_identifier(table_name)} ({', '.join(column_defs)})")

    placeholders = ", ".join(["?"] * len(columns))
    insert_sql = (
        f"INSERT INTO {_quote_identifier(table_name)} "
        f"({', '.join(_quote_identifier(column) for column in columns)}) VALUES ({placeholders})"
    )
    values = [[_to_number(row.get(column)) for column in columns] for row in rows]
    conn.executemany(insert_sql, values)
    conn.commit()
    return len(rows)


def build_connection(table_sources: Optional[Dict[str, str]] = None) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    for table_name, csv_path in (table_sources or TABLE_SOURCES).items():
        if os.path.exists(csv_path):
            load_csv_table(conn, table_name, csv_path)

    return conn


def run_query(conn: sqlite3.Connection, sql: str) -> List[Dict[str, Any]]:
    cursor = conn.execute(sql)
    columns = [description[0] for description in cursor.description or []]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def run_query_file(
    query_path: str = DEFAULT_QUERY_PATH,
    table_sources: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    conn = build_connection(table_sources)
    try:
        sql = Path(query_path).read_text(encoding="utf-8")
        return run_query(conn, sql)
    finally:
        conn.close()


def print_rows(rows: List[Dict[str, Any]], limit: int = 20) -> None:
    if not rows:
        print("No rows returned.")
        return

    columns = list(rows[0].keys())
    sample = rows[:limit]
    widths = {
        column: min(
            max(len(column), *(len(str(row.get(column, ""))) for row in sample)),
            36,
        )
        for column in columns
    }

    def fmt(value: Any, width: int) -> str:
        text = "" if value is None else str(value)
        if len(text) > width:
            text = text[: width - 1] + "…"
        return text.ljust(width)

    print(" | ".join(fmt(column, widths[column]) for column in columns))
    print("-+-".join("-" * widths[column] for column in columns))
    for row in sample:
        print(" | ".join(fmt(row.get(column), widths[column]) for column in columns))

    if len(rows) > limit:
        print(f"... {len(rows) - limit} more rows")


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="analytics",
        description="Run SQL analytics over generated opportunity datasets.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--query", default=DEFAULT_QUERY_PATH)
    parser.add_argument("--features", default=DEFAULT_FEATURES_PATH)
    parser.add_argument("--recommendations", default=DEFAULT_RECOMMENDATIONS_PATH)
    parser.add_argument("--limit", type=int, default=20)
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = _parse_args(argv or sys.argv[1:])
    rows = run_query_file(
        query_path=args.query,
        table_sources={
            "features": args.features,
            "recommendations": args.recommendations,
        },
    )
    print_rows(rows, limit=args.limit)


if __name__ == "__main__":
    main()
