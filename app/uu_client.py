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

    code = data.get("Code")
    if code not in (0, "0", None):
        raise UUClientError(f"UU API returned error: Code={code}, Msg={data.get('Msg')}")

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


def get_template_snapshot(template_id: str, debug: bool = False) -> MarketSnapshot:
    raw = get_template_detail(template_id=template_id, debug=debug)
    return parse_template_detail(raw)


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