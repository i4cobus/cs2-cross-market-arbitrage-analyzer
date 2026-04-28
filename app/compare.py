from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Optional


def _to_dict(obj: Any) -> Dict[str, Any]:
    """
    Convert a snapshot object (which can be dict, dataclass, or any object with __dict__) into a plain dict for comparison.
    """
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if is_dataclass(obj):
        return asdict(obj)
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)
    raise TypeError(f"Unsupported snapshot type: {type(obj)}")


def _to_float(x: Any) -> Optional[float]:
    if x in (None, "", "null"):
        return None
    try:
        return float(x)
    except Exception:
        return None


def _safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return a / b


def _normalize_name(name: Optional[str]) -> Optional[str]:
    """
    Normalize market_hash_name for better matching:
    - Strip leading/trailing whitespace
    - Replace multiple spaces with a single space
    """
    if not name:
        return None
    return " ".join(str(name).strip().split())


def compare_snapshots(
    cs_snapshot: Any,
    uu_snapshot: Any,
    cny_to_usd: float = 0.14,
) -> Dict[str, Any]:
    """
    Compare the market snapshots from CSFloat and UU for the same item, and return a unified dict with comparison results.

    
    CSFloat:
        market_hash_name
        lowest_ask
        highest_bid
        listings
        bid_depth
        vol24h
        asp24h
        currency = "USD"

    UU:
        market_hash_name
        lowest_ask
        highest_bid
        bid_reference
        listings
        bid_depth
        bid_depth_reference
        currency = "CNY"

    Return format:
        {
            "matched": bool,
            "reason": str | None,
            "market_hash_name": ...,

            "uu_lowest_ask_cny": ...,
            "uu_lowest_ask_usd": ...,
            "uu_highest_bid_cny": ...,
            "uu_highest_bid_usd": ...,

            "cs_lowest_ask_usd": ...,
            "cs_highest_bid_usd": ...,

            "spread_to_cs_lowest_usd": ...,
            "spread_to_cs_lowest_pct": ...,

            "spread_to_cs_bid_usd": ...,
            "spread_to_cs_bid_pct": ...,

            "uu_listings": ...,
            "uu_bid_reference": ...,
            "uu_bid_depth_reference": ...,

            "cs_listings": ...,
            "cs_bid_depth": ...,
            "cs_vol24h": ...,
            "cs_asp24h": ...,
        }
    """
    cs = _to_dict(cs_snapshot)
    uu = _to_dict(uu_snapshot)

    cs_name = _normalize_name(cs.get("market_hash_name"))
    uu_name = _normalize_name(uu.get("market_hash_name"))

    if not cs_name or not uu_name:
        return {
            "matched": False,
            "reason": "missing market_hash_name",
            "market_hash_name": None,
        }

    if cs_name != uu_name:
        return {
            "matched": False,
            "reason": "market_hash_name mismatch",
            "market_hash_name": None,
            "cs_market_hash_name": cs_name,
            "uu_market_hash_name": uu_name,
        }

    uu_lowest_ask_cny = _to_float(uu.get("lowest_ask"))
    uu_lowest_ask_usd = uu_lowest_ask_cny * cny_to_usd if uu_lowest_ask_cny is not None else None
    uu_highest_bid_cny = _to_float(uu.get("highest_bid"))
    uu_highest_bid_usd = uu_highest_bid_cny * cny_to_usd if uu_highest_bid_cny is not None else None

    cs_lowest_ask_usd = _to_float(cs.get("lowest_ask"))
    cs_highest_bid_usd = _to_float(cs.get("highest_bid"))

    # UU lowest ask vs CSFloat lowest ask
    spread_to_cs_lowest_usd = None
    spread_to_cs_lowest_pct = None
    if uu_lowest_ask_usd is not None and cs_lowest_ask_usd is not None:
        spread_to_cs_lowest_usd = cs_lowest_ask_usd - uu_lowest_ask_usd
        spread_to_cs_lowest_pct = _safe_div(spread_to_cs_lowest_usd, uu_lowest_ask_usd)

    # UU lowest ask vs CSFloat highest bid
    spread_to_cs_bid_usd = None
    spread_to_cs_bid_pct = None
    if uu_lowest_ask_usd is not None and cs_highest_bid_usd is not None:
        spread_to_cs_bid_usd = cs_highest_bid_usd - uu_lowest_ask_usd
        spread_to_cs_bid_pct = _safe_div(spread_to_cs_bid_usd, uu_lowest_ask_usd)

    return {
        "matched": True,
        "reason": None,
        "market_hash_name": cs_name,

        # UU
        "uu_lowest_ask_cny": uu_lowest_ask_cny,
        "uu_lowest_ask_usd": uu_lowest_ask_usd,
        "uu_highest_bid_cny": uu_highest_bid_cny,
        "uu_highest_bid_usd": uu_highest_bid_usd,
        "uu_listings": uu.get("listings"),
        "uu_bid_depth": uu.get("bid_depth"),
        "uu_bid_reference": _to_float(uu.get("bid_reference")),
        "uu_bid_depth_reference": uu.get("bid_depth_reference"),

        # CSFloat
        "cs_lowest_ask_usd": cs_lowest_ask_usd,
        "cs_highest_bid_usd": cs_highest_bid_usd,
        "cs_listings": cs.get("listings"),
        "cs_bid_depth": cs.get("bid_depth", cs.get("highest_bid_qty")),
        "cs_vol24h": cs.get("vol24h"),
        "cs_asp24h": _to_float(cs.get("asp24h")),

        # Results
        "spread_to_cs_lowest_usd": spread_to_cs_lowest_usd,
        "spread_to_cs_lowest_pct": spread_to_cs_lowest_pct,

        "spread_to_cs_bid_usd": spread_to_cs_bid_usd,
        "spread_to_cs_bid_pct": spread_to_cs_bid_pct,

        # Currency conversion
        "cny_to_usd": cny_to_usd,
    }


def pretty_print_comparison(result: Dict[str, Any]) -> None:
    if not result.get("matched"):
        print("matched              :", False)
        print("reason               :", result.get("reason"))
        if result.get("cs_market_hash_name"):
            print("cs_market_hash_name  :", result.get("cs_market_hash_name"))
        if result.get("uu_market_hash_name"):
            print("uu_market_hash_name  :", result.get("uu_market_hash_name"))
        return

    def fmt_money(x: Any, currency: str = "") -> str:
        if x is None:
            return "None"
        try:
            return f"{float(x):.4f} {currency}".strip()
        except Exception:
            return str(x)

    def fmt_pct(x: Any) -> str:
        if x is None:
            return "None"
        try:
            return f"{float(x) * 100:.2f}%"
        except Exception:
            return str(x)

    print("matched                  :", result.get("matched"))
    print("market_hash_name         :", result.get("market_hash_name"))

    print("\n[UU]")
    print("uu_lowest_ask_cny        :", fmt_money(result.get("uu_lowest_ask_cny"), "CNY"))
    print("uu_lowest_ask_usd        :", fmt_money(result.get("uu_lowest_ask_usd"), "USD"))
    print("uu_highest_bid_cny       :", fmt_money(result.get("uu_highest_bid_cny"), "CNY"))
    print("uu_highest_bid_usd       :", fmt_money(result.get("uu_highest_bid_usd"), "USD"))
    print("uu_listings              :", result.get("uu_listings"))
    print("uu_bid_depth             :", result.get("uu_bid_depth"))
    print("uu_bid_reference         :", fmt_money(result.get("uu_bid_reference"), "CNY"))
    print("uu_bid_depth_reference   :", result.get("uu_bid_depth_reference"))

    print("\n[CSFloat]")
    print("cs_lowest_ask_usd        :", fmt_money(result.get("cs_lowest_ask_usd"), "USD"))
    print("cs_highest_bid_usd       :", fmt_money(result.get("cs_highest_bid_usd"), "USD"))
    print("cs_listings              :", result.get("cs_listings"))
    print("cs_bid_depth             :", result.get("cs_bid_depth"))
    print("cs_vol24h                :", result.get("cs_vol24h"))
    print("cs_asp24h                :", fmt_money(result.get("cs_asp24h"), "USD"))

    print("\n[Comparison]")
    print("spread_to_cs_lowest_usd  :", fmt_money(result.get("spread_to_cs_lowest_usd"), "USD"))
    print("spread_to_cs_lowest_pct  :", fmt_pct(result.get("spread_to_cs_lowest_pct")))
    print("spread_to_cs_bid_usd     :", fmt_money(result.get("spread_to_cs_bid_usd"), "USD"))
    print("spread_to_cs_bid_pct     :", fmt_pct(result.get("spread_to_cs_bid_pct")))
    print("cny_to_usd               :", result.get("cny_to_usd"))
