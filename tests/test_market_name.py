from __future__ import annotations

import unittest

from app.market_name import build_market_hash_name


class MarketNameTests(unittest.TestCase):
    def test_builds_glove_name_with_star_and_wear(self) -> None:
        self.assertEqual(
            build_market_hash_name("Sport Gloves | Nocts", "ft", "normal"),
            "★ Sport Gloves | Nocts (Field-Tested)",
        )

    def test_builds_weapon_stattrak_name_with_wear(self) -> None:
        self.assertEqual(
            build_market_hash_name("AK-47 | Point Disarray", "fn", "stattrak"),
            "StatTrak™ AK-47 | Point Disarray (Factory New)",
        )

    def test_does_not_add_wear_to_non_floatable_item(self) -> None:
        self.assertEqual(
            build_market_hash_name("Sticker | Crown (Foil)", "ft", "normal"),
            "Sticker | Crown (Foil)",
        )


if __name__ == "__main__":
    unittest.main()
