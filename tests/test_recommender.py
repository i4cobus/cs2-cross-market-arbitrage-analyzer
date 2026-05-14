from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from app.recommender import build_recommendations, explain_recommendation, rank_recommendations


class RecommenderTests(unittest.TestCase):
    def test_rank_recommendations_orders_by_score(self) -> None:
        rows = [
            {
                "market_hash_name": "A",
                "recommendation_label": "watchlist",
                "opportunity_score": "0.50",
                "instant_exit_margin_pct": "0.05",
                "cs_liquidity_score": "0.50",
            },
            {
                "market_hash_name": "B",
                "recommendation_label": "strong_candidate",
                "opportunity_score": "0.80",
                "instant_exit_margin_pct": "0.10",
                "cs_liquidity_score": "0.60",
            },
        ]

        ranked = rank_recommendations(rows, min_label="watchlist")

        self.assertEqual([row["market_hash_name"] for row in ranked], ["B", "A"])
        self.assertEqual([row["rank"] for row in ranked], [1, 2])
        self.assertIn("recommendation_reason", ranked[0])

    def test_rank_recommendations_filters_low_priority_by_default_threshold(self) -> None:
        rows = [
            {"market_hash_name": "A", "recommendation_label": "low_priority", "opportunity_score": "0.30"},
            {"market_hash_name": "B", "recommendation_label": "watchlist", "opportunity_score": "0.55"},
            {"market_hash_name": "C", "recommendation_label": "avoid", "opportunity_score": "0.10"},
        ]

        ranked = rank_recommendations(rows, min_label="watchlist")

        self.assertEqual([row["market_hash_name"] for row in ranked], ["B"])

    def test_explain_recommendation_mentions_negative_margin_for_avoid(self) -> None:
        reason = explain_recommendation(
            {
                "recommendation_label": "avoid",
                "instant_exit_margin_pct": "-0.05",
                "risk_score": "0.70",
                "cs_liquidity_score": "0.20",
                "demand_score": "0.30",
                "uu_supply_score": "0.30",
            }
        )

        self.assertIn("negative instant-exit margin", reason)
        self.assertIn("not recommended", reason)

    def test_build_recommendations_writes_output_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "features.csv"
            output_path = Path(tmpdir) / "recommendations.csv"

            with input_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "market_hash_name",
                        "recommendation_label",
                        "opportunity_score",
                        "instant_exit_margin_pct",
                        "risk_score",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "market_hash_name": "A",
                        "recommendation_label": "watchlist",
                        "opportunity_score": "0.55",
                        "instant_exit_margin_pct": "0.05",
                        "risk_score": "0.20",
                    }
                )

            rows = build_recommendations(
                input_path=str(input_path),
                output_path=str(output_path),
                min_label="watchlist",
            )

            self.assertEqual(len(rows), 1)
            self.assertTrue(output_path.exists())
            with output_path.open(newline="", encoding="utf-8") as f:
                written = list(csv.DictReader(f))
            self.assertEqual(written[0]["rank"], "1")
            self.assertEqual(written[0]["market_hash_name"], "A")


if __name__ == "__main__":
    unittest.main()
