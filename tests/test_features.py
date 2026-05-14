from __future__ import annotations

import unittest

from app.features import add_business_indicators


class FeatureEngineeringTests(unittest.TestCase):
    def test_positive_complete_row_gets_scores(self) -> None:
        row = {
            "matched": "True",
            "data_quality_flag": "ok",
            "cs_lowest_ask_usd": "120",
            "cs_highest_bid_usd": "115",
            "cs_bid_depth": "5",
            "cs_vol24h": "30",
            "uu_lowest_ask_usd": "100",
            "uu_highest_bid_usd": "95",
            "uu_bid_depth": "10",
            "uu_listings": "25",
        }

        enriched = add_business_indicators(row)

        self.assertAlmostEqual(enriched["profit_margin_pct"], 0.20)
        self.assertAlmostEqual(enriched["instant_exit_margin_pct"], 0.15)
        self.assertEqual(enriched["data_quality_score"], 1.0)
        self.assertGreater(enriched["opportunity_score"], 0.0)
        self.assertIn(enriched["recommendation_label"], {"watchlist", "strong_candidate"})

    def test_negative_instant_exit_margin_is_avoid(self) -> None:
        row = {
            "matched": "True",
            "data_quality_flag": "ok",
            "cs_lowest_ask_usd": "105",
            "cs_highest_bid_usd": "90",
            "cs_bid_depth": "2",
            "cs_vol24h": "5",
            "uu_lowest_ask_usd": "100",
            "uu_highest_bid_usd": "95",
            "uu_bid_depth": "3",
            "uu_listings": "10",
        }

        enriched = add_business_indicators(row)

        self.assertLess(enriched["instant_exit_margin_pct"], 0)
        self.assertEqual(enriched["recommendation_label"], "avoid")

    def test_missing_prices_are_insufficient_data(self) -> None:
        row = {
            "matched": "True",
            "data_quality_flag": "missing_uu_ask",
            "cs_lowest_ask_usd": "105",
            "cs_highest_bid_usd": "90",
        }

        enriched = add_business_indicators(row)

        self.assertIsNone(enriched["instant_exit_margin_pct"])
        self.assertEqual(enriched["data_quality_score"], 0.0)
        self.assertEqual(enriched["recommendation_label"], "insufficient_data")


if __name__ == "__main__":
    unittest.main()
