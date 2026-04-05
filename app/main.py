# app/main.py
from __future__ import annotations

import os
import sys
import argparse
from typing import Optional

from dotenv import load_dotenv

from .config import require_config
from .csfloat_client import fetch_snapshot_by_params
from .logger import log_snapshot_both


def _parse_args(argv: list[str]) -> dict:
    p = argparse.ArgumentParser(
        prog="cs2-cross-market-arbitrage-analyzer",
        description="Fetch current CSFloat snapshot (lowest ask, highest bid, 24h sales).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    p.add_argument(
        "--snapshot",
        metavar="ITEM_NAME",
        help="Base item name (e.g., 'AK-47 | Redline' or 'Music Kit | Scarlxrd, King, Scar').",
    )
    p.add_argument(
        "--wear",
        choices=["fn", "mw", "ft", "ww", "bs"],
        help="Wear tier (skins/knives/gloves only). Omit for non-float items.",
    )
    p.add_argument(
        "--category",
        choices=["normal", "stattrak", "souvenir"],
        help="Item type. Omit for default/normal items.",
    )
    p.add_argument("--debug", action="store_true", help="Verbose debug output.")
    p.add_argument(
        "--probe",
        action="store_true",
        help="Print result without writing logs (for quick testing).",
    )

    args = vars(p.parse_args(argv))
    if not args.get("snapshot"):
        default_item = os.getenv("DEFAULT_ITEM")
        if default_item:
            args["snapshot"] = default_item
        else:
            p.error('You must pass --snapshot "Item Name" or set DEFAULT_ITEM in .env')
    return args


def _fmt_money(x: Optional[float]) -> str:
    if x is None:
        return "None"
    try:
        return f"${float(x):.2f}"
    except Exception:
        return "None"


def _print_snapshot(base_name: str, wear: Optional[str], category: Optional[str], snap: dict) -> None:
    cat_show = category if category else "any"
    wear_show = wear if wear else "any"
    source = snap.get("source", "n/a")

    print(f"Item: {base_name}")
    print(f"Wear: {wear_show}  Category: {cat_show}  Source: {source}")
    print(f"Lowest ask:  {_fmt_money(snap.get('lowest_ask'))}   (id: {snap.get('lowest_ask_id','')})")

    hb = snap.get("highest_bid")
    hb_qty = snap.get("highest_bid_qty")
    hb_txt = _fmt_money(hb)
    q_txt = f"  (qty: {hb_qty})" if hb_qty is not None else ""
    print(f"Highest bid: {hb_txt}{q_txt}")

    print(f"Vol 24h:     {snap.get('vol24h', 0)}")
    print(f"ASP 24h:     {_fmt_money(snap.get('asp24h'))}")

    if snap.get("is_floatable") is False:
        print("Note: This item type has no float/wear values.")


def main(argv: list[str] | None = None) -> None:
    # 1) Load environment and API key
    load_dotenv(override=False)
    try:
        require_config()
    except Exception:
        print("ERROR: Missing CSFLOAT_API_KEY in .env")
        sys.exit(2)

    # 2) Parse CLI args
    args = _parse_args(argv or sys.argv[1:])

    # 3) Fetch snapshot via friendly API
    snap = fetch_snapshot_by_params(
        base_name=args["snapshot"],
        wear_key=args.get("wear"),
        category_key=args.get("category"),
        debug=args.get("debug", False),
    )

    # 4) Print result
    _print_snapshot(args["snapshot"], args.get("wear"), args.get("category"), snap)

    # 5) Log result unless probing
    if not args.get("probe"):
        log_snapshot_both(
            name=args["snapshot"],
            wear=args.get("wear"),
            category=args.get("category"),
            snap=snap,
        )
        print("Wrote logs → logs/csfloat_snapshots.csv (append), logs/csfloat_snapshot_latest.csv (overwrite)")


if __name__ == "__main__":
    main()
