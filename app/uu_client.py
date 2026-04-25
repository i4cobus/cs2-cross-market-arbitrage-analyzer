from __future__ import annotations

import os
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, List

import httpx
from dotenv import load_dotenv

load_dotenv()

UU_API_BASE = "https://api.youpin898.com"


class UUClientError(RuntimeError):
    pass


@dataclass
class PurchaseOrderSummary:
    highest_bid: Optional[float]
    bid_depth: Optional[int]
    total_orders: Optional[int]


@dataclass
class MarketSnapshot:
    source: str

    # Core keyword
    market_hash_name: Optional[str]

    # Trustworthy keyword 
    lowest_ask: Optional[float]

    
    highest_bid: Optional[float]

    
    listings: Optional[int]
    bid_depth: Optional[int]

    
    vol24h: Optional[int] = None
    asp24h: Optional[float] = None

    currency: str = "CNY"

    # UU Reference price (may be same as highest_bid, or may be None if not available)
    bid_reference: Optional[float] = None
    bid_depth_reference: Optional[int] = None

    # Meta info from UU, for debugging and future use
    source_id: Optional[str] = None          # template_id
    commodity_name_cn: Optional[str] = None
    weapon_hash_name: Optional[str] = None
    type_name_cn: Optional[str] = None
    exterior_name_cn: Optional[str] = None

    steam_price_cny: Optional[float] = None
    steam_price_usd: Optional[float] = None

    ts: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _get_env_required(key: str) -> str:
    value = os.getenv(key, "").strip()
    if not value:
        raise UUClientError(f"Missing required env var: {key}")
    return value


def _to_float(x: Any) -> Optional[float]:
    if x in (None, "", "null"):
        return None
    try:
        return float(x)
    except Exception:
        return None


def _to_int(x: Any) -> Optional[int]:
    if x in (None, "", "null"):
        return None
    try:
        return int(x)
    except Exception:
        return None


def _normalize_market_hash_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    return " ".join(str(name).strip().split())


def _headers() -> Dict[str, str]:
    authorization = _get_env_required("UU_AUTHORIZATION")
    device_id = _get_env_required("UU_DEVICE_ID")
    device_uk = _get_env_required("UU_DEVICE_UK")
    uk = _get_env_required("UU_UK")

    app_version = os.getenv("UU_APP_VERSION", "5.26.0").strip()
    secret_v = os.getenv("UU_SECRET_V", "h5_v1").strip()
    cookie = os.getenv("UU_COOKIE", "").strip()

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Authorization": authorization,
        "DeviceId": device_id,
        "DeviceUk": device_uk,
        "Uk": uk,
        "Origin": "https://www.youpin898.com",
        "Referer": "https://www.youpin898.com/",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/146.0.0.0 Safari/537.36"
        ),
        "App-Version": app_version,
        "AppType": "1",
        "AppVersion": app_version,
        "Platform": "pc",
        "Secret-V": secret_v,
    }

    if cookie:
        headers["Cookie"] = cookie

    return headers


def _post(path: str, payload: Dict[str, Any], timeout: int = 20, debug: bool = False) -> Dict[str, Any]:
    url = f"{UU_API_BASE}{path}"

    if debug:
        print("POST", url)
        print("payload =", payload)

    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, headers=_headers(), json=payload)

    if debug:
        print("status =", resp.status_code)
        print("text[:800] =", resp.text[:800])

    resp.raise_for_status()

    data = resp.json()
    if not isinstance(data, dict):
        raise UUClientError(f"Unexpected response type: {type(data)}")

    code = data.get("Code", data.get("code"))
    if code not in (0, "0", None):
        msg = data.get("Msg", data.get("msg"))
        raise UUClientError(f"UU API returned error: Code={code}, Msg={msg}")

    return data


def search_templates(
    keyword: str,
    list_type: str = "10",
    debug: bool = False,
) -> List[Dict[str, Any]]:
    """
    Keyword search for templates on UU, returns a list of candidates with basic info.
    [
        {
            "template_id": "51135",
            "commodity_name_cn": "...",
        },
        ...
    ]
    """
    payload = {
        "keyWords": keyword,
        "listType": str(list_type),
    }

    data = _post(
        "/api/homepage/pc/goods/market/lenovoSearch",
        payload,
        debug=debug,
    )

    raw_items = data.get("Data") or []
    results: List[Dict[str, Any]] = []

    for item in raw_items:
        template_id = item.get("templateId")
        commodity_name_cn = item.get("commodityName")
        if template_id is None:
            continue

        results.append(
            {
                "template_id": str(template_id),
                "commodity_name_cn": commodity_name_cn,
            }
        )

    return results


def get_template_detail(
    template_id: str,
    game_id: str = "730",
    list_type: str = "10",
    debug: bool = False,
) -> Dict[str, Any]:
    payload = {
        "gameId": str(game_id),
        "listType": str(list_type),
        "templateId": str(template_id),
    }

    return _post(
        "/api/homepage/pc/goods/market/queryTemplateDetail",
        payload,
        debug=debug,
    )


def get_template_purchase_orders(
    template_id: str,
    page_index: int = 1,
    page_size: int = 20,
    debug: bool = False,
) -> Dict[str, Any]:
    """
    Fetch UU purchase orders for a template.

    This endpoint exposes current buy orders, not historical trade volume.
    """
    payload = {
        "templateId": str(template_id),
        "pageIndex": int(page_index),
        "pageSize": int(page_size),
    }

    return _post(
        "/api/youpin/bff/trade/purchase/order/getTemplatePurchaseOrderListPC",
        payload,
        debug=debug,
    )


def parse_purchase_order_summary(orders_response: Dict[str, Any]) -> PurchaseOrderSummary:
    data = orders_response.get("data") or orders_response.get("Data") or {}
    orders = data.get("purchaseOrderResponseList") or []
    total_orders = _to_int(data.get("total"))

    highest_bid = None
    bid_depth = 0

    for order in orders:
        price = _to_float(order.get("purchasePrice"))
        if price is None:
            continue

        quantity = _to_int(order.get("surplusQuantity")) or 0
        if highest_bid is None or price > highest_bid:
            highest_bid = price
            bid_depth = quantity
        elif price == highest_bid:
            bid_depth += quantity

    return PurchaseOrderSummary(
        highest_bid=highest_bid,
        bid_depth=bid_depth if highest_bid is not None else None,
        total_orders=total_orders,
    )


def get_purchase_order_summary(
    template_id: str,
    debug: bool = False,
    max_pages: int = 3,
    page_size: int = 20,
) -> PurchaseOrderSummary:
    all_orders: List[Dict[str, Any]] = []
    total_orders = None

    for page_index in range(1, max_pages + 1):
        raw = get_template_purchase_orders(
            template_id=template_id,
            page_index=page_index,
            page_size=page_size,
            debug=debug,
        )
        data = raw.get("data") or raw.get("Data") or {}
        page_orders = data.get("purchaseOrderResponseList") or []
        all_orders.extend(page_orders)

        if total_orders is None:
            total_orders = _to_int(data.get("total"))

        if not data.get("hasNext"):
            break

    return parse_purchase_order_summary(
        {
            "data": {
                "total": total_orders,
                "purchaseOrderResponseList": all_orders,
            }
        }
    )


def parse_template_detail(detail: Dict[str, Any]) -> MarketSnapshot:
    """
    Parse the raw template detail response from UU into a MarketSnapshot.
    """
    data = detail.get("Data") or {}
    info = data.get("templateInfo") or {}

    market_hash_name = info.get("commodityHashName")
    commodity_name_cn = info.get("commodityName")
    weapon_hash_name = info.get("weaponHashName")
    type_name_cn = info.get("typeName")
    exterior_name_cn = info.get("exteriorName")

    template_id = str(info.get("id")) if info.get("id") is not None else None

    steam_price_cny = _to_float(info.get("steamPrice"))
    steam_price_usd = _to_float(info.get("steamUSDPrice"))

    listings = _to_int(info.get("sellNumber"))
    purchase_number = _to_int(info.get("purchaseNumber"))

    lowest_ask = None
    bid_reference = None

    filters = data.get("filters") or []
    for f in filters:
        if f.get("FilterKey") == "Exterior":
            items = f.get("Items") or []
            selected = None
            for item in items:
                if item.get("IsSelected") is True:
                    selected = item
                    break

            if selected:
                lowest_ask = _to_float(selected.get("SellPrice"))
                bid_reference = _to_float(selected.get("PurchaseMaxPrice"))
            break

    return MarketSnapshot(
        source="uu",

        market_hash_name=market_hash_name,

        
        lowest_ask=lowest_ask,
        highest_bid=None,

        listings=listings,
        bid_depth=None,

        vol24h=None,
        asp24h=None,

        currency="CNY",

        
        bid_reference=bid_reference,
        bid_depth_reference=purchase_number,

        source_id=template_id,
        commodity_name_cn=commodity_name_cn,
        weapon_hash_name=weapon_hash_name,
        type_name_cn=type_name_cn,
        exterior_name_cn=exterior_name_cn,

        steam_price_cny=steam_price_cny,
        steam_price_usd=steam_price_usd,

        ts=int(time.time()),
    )


def enrich_snapshot_with_purchase_orders(
    snapshot: MarketSnapshot,
    template_id: str,
    debug: bool = False,
) -> MarketSnapshot:
    try:
        purchase_summary = get_purchase_order_summary(template_id=template_id, debug=debug)
        snapshot.highest_bid = purchase_summary.highest_bid
        snapshot.bid_depth = purchase_summary.bid_depth
        snapshot.bid_depth_reference = purchase_summary.total_orders or snapshot.bid_depth_reference
    except Exception as e:
        if debug:
            print("Failed to fetch UU purchase orders:", repr(e))

    return snapshot


def get_template_snapshot(
    template_id: str,
    debug: bool = False,
    include_purchase_orders: bool = True,
) -> MarketSnapshot:
    raw = get_template_detail(template_id=template_id, debug=debug)
    snapshot = parse_template_detail(raw)

    if include_purchase_orders:
        enrich_snapshot_with_purchase_orders(snapshot, template_id=template_id, debug=debug)

    return snapshot


def search_and_get_exact_snapshot(
    keyword: str,
    market_hash_name: str,
    debug: bool = False,
) -> MarketSnapshot:
    """
    Search UU by keyword, then return the candidate whose template detail has the exact
    Steam/CS market_hash_name.

    lenovoSearch is only a fuzzy candidate list. Do not trust its order for matching
    StatTrak/Souvenir/wear variants; fetch template detail and compare commodityHashName.
    """
    expected_name = _normalize_market_hash_name(market_hash_name)
    if not expected_name:
        raise UUClientError("market_hash_name is required for exact UU template matching")

    candidates = search_templates(keyword=keyword, debug=debug)
    if not candidates:
        raise UUClientError(f"No templates found for keyword: {keyword}")

    checked: List[str] = []
    for candidate in candidates:
        snapshot = get_template_snapshot(
            template_id=candidate["template_id"],
            debug=debug,
            include_purchase_orders=False,
        )
        candidate_name = _normalize_market_hash_name(snapshot.market_hash_name)
        if candidate_name:
            checked.append(f"{candidate['template_id']}: {candidate_name}")

        if candidate_name == expected_name:
            return enrich_snapshot_with_purchase_orders(
                snapshot,
                template_id=candidate["template_id"],
                debug=debug,
            )

    checked_text = "; ".join(checked[:10])
    if len(checked) > 10:
        checked_text += f"; ... total={len(checked)}"

    raise UUClientError(
        "No exact UU template match found "
        f"for keyword={keyword!r}, market_hash_name={expected_name!r}. "
        f"Checked: {checked_text}"
    )


def search_and_get_snapshot(keyword: str, index: int = 0, debug: bool = False) -> MarketSnapshot:
    """
    Convenience function: search by keyword and directly get the snapshot of the selected candidate.
    """
    candidates = search_templates(keyword=keyword, debug=debug)
    if not candidates:
        raise UUClientError(f"No templates found for keyword: {keyword}")

    if index < 0 or index >= len(candidates):
        raise UUClientError(f"Index out of range: {index}, total={len(candidates)}")

    template_id = candidates[index]["template_id"]
    return get_template_snapshot(template_id=template_id, debug=debug)


def pretty_print_snapshot(snapshot: MarketSnapshot) -> None:
    print("source             :", snapshot.source)
    print("source_id          :", snapshot.source_id)
    print("market_hash_name   :", snapshot.market_hash_name)
    print("commodity_name_cn  :", snapshot.commodity_name_cn)
    print("type_name_cn       :", snapshot.type_name_cn)
    print("exterior_name_cn   :", snapshot.exterior_name_cn)
    print("lowest_ask         :", snapshot.lowest_ask, snapshot.currency)
    print("highest_bid        :", snapshot.highest_bid, snapshot.currency)
    print("bid_reference      :", snapshot.bid_reference, snapshot.currency)
    print("listings           :", snapshot.listings)
    print("bid_depth          :", snapshot.bid_depth)
    print("bid_depth_reference:", snapshot.bid_depth_reference)
    print("steam_price_cny    :", snapshot.steam_price_cny)
    print("steam_price_usd    :", snapshot.steam_price_usd)
    print("ts                 :", snapshot.ts)
