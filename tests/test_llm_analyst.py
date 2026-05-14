from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from app.llm_analyst import answer_question, classify_intent, summarize_rows


class LLMAnalystTests(unittest.TestCase):
    def test_classify_intent(self) -> None:
        self.assertEqual(classify_intent("show top opportunities").name, "top_opportunities")
        self.assertEqual(classify_intent("summarize data quality").name, "data_quality")
        self.assertEqual(classify_intent("label distribution").name, "label_distribution")
        self.assertEqual(classify_intent("which items have liquidity").name, "liquidity")

    def test_summarize_quality_rows(self) -> None:
        intent = classify_intent("quality")
        summary = summarize_rows(
            intent,
            [
                {
                    "total_rows": 10,
                    "match_rate_pct": 100.0,
                    "ok_rate_pct": 90.0,
                    "missing_uu_ask_rows": 1,
                    "missing_uu_bid_rows": 0,
                    "missing_cs_bid_rows": 1,
                    "negative_exit_margin_rows": 2,
                }
            ],
        )

        self.assertIn("10 rows", summary)
        self.assertIn("100.0% match rate", summary)

    def test_answer_question_runs_sql_against_temp_datasets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            features_path = Path(tmpdir) / "features.csv"
            recommendations_path = Path(tmpdir) / "recommendations.csv"

            with features_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "matched",
                        "data_quality_flag",
                        "uu_lowest_ask_usd",
                        "uu_highest_bid_usd",
                        "cs_highest_bid_usd",
                        "instant_exit_margin_pct",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "matched": "True",
                        "data_quality_flag": "ok",
                        "uu_lowest_ask_usd": "10",
                        "uu_highest_bid_usd": "9",
                        "cs_highest_bid_usd": "12",
                        "instant_exit_margin_pct": "0.2",
                    }
                )

            with recommendations_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "rank",
                        "market_hash_name",
                        "recommendation_label",
                        "opportunity_score",
                        "instant_exit_margin_pct",
                        "risk_score",
                        "cs_highest_bid_usd",
                        "uu_lowest_ask_usd",
                        "cs_vol24h",
                        "uu_listings",
                        "recommendation_reason",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "rank": "1",
                        "market_hash_name": "A",
                        "recommendation_label": "strong_candidate",
                        "opportunity_score": "0.8",
                        "instant_exit_margin_pct": "0.2",
                        "risk_score": "0.1",
                        "cs_highest_bid_usd": "12",
                        "uu_lowest_ask_usd": "10",
                        "cs_vol24h": "5",
                        "uu_listings": "3",
                        "recommendation_reason": "test",
                    }
                )

            answer = answer_question(
                "what are the top opportunities?",
                features_path=str(features_path),
                recommendations_path=str(recommendations_path),
            )

        self.assertEqual(answer["intent"], "top_opportunities")
        self.assertEqual(answer["rows"][0]["market_hash_name"], "A")
        self.assertIn("Top opportunity summary", answer["summary"])


if __name__ == "__main__":
    unittest.main()
