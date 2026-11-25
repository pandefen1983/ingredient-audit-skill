from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.recall.normalize import dedupe_fuzzy, normalize_spec, normalize_title, spec_grams
from src.recall.keywords import expand_queries, load_keywords, resolve_category
from src.recall.planner import build_plan
from src.recall.run import build_cache_report
from src.recall.store import SkuCache
from src.recall.taxonomy import build_category_tasks, load_platforms
from src.sources.base import EvidenceType, make_sku, SkuDraft

KEYWORDS = load_keywords()
PLATFORMS = load_platforms()


def _sku(title: str, spec: str, evidence: EvidenceType = EvidenceType.D, platform: str = "jd"):
    return make_sku(
        SkuDraft(
            platform=platform,
            sku_id=title,
            title=title,
            price=12.0,
            spec=spec,
            ingredient_text="荞麦粉、生活饮用水",
            evidence_type=evidence,
        )
    )


class KeywordExpansionTests(unittest.TestCase):
    def test_resolves_primary_and_alias(self) -> None:
        self.assertEqual(resolve_category("面条", KEYWORDS)[0], "面条")
        self.assertEqual(resolve_category("挂面", KEYWORDS)[0], "面条")
        self.assertEqual(resolve_category("米粉", KEYWORDS)[0], "米线")

    def test_unknown_intent_does_not_crash(self) -> None:
        self.assertIsNone(resolve_category("不存在的品类", KEYWORDS))
        queries = expand_queries("不存在的品类", KEYWORDS, ["jd"], "medical-medium")
        self.assertTrue(all(q.query == "不存在的品类" for q in queries))

    def test_tier1_has_ingredient_and_brand_queries(self) -> None:
        queries = expand_queries("面条", KEYWORDS, ["jd"], "medical-medium")
        texts = {q.query for q in queries}
        self.assertIn("荞麦面条", texts)
        self.assertIn("纯荞麦面条", texts)
        self.assertIn("金沙河 面条", texts)
        tiers = {q.tier for q in queries if q.query == "纯荞麦面条"}
        self.assertEqual(tiers, {1})

    def test_alias_queries_are_tier3(self) -> None:
        queries = expand_queries("面条", KEYWORDS, ["jd"], "medical-medium")
        aliases = [q for q in queries if q.query in {"挂面", "龙须面"}]
        self.assertTrue(aliases)
        self.assertTrue(all(q.tier == 3 for q in aliases))

    def test_expansion_is_deterministic_and_deduplicated(self) -> None:
        first = expand_queries("面条", KEYWORDS, ["jd", "taobao"], "medical-medium")
        second = expand_queries("面条", KEYWORDS, ["jd", "taobao"], "medical-medium")
        self.assertEqual([q.as_dict() for q in first], [q.as_dict() for q in second])
        keys = [(q.platform, q.query) for q in first]
        self.assertEqual(len(keys), len(set(keys)))

    def test_platform_filter_is_respected(self) -> None:
        queries = expand_queries("面条", KEYWORDS, ["jd"], "medical-medium")
        self.assertEqual({q.platform for q in queries}, {"jd"})


class CategoryTaskTests(unittest.TestCase):
    def test_one_task_per_price_band(self) -> None:
        tasks = build_category_tasks(["jd"], PLATFORMS, "面条")
        self.assertEqual(len(tasks), 3)  # three configured bands
        self.assertTrue(all(task.requests == task.pages for task in tasks))

    def test_unknown_category_has_no_task(self) -> None:
        self.assertEqual(build_category_tasks(["jd"], PLATFORMS, "不存在的品类"), [])

    def test_max_pages_override(self) -> None:
        tasks = build_category_tasks(["jd"], PLATFORMS, "面条", max_pages=1)
        self.assertTrue(all(task.pages == 1 for task in tasks))


class PlanTests(unittest.TestCase):
    def test_plan_orders_tiers_and_counts_requests(self) -> None:
        plan = build_plan("面条", preset="medical-medium", mode="level_3", platforms=["jd", "taobao"])
        self.assertGreater(plan.requests, 20)
        tiers = [q.tier for q in plan.queries]
        self.assertEqual(tiers, sorted(tiers))
        summary = plan.summary()
        self.assertIn("tier1", summary["by_tier"])
        self.assertEqual(summary["platforms"], ["jd", "taobao"])

    def test_budget_drops_lowest_tier_first(self) -> None:
        full = build_plan("面条", platforms=["jd"], budget=10_000)
        cut = build_plan("面条", platforms=["jd"], budget=8)
        self.assertLessEqual(cut.requests, 8)
        self.assertTrue(cut.dropped)
        # Everything kept should be tier 1 unless tier 1 alone exceeded the budget.
        kept_tiers = {q.tier for q in cut.queries}
        self.assertTrue(kept_tiers <= {1})
        self.assertGreater(full.requests, cut.requests)
        self.assertTrue(all(item["reason"] == "budget exceeded" for item in cut.dropped))

    def test_plan_is_json_serialisable(self) -> None:
        import json

        plan = build_plan("米线", platforms=["douyin"], budget=20)
        json.dumps(plan.as_dict(), ensure_ascii=False)


class NormalizeTests(unittest.TestCase):
    def test_spec_grams_handles_units_and_multipacks(self) -> None:
        self.assertEqual(spec_grams("500g"), 500.0)
        self.assertEqual(spec_grams("500克"), 500.0)
        self.assertEqual(spec_grams("1kg"), 1000.0)
        self.assertEqual(spec_grams("2斤"), 1000.0)
        self.assertEqual(spec_grams("500g*2袋"), 1000.0)
        self.assertIsNone(spec_grams("无规格"))

    def test_normalize_spec(self) -> None:
        self.assertEqual(normalize_spec("1kg"), "1000g")
        self.assertEqual(normalize_spec("500克"), "500g")
        self.assertEqual(normalize_spec(""), "")

    def test_normalize_title_strips_noise(self) -> None:
        self.assertEqual(normalize_title("【包邮】金沙河 荞麦面 500克"), "金沙河 荞麦面 500g".replace(" ", ""))
        self.assertEqual(normalize_title(None), "")


class FuzzyDedupeTests(unittest.TestCase):
    def test_merges_same_product_listed_twice_and_keeps_best_evidence(self) -> None:
        weak = _sku("金沙河100%纯荞麦面 500g 包邮", "500g", EvidenceType.D)
        strong = _sku("金沙河 100%纯荞麦面 500g 旗舰店", "500g", EvidenceType.A)
        unique = dedupe_fuzzy([weak, strong])
        self.assertEqual(len(unique), 1)
        self.assertEqual(unique[0].evidence_type, EvidenceType.A)

    def test_keeps_different_specs_separate(self) -> None:
        small = _sku("金沙河100%纯荞麦面 500g", "500g")
        large = _sku("金沙河100%纯荞麦面 1kg", "1kg")
        self.assertEqual(len(dedupe_fuzzy([small, large])), 2)

    def test_does_not_merge_different_products(self) -> None:
        noodles = _sku("金沙河纯荞麦面条 500g", "500g")
        pancakes = _sku("沂蒙纯小米煎饼 500g", "500g")
        self.assertEqual(len(dedupe_fuzzy([noodles, pancakes])), 2)


class CacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = SkuCache(Path(self.tmp.name) / "recall.sqlite3")

    def tearDown(self) -> None:
        self.cache.close()
        self.tmp.cleanup()

    def test_refetch_respects_ttl(self) -> None:
        now = datetime.now(timezone.utc)
        self.assertTrue(self.cache.should_refetch("jd", "荞麦面条", at=now))
        self.cache.record_query("jd", "荞麦面条", 42, at=now - timedelta(days=3))
        self.assertFalse(self.cache.should_refetch("jd", "荞麦面条", ttl_days=7, at=now))
        self.assertTrue(self.cache.should_refetch("jd", "荞麦面条", ttl_days=1, at=now))

    def test_query_log_records_hits(self) -> None:
        self.cache.record_query("jd", "荞麦面条", 42)
        rows = self.cache.query_log("jd")
        self.assertEqual(rows[0]["n_items"], 42)

    def test_sku_roundtrip_and_stats(self) -> None:
        payload = {"skuId": "100012043978", "skuName": "金沙河 荞麦面", "priceInfo": {"lowestPrice": 11.9}}
        self.cache.upsert_sku("jd", "100012043978", payload, "D")
        self.cache.upsert_sku("jd", "100012043978", payload, "D")  # idempotent
        raw = self.cache.load_raw("jd")
        self.assertEqual(len(raw), 1)
        self.assertEqual(self.cache.stats()["skus"], 1)

    def test_cache_report_runs_the_evidence_gate(self) -> None:
        self.cache.upsert_sku(
            "douyin",
            "3685154883787522",
            {
                "product_id": "3825746598722405308",
                "sku_id": "3685154883787522",
                "title": "100%纯荞麦挂面 500g",
                "price": 12.53,
                "spec": "1000g",
                "配料表": "荞麦粉、生活饮用水",
            },
            "A",
        )
        self.cache.upsert_sku(
            "douyin",
            "3710291584422402",
            {
                "product_id": "3840631879531364379",
                "sku_id": "3710291584422402",
                "title": "纯荞麦卷饼",
                "price": 15.39,
                "spec": "1g*2张",
                "配料表": "详见详情",
            },
            "D",
        )
        report = build_cache_report(self.cache, "medical-medium", "level_3")
        self.assertEqual(report["funnel"]["recalled"], 2)
        self.assertEqual(report["funnel"]["with_trusted_evidence"], 1)
        self.assertEqual(report["funnel"]["verdicts"]["PASS"], 1)
        self.assertEqual(report["funnel"]["verdicts"]["UNVERIFIED"], 1)
        self.assertEqual(report["sources"]["raw_from_cache"], 2)


if __name__ == "__main__":
    unittest.main()
