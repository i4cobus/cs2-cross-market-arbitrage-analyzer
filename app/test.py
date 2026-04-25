from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List

from app.csfloat_client import fetch_snapshot_by_params
from app.uu_client import (
    enrich_snapshot_with_purchase_orders,
    get_template_snapshot,
    pretty_print_snapshot,
    search_templates,
)
from app.compare import compare_snapshots, pretty_print_comparison
from app.market_name import build_market_hash_name


@dataclass
class TestCase:
    label: str
    base_name: str
    wear: Optional[str]
    category: Optional[str]
    uu_keyword: str
    uu_index: int = 0
    debug: bool = False


def print_header(title: str) -> None:
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)


def print_subheader(title: str) -> None:
    print("\n" + "-" * 40)
    print(title)
    print("-" * 40)


def normalize_market_hash_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    return " ".join(str(name).strip().split())


def expected_market_hash_name(case: TestCase) -> str:
    return build_market_hash_name(
        base_name=case.base_name,
        wear=case.wear,
        category=case.category,
    )


def fetch_cs_snapshot(case: TestCase):
    print_subheader("Step 1: Fetch CSFloat snapshot")
    cs_snap = fetch_snapshot_by_params(
        base_name=case.base_name,
        wear_key=case.wear,
        category_key=case.category,
        debug=case.debug,
    )
    print(cs_snap)
    return cs_snap


def search_uu_candidates(case: TestCase):
    print_subheader("Step 2: Search UU templates")
    candidates = search_templates(case.uu_keyword, debug=case.debug)

    if not candidates:
        print("No UU candidates found.")
        return []

    print("Candidates:")
    for i, item in enumerate(candidates[:10]):
        print(i, item)

    return candidates


def fetch_uu_snapshot(candidates: list[dict], case: TestCase, expected_name: str):
    if not candidates:
        return None

    print_subheader("Step 3: Fetch UU snapshot")
    print("Expected market_hash_name:", expected_name)

    expected_normalized = normalize_market_hash_name(expected_name)
    checked = []

    for i, candidate in enumerate(candidates):
        uu_snap = get_template_snapshot(
            candidate["template_id"],
            debug=case.debug,
            include_purchase_orders=False,
        )
        candidate_name = normalize_market_hash_name(uu_snap.market_hash_name)
        checked.append(candidate_name)

        print(f"Candidate {i}:", candidate)
        print("market_hash_name:", candidate_name)

        if candidate_name == expected_normalized:
            print("Chosen candidate:", candidate)
            uu_snap = enrich_snapshot_with_purchase_orders(
                uu_snap,
                template_id=candidate["template_id"],
                debug=case.debug,
            )
            pretty_print_snapshot(uu_snap)
            return uu_snap

    print("No exact UU candidate matched expected market_hash_name.")
    print("Checked market_hash_names:", checked)
    return None


def compare_two_snapshots(cs_snap, uu_snap):
    if cs_snap is None or uu_snap is None:
        print_subheader("Step 4: Compare")
        print("Skip compare because one side is missing.")
        return None

    print_subheader("Step 4: Compare")
    result = compare_snapshots(cs_snap, uu_snap, cny_to_usd=0.14)
    pretty_print_comparison(result)
    print("\nRaw result:")
    print(result)
    return result


def test_one_item(case: TestCase):
    print_header(f"Testing: {case.label}")
    print("base_name :", case.base_name)
    print("wear      :", case.wear)
    print("category  :", case.category)
    print("uu_keyword:", case.uu_keyword)
    print("uu_index  :", case.uu_index, "(legacy only; exact matching is used)")
    print("debug     :", case.debug)

    expected_name = expected_market_hash_name(case)
    print("expected  :", expected_name)

    cs_snap = fetch_cs_snapshot(case)
    candidates = search_uu_candidates(case)
    uu_snap = fetch_uu_snapshot(candidates, case, expected_name)
    result = compare_two_snapshots(cs_snap, uu_snap)

    return {
        "case": case,
        "cs_snapshot": cs_snap,
        "uu_candidates": candidates,
        "uu_snapshot": uu_snap,
        "comparison": result,
    }


def run_cases(cases: List[TestCase]):
    results = []
    for case in cases:
        try:
            result = test_one_item(case)
            results.append(result)
        except Exception as e:
            print_header(f"FAILED: {case.label}")
            print("Error:", repr(e))
            results.append(
                {
                    "case": case,
                    "cs_snapshot": None,
                    "uu_candidates": None,
                    "uu_snapshot": None,
                    "comparison": None,
                    "error": repr(e),
                }
            )
    return results


def main():
    cases = [
        # 手套
        TestCase(
            label="Gloves - Nocts FT",
            base_name="Sport Gloves | Nocts",
            wear="ft",
            category="normal",
            uu_keyword="夜行衣",
            uu_index=0,
            debug=True,
        ),

        # 音乐盒
        TestCase(
            label="Music Kit - Skog normal",
            base_name="Music Kit | Skog, Metal",
            wear=None,
            category="normal",
            uu_keyword="Skog",
            uu_index=0,
            debug=True,
        ),
        TestCase(
            label="Music Kit - Skog stattrak",
            base_name="Music Kit | Skog, Metal",
            wear=None,
            category="stattrak",
            uu_keyword="Skog",
            uu_index=0,
            debug=True,
        ),

        # 贴纸
        TestCase(
            label="Sticker - Crown (Foil)",
            base_name="Sticker | Crown (Foil)",
            wear=None,
            category="normal",
            uu_keyword="皇冠",
            uu_index=0,
            debug=True,
        ),

        # 箱子
        TestCase(
            label="Case - Revolution Case",
            base_name="Revolution Case",
            wear=None,
            category="normal",
            uu_keyword="反冲武器箱",
            uu_index=0,
            debug=True,
        ),
    ]

    results = run_cases(cases)

    print_header("Summary")
    for r in results:
        case = r["case"]
        comparison = r.get("comparison")
        error = r.get("error")

        if error:
            print(f"[FAILED] {case.label} -> {error}")
            continue

        if comparison and comparison.get("matched"):
            print(f"[MATCHED] {case.label} -> {comparison.get('market_hash_name')}")
        else:
            reason = comparison.get("reason") if comparison else "no comparison"
            print(f"[NOT MATCHED] {case.label} -> {reason}")


if __name__ == "__main__":
    main()
