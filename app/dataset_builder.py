from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from dotenv import load_dotenv

from app.compare import compare_snapshots
from app.config import require_config
from app.csfloat_client import fetch_snapshot_by_params
from app.market_name import build_market_hash_name
from app.uu_client import search_and_get_exact_snapshot

DEFAULT_WATCHLIST_PATH = "data/watchlist.csv"
DEFAULT_OUTPUT_PATH = "data/opportunity_snapshots.csv"

OUTPUT_COLUMNS = [
    "timestamp",
    "base_name",
    "wear",
    "category",
    "uu_keyword",
    "market_hash_name",
    "matched",
    "data_quality_flag",
    "error",
    "cs_lowest_ask_usd",
    "cs_highest_bid_usd",
    "cs_bid_depth",
    "cs_vol24h",
    "cs_asp24h",
    "uu_lowest_ask_cny",
    "uu_lowest_ask_usd",
    "uu_highest_bid_cny",
    "uu_highest_bid_usd",
    "uu_bid_depth",
    "uu_listings",
    "uu_bid_reference",
    "uu_bid_depth_reference",
    "spread_to_cs_lowest_usd",
    "spread_to_cs_lowest_pct",
    "spread_to_cs_bid_usd",
    "spread_to_cs_bid_pct",
    "cny_to_usd",
]


@dataclass(frozen=True)
class WatchlistItem:
    base_name: str
    wear: Optional[str]
    category: Optional[str]
    uu_keyword: str


def _blank_to_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_float(value: Any) -> Optional[float]:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _fmt_float(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return ""
    return f"{number:.6f}"


def _fmt_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def load_watchlist(path: str = DEFAULT_WATCHLIST_PATH) -> List[WatchlistItem]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"base_name", "wear", "category", "uu_keyword"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Watchlist is missing columns: {sorted(missing)}")

        items = []
        for row_number, row in enumerate(reader, start=2):
            base_name = _blank_to_none(row.get("base_name"))
            uu_keyword = _blank_to_none(row.get("uu_keyword"))
            if not base_name or not uu_keyword:
                raise ValueError(f"Watchlist row {row_number} requires base_name and uu_keyword")

            items.append(
                WatchlistItem(
                    base_name=base_name,
                    wear=_blank_to_none(row.get("wear")),
                    category=_blank_to_none(row.get("category")),
                    uu_keyword=uu_keyword,
                )
            )

    return items


def _quality_flag(
    matched: bool,
    cs_snapshot: Optional[Dict[str, Any]],
    comparison: Optional[Dict[str, Any]],
    error: Optional[str],
) -> str:
    if error:
        return "error"
    if not matched:
        return "not_matched"
    if not cs_snapshot or _to_float(cs_snapshot.get("lowest_ask")) in (None, 0.0):
        return "missing_cs_ask"
    if not comparison or _to_float(comparison.get("uu_lowest_ask_cny")) in (None, 0.0):
        return "missing_uu_ask"
    if _to_float(comparison.get("uu_highest_bid_cny")) is None:
        return "missing_uu_bid"
    return "ok"


def build_opportunity_row(
    item: WatchlistItem,
    cny_to_usd: float,
    debug: bool = False,
) -> Dict[str, Any]:
    timestamp = int(time.time())
    market_hash_name = build_market_hash_name(item.base_name, item.wear, item.category)

    base_row: Dict[str, Any] = {
        "timestamp": timestamp,
        "base_name": item.base_name,
        "wear": item.wear or "",
        "category": item.category or "",
        "uu_keyword": item.uu_keyword,
        "market_hash_name": market_hash_name,
        "matched": False,
        "data_quality_flag": "not_run",
        "error": "",
    }

    cs_snapshot: Optional[Dict[str, Any]] = None
    comparison: Optional[Dict[str, Any]] = None
    error = None

    try:
        cs_snapshot = fetch_snapshot_by_params(
            base_name=item.base_name,
            wear_key=item.wear,
            category_key=item.category,
            debug=debug,
        )
        uu_snapshot = search_and_get_exact_snapshot(
            keyword=item.uu_keyword,
            market_hash_name=market_hash_name,
            debug=debug,
        )
        comparison = compare_snapshots(cs_snapshot, uu_snapshot, cny_to_usd=cny_to_usd)
    except Exception as exc:
        error = repr(exc)

    matched = bool(comparison and comparison.get("matched"))
    base_row["matched"] = matched
    base_row["error"] = error or (comparison.get("reason") if comparison and not matched else "")
    base_row["data_quality_flag"] = _quality_flag(matched, cs_snapshot, comparison, error)

    if cs_snapshot:
        base_row.update(
            {
                "cs_lowest_ask_usd": cs_snapshot.get("lowest_ask"),
                "cs_highest_bid_usd": cs_snapshot.get("highest_bid"),
                "cs_bid_depth": cs_snapshot.get("bid_depth", cs_snapshot.get("highest_bid_qty")),
                "cs_vol24h": cs_snapshot.get("vol24h"),
                "cs_asp24h": cs_snapshot.get("asp24h"),
            }
        )

    if comparison:
        base_row.update(comparison)

    return base_row


def _serialise_row(row: Dict[str, Any]) -> Dict[str, str]:
    serialised = {}
    for column in OUTPUT_COLUMNS:
        value = row.get(column)
        if isinstance(value, float):
            serialised[column] = _fmt_float(value)
        else:
            serialised[column] = _fmt_value(value)
    return serialised


def write_dataset(
    rows: Iterable[Dict[str, Any]],
    output_path: str = DEFAULT_OUTPUT_PATH,
    append: bool = True,
) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    file_exists = os.path.exists(output_path) and os.path.getsize(output_path) > 0
    mode = "a" if append else "w"

    with open(output_path, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        if not append or not file_exists:
            writer.writeheader()
        for row in rows:
            writer.writerow(_serialise_row(row))


def build_dataset(
    watchlist_path: str = DEFAULT_WATCHLIST_PATH,
    output_path: str = DEFAULT_OUTPUT_PATH,
    cny_to_usd: float = 0.14,
    append: bool = True,
    debug: bool = False,
) -> List[Dict[str, Any]]:
    items = load_watchlist(watchlist_path)
    rows = []

    for index, item in enumerate(items, start=1):
        print(f"[{index}/{len(items)}] {item.base_name} wear={item.wear or '-'} category={item.category or '-'}")
        rows.append(build_opportunity_row(item, cny_to_usd=cny_to_usd, debug=debug))

    write_dataset(rows, output_path=output_path, append=append)
    return rows


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dataset-builder",
        description="Build a structured cross-market opportunity dataset from a watchlist.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--watchlist", default=DEFAULT_WATCHLIST_PATH)
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--cny-to-usd", type=float, default=float(os.getenv("CNY_USD", "0.14")))
    parser.add_argument("--overwrite", action="store_true", help="Overwrite output instead of appending.")
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    load_dotenv(override=False)
    args = _parse_args(argv or sys.argv[1:])

    try:
        require_config()
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(2)

    rows = build_dataset(
        watchlist_path=args.watchlist,
        output_path=args.output,
        cny_to_usd=args.cny_to_usd,
        append=not args.overwrite,
        debug=args.debug,
    )

    ok_count = sum(1 for row in rows if row.get("data_quality_flag") == "ok")
    print(f"Wrote {len(rows)} rows to {args.output}. ok={ok_count}, non_ok={len(rows) - ok_count}")


if __name__ == "__main__":
    main()
