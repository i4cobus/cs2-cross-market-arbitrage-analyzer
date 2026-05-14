from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.analytics import (
    DEFAULT_FEATURES_PATH,
    DEFAULT_RECOMMENDATIONS_PATH,
    run_query_file,
)


@dataclass(frozen=True)
class AnalystIntent:
    name: str
    query_path: str
    description: str


INTENTS = {
    "top_opportunities": AnalystIntent(
        name="top_opportunities",
        query_path="sql/top_opportunities.sql",
        description="Ranked strong candidates and watchlist opportunities.",
    ),
    "data_quality": AnalystIntent(
        name="data_quality",
        query_path="sql/data_quality_report.sql",
        description="Dataset match rate, completeness, and missing-field checks.",
    ),
    "label_distribution": AnalystIntent(
        name="label_distribution",
        query_path="sql/label_distribution.sql",
        description="Distribution of recommendation labels and aggregate scores.",
    ),
    "liquidity": AnalystIntent(
        name="liquidity",
        query_path="sql/liquidity_analysis.sql",
        description="Liquidity-focused opportunity analysis.",
    ),
}


def classify_intent(question: str) -> AnalystIntent:
    text = question.lower()

    if any(keyword in text for keyword in ("quality", "missing", "complete", "matched", "valid")):
        return INTENTS["data_quality"]
    if any(keyword in text for keyword in ("distribution", "label", "count", "how many")):
        return INTENTS["label_distribution"]
    if any(keyword in text for keyword in ("liquidity", "volume", "depth", "demand", "supply")):
        return INTENTS["liquidity"]
    if any(keyword in text for keyword in ("top", "best", "recommend", "candidate", "opportunit", "profit")):
        return INTENTS["top_opportunities"]

    return INTENTS["top_opportunities"]


def _to_float(value: Any) -> Optional[float]:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _fmt_pct(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "n/a"
    return f"{number:.2f}%"


def _fmt_score(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "n/a"
    return f"{number:.3f}"


def summarize_rows(intent: AnalystIntent, rows: List[Dict[str, Any]], limit: int = 5) -> str:
    if not rows:
        return "No matching rows were returned for this question."

    if intent.name == "data_quality":
        row = rows[0]
        return (
            "Dataset quality summary: "
            f"{row.get('total_rows')} rows, "
            f"{row.get('match_rate_pct')}% match rate, "
            f"{row.get('ok_rate_pct')}% OK rows, "
            f"{row.get('missing_uu_ask_rows')} missing UU asks, "
            f"{row.get('missing_uu_bid_rows')} missing UU bids, "
            f"{row.get('missing_cs_bid_rows')} missing CS bids, and "
            f"{row.get('negative_exit_margin_rows')} rows with negative instant-exit margin."
        )

    if intent.name == "label_distribution":
        parts = []
        for row in rows:
            parts.append(
                f"{row.get('recommendation_label')}: {row.get('row_count')} rows "
                f"(avg score {_fmt_score(row.get('avg_opportunity_score'))}, "
                f"avg exit {_fmt_pct(row.get('avg_instant_exit_margin_pct'))})"
            )
        return "Recommendation label distribution: " + "; ".join(parts) + "."

    if intent.name == "liquidity":
        top = rows[:limit]
        lines = ["Liquidity summary:"]
        for index, row in enumerate(top, start=1):
            lines.append(
                f"{index}. {row.get('market_hash_name')} has liquidity score "
                f"{_fmt_score(row.get('cs_liquidity_score'))}, CS 24h volume "
                f"{row.get('cs_vol24h')}, UU listings {row.get('uu_listings')}, "
                f"and instant-exit margin {_fmt_pct(row.get('instant_exit_margin_pct'))}."
            )
        return "\n".join(lines)

    top = rows[:limit]
    lines = ["Top opportunity summary:"]
    for row in top:
        lines.append(
            f"{row.get('rank')}. {row.get('market_hash_name')} is labeled "
            f"{row.get('recommendation_label')} with score "
            f"{_fmt_score(row.get('opportunity_score'))}, instant-exit margin "
            f"{_fmt_pct(row.get('instant_exit_margin_pct'))}, and risk "
            f"{_fmt_score(row.get('risk_score'))}."
        )
    return "\n".join(lines)


def answer_question(
    question: str,
    features_path: str = DEFAULT_FEATURES_PATH,
    recommendations_path: str = DEFAULT_RECOMMENDATIONS_PATH,
    limit: int = 5,
) -> Dict[str, Any]:
    intent = classify_intent(question)
    rows = run_query_file(
        query_path=intent.query_path,
        table_sources={
            "features": features_path,
            "recommendations": recommendations_path,
        },
    )
    return {
        "question": question,
        "intent": intent.name,
        "description": intent.description,
        "sql_file": intent.query_path,
        "summary": summarize_rows(intent, rows, limit=limit),
        "rows": rows[:limit],
        "row_count": len(rows),
    }


def _print_answer(answer: Dict[str, Any]) -> None:
    print(f"Question: {answer['question']}")
    print(f"Intent: {answer['intent']}")
    print(f"SQL used: {answer['sql_file']}")
    print()
    print(answer["summary"])


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="llm-analyst",
        description="LLM-ready natural-language analytics over generated market datasets.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("question", help="Natural-language analytics question.")
    parser.add_argument("--features", default=DEFAULT_FEATURES_PATH)
    parser.add_argument("--recommendations", default=DEFAULT_RECOMMENDATIONS_PATH)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = _parse_args(argv or sys.argv[1:])
    answer = answer_question(
        args.question,
        features_path=args.features,
        recommendations_path=args.recommendations,
        limit=args.limit,
    )
    if args.json:
        print(json.dumps(answer, ensure_ascii=False, indent=2))
    else:
        _print_answer(answer)


if __name__ == "__main__":
    main()
