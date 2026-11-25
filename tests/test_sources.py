from __future__ import annotations

import unittest

from src.pipeline import audit_sku, build_funnel, dedupe_skus, run_pipeline
from src.sources import (
    SkuDraft,
    douyin_to_sku,
    jd_to_sku,
    make_sku,
    taobao_to_sku,
)
from src.sources.base import EvidenceType


DOUYIN_TRUSTED = {
    "product_id": "3825746598722405308",
    "sku_id": "3685154883787522",
    "title": "100%纯荞麦挂面 500g",
    "price": 12.53,
    "spec": "1000g",
    "配料表": "荞麦粉、生活饮用水",
}

DOUYIN_PLACEHOLDER = {
    "product_id": "3840631879531364379",
    "sku_id": "3710291584422402",
    "title": "纯荞麦卷饼",
    "price": 15.39,
    "spec": "1g*2张",
    "配料表": "详见详情",
}

DOUYIN_SOY = {
    "product_id": "3832084106494214505",
    "sku_id": "3698429215302402",
    "title": "沂蒙公社纯荞麦煎饼",
    "price": 28,
    "spec": "400g",
    "配料表": "荞麦、大豆、生活饮用水",
}

JD_RAW = {
    "skuId": "100012043978",
    "skuName": "金沙河 100%荞麦面 500g",
    "priceInfo": {"lowestPrice": 11.9},
    "materialUrl": "https://item.jd.com/100012043978.html",
    "shopInfo": {"shopName": "金沙河旗舰店"},
}

TB_RAW = {
    "num_iid": "680123456789",
    "title": "金沙河荞麦面条100%纯荞麦挂面",
    "zk_final_price": "10.81",
    "coupon_share_url": "https://uland.taobao.com/coupon/edetail?itemId=680123456789",
}


class AdapterTests(unittest.TestCase):
    def test_douyin_trusted_label_is_grade_a(self) -> None:
        sku = douyin_to_sku(DOUYIN_TRUSTED)
        self.assertEqual(sku.platform, "douyin")
        self.assertEqual(sku.evidence_type, EvidenceType.A)
        self.assertEqual(sku.ingredient_text, "荞麦粉、生活饮用水")
        self.assertIn("haohuo.jinritemai.com", sku.url)

    def test_douyin_placeholder_becomes_grade_d(self) -> None:
        sku = douyin_to_sku(DOUYIN_PLACEHOLDER)
        self.assertEqual(sku.evidence_type, EvidenceType.D)
        self.assertIsNone(sku.ingredient_text)

    def test_jd_union_never_claims_evidence(self) -> None:
        sku = jd_to_sku(JD_RAW)
        self.assertEqual(sku.evidence_type, EvidenceType.D)
        self.assertIsNone(sku.ingredient_text)
        self.assertEqual(sku.price, 11.9)
        self.assertIn("item.jd.com", sku.url)

    def test_jd_price_defaults_to_yuan_and_never_guesses(self) -> None:
        # No magnitude heuristics: 1190 stays 1190 unless the caller says cents.
        sku = jd_to_sku({**JD_RAW, "priceInfo": {"lowestPrice": 1190}})
        self.assertEqual(sku.price, 1190.0)

    def test_jd_price_declared_in_cents_is_scaled(self) -> None:
        sku = jd_to_sku({**JD_RAW, "priceInfo": {"lowestPrice": 1190}}, price_unit="cents")
        self.assertEqual(sku.price, 11.9)
        self.assertIn("cents", sku.evidence_note)

    def test_jd_rejects_unknown_price_unit(self) -> None:
        with self.assertRaises(ValueError):
            jd_to_sku(JD_RAW, price_unit="fen")

    def test_taobao_union_never_claims_evidence(self) -> None:
        sku = taobao_to_sku(TB_RAW)
        self.assertEqual(sku.evidence_type, EvidenceType.D)
        self.assertEqual(sku.price, 10.81)
        self.assertIn("uland.taobao.com", sku.url)

    def test_trusted_grade_without_text_is_downgraded(self) -> None:
        sku = make_sku(
            SkuDraft(
                platform="douyin",
                sku_id="1",
                title="x",
                price=1.0,
                spec="500g",
                ingredient_text=None,
                evidence_type=EvidenceType.A,
            )
        )
        self.assertEqual(sku.evidence_type, EvidenceType.D)


class EvidenceGateTests(unittest.TestCase):
    def test_trusted_label_passes(self) -> None:
        result = audit_sku(douyin_to_sku(DOUYIN_TRUSTED), "medical-medium", "level_3")
        self.assertEqual(result["conclusion"], "PASS")
        self.assertEqual(result["pricing"]["price_per_500g"], 6.26)

    def test_soy_fails_at_level_3(self) -> None:
        result = audit_sku(douyin_to_sku(DOUYIN_SOY), "medical-medium", "level_3")
        self.assertEqual(result["conclusion"], "FAIL")
        matches = [item["match"] for item in result["audit"]["failures"]]
        self.assertIn("大豆", matches)

    def test_jd_sku_is_unverified_not_failed(self) -> None:
        result = audit_sku(jd_to_sku(JD_RAW), "medical-medium", "level_3")
        self.assertEqual(result["conclusion"], "UNVERIFIED")
        self.assertEqual(result["reason"], "no_trusted_ingredient_evidence")
        self.assertIsNone(result["audit"])

    def test_marketing_claim_never_passes(self) -> None:
        sku = make_sku(
            SkuDraft(
                platform="douyin",
                sku_id="9",
                title="100%纯荞麦面 无添加",
                price=9.9,
                spec="500g",
                ingredient_text="100%纯荞麦",
                evidence_type=EvidenceType.C,
            )
        )
        result = audit_sku(sku, "medical-medium", "level_3")
        self.assertEqual(result["conclusion"], "UNVERIFIED")


class FunnelTests(unittest.TestCase):
    def test_dedupe_prefers_best_evidence(self) -> None:
        weak = douyin_to_sku({**DOUYIN_TRUSTED, "配料表": "详见详情"})
        strong = douyin_to_sku(DOUYIN_TRUSTED)
        unique = dedupe_skus([weak, strong])
        self.assertEqual(len(unique), 1)
        self.assertEqual(unique[0].evidence_type, EvidenceType.A)

    def test_funnel_counts(self) -> None:
        skus = [
            douyin_to_sku(DOUYIN_TRUSTED),
            douyin_to_sku(DOUYIN_SOY),
            douyin_to_sku(DOUYIN_PLACEHOLDER),
            jd_to_sku(JD_RAW),
            taobao_to_sku(TB_RAW),
        ]
        output = run_pipeline(skus, "medical-medium", "level_3")
        funnel = output["funnel"]
        self.assertEqual(funnel["recalled"], 5)
        self.assertEqual(funnel["unique"], 5)
        self.assertEqual(funnel["with_trusted_evidence"], 2)
        self.assertEqual(funnel["verdicts"]["PASS"], 1)
        self.assertEqual(funnel["verdicts"]["FAIL"], 1)
        self.assertEqual(funnel["verdicts"]["UNVERIFIED"], 3)

    def test_funnel_handles_empty_input(self) -> None:
        self.assertEqual(build_funnel([], [])["verified_ratio"], 0.0)


if __name__ == "__main__":
    unittest.main()
