from __future__ import annotations

import unittest

from app.uu_client import (
    get_on_sale_commodities,
    get_template_purchase_orders,
    parse_on_sale_summary,
    parse_purchase_order_summary,
)
import app.uu_client as uu_client


class UUClientParserTests(unittest.TestCase):
    def test_parse_on_sale_summary_uses_total_count_and_lowest_price(self) -> None:
        summary = parse_on_sale_summary(
            {
                "Code": 0,
                "Data": {
                    "TotalCount": 60707,
                    "commodityList": [
                        {"price": 2.10},
                        {"price": 2.09},
                    ],
                },
            }
        )

        self.assertEqual(summary.lowest_ask, 2.09)
        self.assertEqual(summary.listings, 60707)

    def test_parse_on_sale_summary_supports_nested_lists(self) -> None:
        summary = parse_on_sale_summary(
            {
                "Data": {
                    "result": {
                        "total": 2,
                        "records": [
                            {"sellPrice": "12.50"},
                            {"sellPrice": "11.90"},
                        ],
                    }
                }
            }
        )

        self.assertEqual(summary.lowest_ask, 11.9)
        self.assertEqual(summary.listings, 2)

    def test_parse_purchase_order_summary_sums_depth_at_highest_bid(self) -> None:
        summary = parse_purchase_order_summary(
            {
                "code": 0,
                "data": {
                    "total": 26,
                    "purchaseOrderResponseList": [
                        {"purchasePrice": 10190.0, "surplusQuantity": 1},
                        {"purchasePrice": 10180.0, "surplusQuantity": 4},
                        {"purchasePrice": 10190.0, "surplusQuantity": 2},
                    ],
                },
            }
        )

        self.assertEqual(summary.highest_bid, 10190.0)
        self.assertEqual(summary.bid_depth, 3)
        self.assertEqual(summary.total_orders, 26)

    def test_purchase_order_payload_uses_widest_abrade_range(self) -> None:
        calls = []
        original_post = uu_client._post

        def fake_post(path, payload, timeout=20, debug=False):
            calls.append((path, payload))
            return {"code": 0, "data": {}}

        try:
            uu_client._post = fake_post
            get_template_purchase_orders("51135", page_index=1, page_size=10)
        finally:
            uu_client._post = original_post

        self.assertEqual(
            calls[0][0],
            "/api/youpin/bff/trade/purchase/order/getTemplatePurchaseOrderListPC",
        )
        self.assertEqual(
            calls[0][1],
            {
                "templateId": "51135",
                "minAbrade": "0",
                "maxAbrade": "1",
                "pageIndex": 1,
                "pageSize": 10,
            },
        )

    def test_on_sale_payload_matches_market_listing_endpoint(self) -> None:
        calls = []
        original_post = uu_client._post

        def fake_post(path, payload, timeout=20, debug=False):
            calls.append((path, payload))
            return {"Code": 0, "Data": {}}

        try:
            uu_client._post = fake_post
            get_on_sale_commodities("880", page_index=1, page_size=10)
        finally:
            uu_client._post = original_post

        self.assertEqual(calls[0][0], "/api/homepage/pc/goods/market/queryOnSaleCommodityList")
        self.assertEqual(
            calls[0][1],
            {
                "gameId": "730",
                "listType": "10",
                "templateId": "880",
                "listSortType": 1,
                "sortType": 0,
                "pageIndex": 1,
                "pageSize": 10,
            },
        )


if __name__ == "__main__":
    unittest.main()
