# app/csfloat_client.py
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, Iterator, Tuple

import httpx

from .config import CFG, require_config
from .wear import wear_bucket_range
from .market_name import build_market_hash_name
from .history import compute_sales_24h_metrics

API_BASE = "https://csfloat.com/api/v1"

# ---------------------------------------------
# Models
# ---------------------------------------------

@dataclass
class Listing:
    id: Optional[str]
    market_hash_name: str
    price_usd: float
    float_value: Optional[float] = None
    state: Optional[str] = None
    paint_seed: Optional[int] = None


# ---------------------------------------------
# Helpers
# ---------------------------------------------

def _headers() -> Dict[str, str]:
    require_config()
    return {"Authorization": CFG["CSFLOAT_API_KEY"]}

def _as_int(x, default=0) -> int:
    try:
        return int(x)
    except Exception:
        return default

def _as_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default

def _price_cents_from_row(row: dict) -> int:
    """
    Most CSFloat listing payloads have 'price' in cents at root.
    Be defensive with alternates.
    """
    for key in ("price", "usd_price_cents", "price_cents", "listed_price"):
        if key in row and isinstance(row[key], (int, float, str)):
            return _as_int(row[key], 0)
    return 0

_NON_FLOAT_KEYWORDS = {
    "music kit", "sticker", "patch", "agent", "graffiti",
    "case", "collectible", "pin", "key", "viewer pass", "souvenir package",
    "charm", "gift"
}

def _item_supports_float(name: str) -> bool:
    low = (name or "").lower()
    return not any(k in low for k in _NON_FLOAT_KEYWORDS)

def _extract_rows(payload) -> list[dict]:
    # API can return a list or a dict holding a list
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for k in ("listings", "results", "data", "items", "rows"):
            v = payload.get(k)
            if isinstance(v, list):
                return v
    return []

# ---------------------------------------------
# Listings
# ---------------------------------------------

def iter_listings(
    market_hash_name: Optional[str] = None,
    sort_by: str = "lowest_price",          # "lowest_price" | "highest_price" | "best_deal" | "most_recent"
    limit: int = 50,                         # API caps at 50
    extra_params: Optional[Dict[str, Any]] = None,
    max_pages: int = 5,
    backoff_s: float = 1.5,
    debug: bool = False,
) -> Iterator[dict]:
    """
    Streams paginated listings with robust parsing & optional debug logs.
    Yields raw listing dicts as returned by the API.
    """
    base_params: Dict[str, Any] = {
        "limit": min(int(limit or 50), 50),
        "sort_by": sort_by or "lowest_price",
    }
    if market_hash_name:
        base_params["market_hash_name"] = market_hash_name

    if extra_params:
        for k, v in extra_params.items():
            if v is None:
                continue
            if isinstance(v, str) and v.strip() == "":
                continue
            if isinstance(v, (list, tuple)) and len(v) == 0:
                continue
            base_params[k] = v

    cursor = None
    pages = 0

    with httpx.Client(timeout=20) as client:
        while True:
            request_params = dict(base_params)
            if cursor:
                request_params["cursor"] = cursor

            if debug:
                print("➡️  GET /listings", request_params)

            r = client.get(f"{API_BASE}/listings", headers=_headers(), params=request_params)

            if debug:
                print("⬅️  Status:", r.status_code, "X-Next-Cursor:", r.headers.get("X-Next-Cursor"))

            if r.status_code == 429:
                if debug:
                    print(f"⚠️  429 rate limited → sleeping {backoff_s}s…")
                time.sleep(backoff_s)
                continue

            if 500 <= r.status_code < 600:
                if debug:
                    print(f"⚠️  {r.status_code} server error → sleeping {backoff_s}s and retrying once…")
                time.sleep(backoff_s)
                r = client.get(f"{API_BASE}/listings", headers=_headers(), params=request_params)

            r.raise_for_status()

            try:
                payload = r.json()
            except Exception as e:
                if debug:
                    print("❌ JSON parse error:", e, "| text[:400]=", r.text[:400])
                return

            rows = _extract_rows(payload)
            if debug:
                shape = type(payload).__name__
                print(f"🧩 Payload shape={shape} | rows_found={len(rows)}")
                if not rows and isinstance(payload, dict):
                    print("   Available keys:", list(payload.keys()))

            if not rows:
                return

            for row in rows:
                yield row

            cursor = r.headers.get("X-Next-Cursor") or None
            pages += 1

            if debug:
                print("📄 Page", pages, "| next_cursor:", cursor)

            if not cursor or pages >= max_pages:
                return

def map_listing(row: dict) -> Listing:
    item = row.get("item", {}) or {}
    price_cents = _price_cents_from_row(row)

    fv = row.get("float_value")
    if fv is None:
        fv = item.get("float_value")

    paint_seed = row.get("paint_seed")
    if paint_seed is None:
        paint_seed = item.get("paint_seed")

    return Listing(
        id=str(row.get("id")) if row.get("id") is not None else None,
        market_hash_name=item.get("market_hash_name", "") or row.get("market_hash_name", ""),
        price_usd=_as_float(price_cents, 0) / 100.0,
        float_value=_as_float(fv, None) if fv is not None else None,
        state=row.get("state") or item.get("state"),
        paint_seed=_as_int(paint_seed, None) if paint_seed is not None else None,
    )

def _first_listing(
    name: str,
    sort_by: str,
    category: int | None,
    wear_bucket: tuple[float, float] | None,
) -> Listing | None:
    params: Dict[str, Any] = {}
    if category is not None:
        params["category"] = category              # 1 normal, 2 stattrak, 3 souvenir
    if wear_bucket:
        lo, hi = wear_bucket
        if lo is not None and hi is not None:
            params["min_float"], params["max_float"] = lo, hi

    for row in iter_listings(
        market_hash_name=name,
        sort_by=sort_by,
        limit=50,
        extra_params=params if params else None,
        max_pages=1,
    ):
        return map_listing(row)
    return None

# ---------------------------------------------
# Buy orders
# ---------------------------------------------

def fetch_buy_orders_for_listing(listing_id: str, limit: int = 10) -> list[dict]:
    r = httpx.get(
        f"{API_BASE}/listings/{listing_id}/buy-orders",
        headers=_headers(),
        params={"limit": limit},
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []

def highest_bid_from_orders(orders: list[dict]) -> Tuple[float, int] | None:
    """
    Returns (highest_bid_usd, qty_at_top) or None if empty. Prices are cents.
    """
    if not orders:
        return None
    clean = [o for o in orders if isinstance(o.get("price"), (int, float, str))]
    if not clean:
        return None
    cents = [_as_int(o.get("price")) for o in clean]
    top_cents = max(cents)
    qty_top = sum(_as_int(o.get("qty", 0)) for o in clean if _as_int(o.get("price")) == top_cents)
    return (top_cents / 100.0, qty_top)

# ---------------------------------------------
# Snapshots
# ---------------------------------------------

# Back-compat category mapping (int for API)
_CATEGORY_MAP = {"normal": 1, "stattrak": 2, "souvenir": 3}

def fetch_snapshot_by_params(
    base_name: str,
    wear_key: Optional[str] = None,              # "fn","mw","ft","ww","bs" or None
    category_key: Optional[str] = None,          # "normal","stattrak","souvenir" or None
    debug: bool = False,
) -> dict:
    """
    Build canonical name from friendly inputs and fetch a snapshot.
    If the first attempt yields no listing for non-floatables (e.g., Music Kits),
    we auto-try the alternate name variant (normal <-> stattrak) with relaxed category.
    """
    # 1) Primary attempt
    name_primary = build_market_hash_name(base_name, wear_key, category_key)
    cat_primary = _CATEGORY_MAP.get(category_key) if category_key else None
    wear_bucket = wear_bucket_range(wear_key) if (wear_key and _item_supports_float(name_primary)) else None

    snap = fetch_snapshot_metrics(
        name=name_primary,
        category=cat_primary,
        wear_bucket=wear_bucket,
        debug=debug,
    )

    # If we found something, return immediately
    if snap.get("lowest_ask", 0.0) > 0.0 or snap.get("vol24h", 0) > 0:
        return snap

    # 2) Alternate attempt (handles Music Kit / Sticker etc. name mismatch)
    # Only makes sense when switching stattrak <-> normal (souvenir not applicable to music kits/etc.)
    alt_category_key = None
    if category_key == "stattrak":
        alt_category_key = "normal"
    elif category_key == "normal":
        alt_category_key = "stattrak"

    # If there is a viable alternate
    if alt_category_key:
        name_alt = build_market_hash_name(base_name, wear_key, alt_category_key)
        # For the alternate attempt, relax category to None (most permissive)
        cat_alt = None
        wear_bucket_alt = wear_bucket if _item_supports_float(name_alt) else None

        if debug:
            print(f"⚙️  Primary name had no results. Trying alt name: {name_alt} (category=None)")

        snap_alt = fetch_snapshot_metrics(
            name=name_alt,
            category=cat_alt,
            wear_bucket=wear_bucket_alt,
            debug=debug,
        )

        # If alt found results, annotate and return
        if snap_alt.get("lowest_ask", 0.0) > 0.0 or snap_alt.get("vol24h", 0) > 0:
            # Optional: surface which name matched (useful for logs)
            snap_alt["used_name_variant"] = name_alt
            return snap_alt

    # Nothing found—return the primary (empty) result
    return snap

def fetch_snapshot_metrics(
    name: str,
    category: int | None = None,                        # 1=normal, 2=stattrak, 3=souvenir
    wear_bucket: tuple[float, float] | None = None,     # (min_float, max_float)
    debug: bool = False,
) -> dict:
    """
    Snapshot for one item (already-built market_hash_name):
      - lowest ask (by filters, with fallbacks)
      - highest bid (+ qty) via /listings/{id}/buy-orders
      - vol24h & asp24h via /history/<name>/sales (filtered client-side)
    """

    full_name = name

    # If item family doesn't support floats, never pass wear filters
    supports_float = _item_supports_float(name)
    requested_wear = wear_bucket
    if not supports_float:
        wear_bucket = None

    def try_first(sort_by: str, cat: int | None, wb: tuple[float, float] | None, label: str):
        lst = _first_listing(name, sort_by, cat, wb)
        return lst, label, cat, wb

    lowest = None
    source = "n/a"
    used_cat = None
    used_wear = None

    # 1) strict: name + cat + wear
    l, s, c_used, w_used = try_first("lowest_price", category, wear_bucket, "strict(name+cat+wear)")
    if l:
        lowest, source, used_cat, used_wear = l, s, c_used, w_used

    # 2) relax wear
    if not lowest and wear_bucket is not None:
        l, s, c_used, w_used = try_first("lowest_price", category, None, "no_wear(name+cat)")
        if l:
            lowest, source, used_cat, used_wear = l, s, c_used, w_used

    # 3) relax category
    if not lowest and category is not None:
        l, s, c_used, w_used = try_first("lowest_price", None, requested_wear if supports_float else None, "no_cat(name+wear)")
        if l:
            lowest, source, used_cat, used_wear = l, s, c_used, w_used

    # 4) name only
    if not lowest:
        l, s, c_used, w_used = try_first("lowest_price", None, None, "name_only")
        if l:
            lowest, source, used_cat, used_wear = l, s, c_used, w_used

    # Highest bid
    highest_bid = None
    highest_bid_qty = None
    if lowest and lowest.id:
        try:
            orders = fetch_buy_orders_for_listing(lowest.id, limit=10)
            hb = highest_bid_from_orders(orders)
            if hb:
                highest_bid, highest_bid_qty = hb
        except Exception:
            pass

    # Sales 24h (history): keep user's category intent; apply wear only if floatable
    history_wear = requested_wear if supports_float else None
    history_cat = category

    try:
        vol24h, asp24h = compute_sales_24h_metrics(
            name, history_wear, history_cat, lookback_hours=24, limit=400, debug=debug
        )
    except Exception:
        vol24h, asp24h = 0, 0.0

    return {
        "source": source,
        "market_hash_name": full_name,
        "lowest_ask": lowest.price_usd if lowest else 0.0,
        "lowest_ask_id": lowest.id if lowest else "",
        "highest_bid": highest_bid,
        "highest_bid_qty": highest_bid_qty,
        "vol24h": vol24h,
        "asp24h": asp24h,
        "used_category": used_cat,
        "used_wear": used_wear,
        "is_floatable": supports_float,
    }