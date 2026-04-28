from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_INPUT_PATH = "data/opportunity_snapshots.csv"
DEFAULT_OUTPUT_PATH = "data/opportunity_features.csv"

BASE_COLUMNS = [
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
    "spread_to_cs_lowest_pct",
    "spread_to_cs_bid_pct",
]

FEATURE_COLUMNS = [
    "profit_margin_pct",
    "instant_exit_margin_pct",
    "cs_liquidity_score",
    "uu_supply_score",
    "demand_score",
    "data_quality_score",
    "risk_score",
    "opportunity_score",
    "recommendation_label",
]

OUTPUT_COLUMNS = BASE_COLUMNS + FEATURE_COLUMNS


def _to_float(value: Any) -> Optional[float]:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _to_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _safe_div(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _log_score(value: Optional[float], scale: float) -> float:
    if value is None or value <= 0:
        return 0.0
    return _clamp(math.log1p(value) / math.log1p(scale))


def _profit_score(margin: Optional[float]) -> float:
    if margin is None:
        return 0.0
    # 10%+ is treated as excellent for a cross-market instant-exit signal.
    return _clamp(margin / 0.10)


def _quality_score(row: Dict[str, Any]) -> float:
    if row.get("data_quality_flag") != "ok":
        return 0.0
    if not _to_bool(row.get("matched")):
        return 0.0

    required_fields = (
        "cs_lowest_ask_usd",
        "cs_highest_bid_usd",
        "uu_lowest_ask_usd",
        "uu_highest_bid_usd",
    )
    present = sum(1 for field in required_fields if _to_float(row.get(field)) is not None)
    return present / len(required_fields)


def _risk_score(
    instant_exit_margin_pct: Optional[float],
    cs_liquidity_score: float,
    uu_supply_score: float,
    data_quality_score: float,
) -> float:
    risk = 0.0
    if instant_exit_margin_pct is None:
        risk += 0.35
    elif instant_exit_margin_pct < 0:
        risk += 0.40
    elif instant_exit_margin_pct < 0.02:
        risk += 0.15

    risk += (1.0 - cs_liquidity_score) * 0.25
    risk += (1.0 - uu_supply_score) * 0.20
    risk += (1.0 - data_quality_score) * 0.20
    return _clamp(risk)


def _recommendation_label(score: float, risk_score: float, instant_exit_margin_pct: Optional[float]) -> str:
    if instant_exit_margin_pct is None:
        return "insufficient_data"
    if instant_exit_margin_pct < 0:
        return "avoid"
    if score >= 0.70 and risk_score <= 0.35:
        return "strong_candidate"
    if score >= 0.50:
        return "watchlist"
    return "low_priority"


def add_business_indicators(row: Dict[str, Any]) -> Dict[str, Any]:
    uu_ask = _to_float(row.get("uu_lowest_ask_usd"))
    cs_ask = _to_float(row.get("cs_lowest_ask_usd"))
    cs_bid = _to_float(row.get("cs_highest_bid_usd"))

    profit_margin_pct = _safe_div((cs_ask - uu_ask) if cs_ask is not None and uu_ask is not None else None, uu_ask)
    instant_exit_margin_pct = _safe_div((cs_bid - uu_ask) if cs_bid is not None and uu_ask is not None else None, uu_ask)

    cs_vol24h = _to_float(row.get("cs_vol24h"))
    cs_bid_depth = _to_float(row.get("cs_bid_depth"))
    uu_listings = _to_float(row.get("uu_listings"))
    uu_bid_depth = _to_float(row.get("uu_bid_depth"))

    cs_liquidity_score = 0.65 * _log_score(cs_vol24h, 50) + 0.35 * _log_score(cs_bid_depth, 20)
    uu_supply_score = 0.70 * _log_score(uu_listings, 100) + 0.30 * _log_score(uu_bid_depth, 50)
    demand_score = 0.75 * _log_score(cs_vol24h, 50) + 0.25 * _log_score(uu_bid_depth, 50)
    data_quality_score = _quality_score(row)
    risk_score = _risk_score(
        instant_exit_margin_pct=instant_exit_margin_pct,
        cs_liquidity_score=cs_liquidity_score,
        uu_supply_score=uu_supply_score,
        data_quality_score=data_quality_score,
    )

    opportunity_score = _clamp(
        0.35 * _profit_score(instant_exit_margin_pct)
        + 0.25 * cs_liquidity_score
        + 0.20 * demand_score
        + 0.10 * uu_supply_score
        + 0.10 * data_quality_score
        - 0.20 * risk_score
    )

    enriched = dict(row)
    enriched.update(
        {
            "profit_margin_pct": profit_margin_pct,
            "instant_exit_margin_pct": instant_exit_margin_pct,
            "cs_liquidity_score": cs_liquidity_score,
            "uu_supply_score": uu_supply_score,
            "demand_score": demand_score,
            "data_quality_score": data_quality_score,
            "risk_score": risk_score,
            "opportunity_score": opportunity_score,
            "recommendation_label": _recommendation_label(
                opportunity_score,
                risk_score,
                instant_exit_margin_pct,
            ),
        }
    )
    return enriched


def load_rows(input_path: str = DEFAULT_INPUT_PATH) -> List[Dict[str, Any]]:
    with open(input_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def write_feature_rows(
    rows: Iterable[Dict[str, Any]],
    output_path: str = DEFAULT_OUTPUT_PATH,
) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _format_value(row.get(column)) for column in OUTPUT_COLUMNS})


def build_feature_dataset(
    input_path: str = DEFAULT_INPUT_PATH,
    output_path: str = DEFAULT_OUTPUT_PATH,
) -> List[Dict[str, Any]]:
    rows = [add_business_indicators(row) for row in load_rows(input_path)]
    write_feature_rows(rows, output_path)
    return rows


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="features",
        description="Compute business indicators and opportunity scores from market snapshots.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--top", type=int, default=10, help="Print top N opportunities after writing output.")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = _parse_args(argv or sys.argv[1:])
    rows = build_feature_dataset(input_path=args.input, output_path=args.output)
    ranked = sorted(rows, key=lambda row: _to_float(row.get("opportunity_score")) or 0.0, reverse=True)

    print(f"Wrote {len(rows)} rows to {args.output}")
    print("Top opportunities:")
    for index, row in enumerate(ranked[: args.top], start=1):
        score = _to_float(row.get("opportunity_score")) or 0.0
        margin = _to_float(row.get("instant_exit_margin_pct"))
        margin_text = "n/a" if margin is None else f"{margin * 100:.2f}%"
        print(
            f"{index:>2}. {row.get('market_hash_name')} "
            f"score={score:.3f} instant_exit={margin_text} "
            f"label={row.get('recommendation_label')}"
        )


if __name__ == "__main__":
    main()
