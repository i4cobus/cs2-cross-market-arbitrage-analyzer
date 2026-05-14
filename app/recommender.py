from __future__ import annotations

import argparse
import csv
import os
import sys
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_INPUT_PATH = "data/opportunity_features.csv"
DEFAULT_OUTPUT_PATH = "data/recommendations.csv"

RECOMMENDATION_COLUMNS = [
    "rank",
    "market_hash_name",
    "base_name",
    "wear",
    "category",
    "recommendation_label",
    "opportunity_score",
    "instant_exit_margin_pct",
    "profit_margin_pct",
    "risk_score",
    "cs_liquidity_score",
    "demand_score",
    "uu_supply_score",
    "cs_highest_bid_usd",
    "uu_lowest_ask_usd",
    "cs_vol24h",
    "uu_listings",
    "recommendation_reason",
]


def _to_float(value: Any) -> Optional[float]:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def _fmt_money(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"${value:.2f}"


def load_feature_rows(input_path: str = DEFAULT_INPUT_PATH) -> List[Dict[str, Any]]:
    with open(input_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def explain_recommendation(row: Dict[str, Any]) -> str:
    label = row.get("recommendation_label", "")
    instant_exit = _to_float(row.get("instant_exit_margin_pct"))
    risk = _to_float(row.get("risk_score"))
    liquidity = _to_float(row.get("cs_liquidity_score"))
    demand = _to_float(row.get("demand_score"))
    supply = _to_float(row.get("uu_supply_score"))

    reasons = []

    if instant_exit is None:
        reasons.append("missing instant-exit margin")
    elif instant_exit < 0:
        reasons.append(f"negative instant-exit margin ({_fmt_pct(instant_exit)})")
    elif instant_exit >= 0.10:
        reasons.append(f"high instant-exit margin ({_fmt_pct(instant_exit)})")
    elif instant_exit >= 0.02:
        reasons.append(f"positive instant-exit margin ({_fmt_pct(instant_exit)})")
    else:
        reasons.append(f"thin instant-exit margin ({_fmt_pct(instant_exit)})")

    if liquidity is not None:
        if liquidity >= 0.65:
            reasons.append("strong CSFloat liquidity")
        elif liquidity < 0.35:
            reasons.append("weak CSFloat liquidity")

    if demand is not None:
        if demand >= 0.65:
            reasons.append("strong demand signal")
        elif demand < 0.35:
            reasons.append("weak demand signal")

    if supply is not None:
        if supply >= 0.65:
            reasons.append("healthy UU supply")
        elif supply < 0.35:
            reasons.append("limited UU supply")

    if risk is not None:
        if risk >= 0.55:
            reasons.append("elevated risk")
        elif risk <= 0.30:
            reasons.append("controlled risk")

    if label == "avoid":
        reasons.append("not recommended")
    elif label == "strong_candidate":
        reasons.append("recommended for priority review")
    elif label == "watchlist":
        reasons.append("worth monitoring")

    return "; ".join(reasons)


def _allowed_labels(min_label: str) -> set[str]:
    levels = ["avoid", "low_priority", "watchlist", "strong_candidate"]
    if min_label not in levels:
        raise ValueError(f"Unsupported min_label={min_label!r}. Choose one of {levels}")
    return set(levels[levels.index(min_label) :])


def rank_recommendations(
    rows: Iterable[Dict[str, Any]],
    min_label: str = "low_priority",
    include_avoid: bool = False,
) -> List[Dict[str, Any]]:
    allowed = _allowed_labels(min_label)
    if include_avoid:
        allowed.add("avoid")

    filtered = [
        dict(row)
        for row in rows
        if row.get("recommendation_label") in allowed
        and row.get("recommendation_label") != "insufficient_data"
    ]

    ranked = sorted(
        filtered,
        key=lambda row: (
            _to_float(row.get("opportunity_score")) or 0.0,
            _to_float(row.get("instant_exit_margin_pct")) or -999.0,
            _to_float(row.get("cs_liquidity_score")) or 0.0,
        ),
        reverse=True,
    )

    for index, row in enumerate(ranked, start=1):
        row["rank"] = index
        row["recommendation_reason"] = explain_recommendation(row)

    return ranked


def write_recommendations(
    rows: Iterable[Dict[str, Any]],
    output_path: str = DEFAULT_OUTPUT_PATH,
) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RECOMMENDATION_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _format_value(row.get(column)) for column in RECOMMENDATION_COLUMNS})


def build_recommendations(
    input_path: str = DEFAULT_INPUT_PATH,
    output_path: str = DEFAULT_OUTPUT_PATH,
    min_label: str = "low_priority",
    include_avoid: bool = False,
) -> List[Dict[str, Any]]:
    ranked = rank_recommendations(
        load_feature_rows(input_path),
        min_label=min_label,
        include_avoid=include_avoid,
    )
    write_recommendations(ranked, output_path=output_path)
    return ranked


def print_recommendations(rows: List[Dict[str, Any]], top: int) -> None:
    print("Top recommendations:")
    for row in rows[:top]:
        score = _to_float(row.get("opportunity_score"))
        instant_exit = _to_float(row.get("instant_exit_margin_pct"))
        risk = _to_float(row.get("risk_score"))
        uu_ask = _to_float(row.get("uu_lowest_ask_usd"))
        cs_bid = _to_float(row.get("cs_highest_bid_usd"))
        print(
            f"{int(row['rank']):>2}. {row.get('market_hash_name')} "
            f"score={score or 0:.3f} "
            f"instant_exit={_fmt_pct(instant_exit)} "
            f"risk={risk or 0:.3f} "
            f"buy={_fmt_money(uu_ask)} sell_bid={_fmt_money(cs_bid)} "
            f"label={row.get('recommendation_label')}"
        )
        print(f"    reason: {row.get('recommendation_reason')}")


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="recommender",
        description="Rank feature rows into explainable market opportunity recommendations.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH)
    parser.add_argument(
        "--min-label",
        choices=["avoid", "low_priority", "watchlist", "strong_candidate"],
        default="low_priority",
        help="Lowest recommendation tier to include in the output.",
    )
    parser.add_argument("--include-avoid", action="store_true")
    parser.add_argument("--top", type=int, default=10)
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = _parse_args(argv or sys.argv[1:])
    rows = build_recommendations(
        input_path=args.input,
        output_path=args.output,
        min_label=args.min_label,
        include_avoid=args.include_avoid,
    )
    print(f"Wrote {len(rows)} recommendations to {args.output}")
    print_recommendations(rows, top=args.top)


if __name__ == "__main__":
    main()
