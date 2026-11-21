from __future__ import annotations

import unittest

from src.auditor import audit_ingredients
from src.pricer import normalize_price, parse_spec
from src.reporter import build_report
from src.schema import load_preset


class PresetTests(unittest.TestCase):
    def audit(
        self,
        text: str,
        preset: str,
        mode: str | None = None,
        options: list[str] | None = None,
    ) -> str:
        return audit_ingredients(text, load_preset(preset, mode, options))["status"]

    def test_medical_medium_levels_are_incremental(self) -> None:
        self.assertEqual(self.audit("配料：牛奶", "medical-medium", "level_1"), "FAIL")
        self.assertEqual(self.audit("配料：水、食盐", "medical-medium", "level_1"), "WARN")
        self.assertEqual(self.audit("配料：玉米淀粉", "medical-medium", "level_1"), "PASS")
        self.assertEqual(self.audit("配料：玉米淀粉", "medical-medium", "level_2"), "FAIL")
        self.assertEqual(self.audit("配料：大豆", "medical-medium", "level_2"), "PASS")
        self.assertEqual(self.audit("配料：大豆", "medical-medium", "level_3"), "FAIL")
        self.assertEqual(self.audit("配料：鲑鱼", "medical-medium", "level_3"), "PASS")
        self.assertEqual(self.audit("配料：虾", "medical-medium", "level_3"), "FAIL")
        self.assertEqual(self.audit("配料：苹果醋", "medical-medium", "level_4"), "FAIL")
        self.assertEqual(self.audit("配料：米醋", "medical-medium", "level_4"), "FAIL")
        self.assertEqual(self.audit("配料：康普茶", "medical-medium", "level_4"), "FAIL")
        self.assertEqual(self.audit("配料：咖啡", "medical-medium", "level_4"), "FAIL")
        self.assertEqual(self.audit("配料：植物油", "medical-medium", "level_5"), "FAIL")
        self.assertEqual(self.audit("配料：大米", "medical-medium", "level_5"), "FAIL")
        self.assertEqual(self.audit("配料：燕麦", "medical-medium", "level_5"), "PASS")

    def test_medical_medium_optional_restrictions_are_multiselect(self) -> None:
        options = ["citric_acid", "msg", "preservatives"]
        rules = load_preset("medical-medium", "level_1", options)
        self.assertEqual(audit_ingredients("配料：水、柠檬酸", rules)["status"], "FAIL")
        self.assertEqual(audit_ingredients("配料：水、味精", rules)["status"], "FAIL")
        self.assertEqual(audit_ingredients("配料：水、山梨酸钾", rules)["status"], "FAIL")
        bonus = load_preset("medical-medium", "level_5", ["bonus_no_salt_seasonings"])
        self.assertEqual(audit_ingredients("配料：水、食盐", bonus)["status"], "FAIL")

    def test_gluten_free_hidden_trap_warns(self) -> None:
        self.assertEqual(self.audit("配料：水、酱油", "gluten-free"), "WARN")
        self.assertEqual(self.audit("配料：水、无麸质酱油", "gluten-free"), "PASS")
        self.assertEqual(self.audit("配料：小麦粉", "gluten-free"), "FAIL")

    def test_vegetarian_modes_differ(self) -> None:
        self.assertEqual(self.audit("配料：鱼肉、食盐", "vegetarian", "vegan"), "FAIL")
        self.assertEqual(self.audit("配料：鱼肉、食盐", "vegetarian", "lacto_ovo"), "FAIL")
        self.assertEqual(self.audit("配料：鱼肉、食盐", "vegetarian", "pescatarian"), "PASS")
        self.assertEqual(self.audit("配料：牛奶、鸡蛋", "vegetarian", "lacto_ovo"), "PASS")

    def test_clean_label_additive_and_count(self) -> None:
        self.assertEqual(self.audit("配料：水、山梨酸钾", "clean-label"), "FAIL")
        long_list = "配料：水、米、盐、糖、姜、蒜、葱、胡椒、花椒"
        result = audit_ingredients(long_list, load_preset("clean-label"))
        self.assertEqual(result["status"], "WARN")
        self.assertEqual(result["ingredient_count"], 9)

    def test_common_ocr_noise_is_normalized(self) -> None:
        self.assertEqual(self.audit("配料：水、山梨酸甲", "clean-label"), "FAIL")
        self.assertEqual(self.audit("配料：水、麦芽胡精", "gluten-free"), "WARN")
        self.assertEqual(self.audit("配料：水、大豆卵粼脂", "medical-medium", "level_3"), "FAIL")

    def test_custom_exclusion_merges(self) -> None:
        rules = load_preset("clean-label", custom_exclusions=["香菜"])
        self.assertEqual(audit_ingredients("配料：水、香菜", rules)["status"], "FAIL")


class PricingTests(unittest.TestCase):
    def test_common_chinese_specs(self) -> None:
        self.assertEqual(parse_spec("500g*2袋")["total_amount"], 1000)
        self.assertEqual(parse_spec("1.5kg")["total_amount"], 1500)
        self.assertEqual(parse_spec("250ml×6盒")["total_amount"], 1500)
        self.assertEqual(parse_spec("共2斤")["total_amount"], 1000)

    def test_price_normalization(self) -> None:
        result = normalize_price("¥30", "500g*2袋")
        self.assertEqual(result["price_per_100"], 3.0)
        self.assertEqual(result["price_per_500g"], 15.0)

    def test_ambiguous_solid_content(self) -> None:
        self.assertTrue(parse_spec("净含量500g，固形物含量不低于60%")["needs_manual_check"])

    def test_ambiguous_quantity_does_not_claim_unit_price(self) -> None:
        result = normalize_price(15, "净含量500g，固形物含量不低于60%")
        self.assertTrue(result["needs_manual_check"])
        self.assertIsNone(result["price_per_100"])
        self.assertNotIn("price_per_500g", result)

    def test_report_combines_evidence(self) -> None:
        report = build_report("配料：水、山梨酸钾", "clean-label", price=12, spec="200g")
        self.assertEqual(report["conclusion"], "FAIL")
        self.assertEqual(report["pricing"]["price_per_100"], 6.0)

    def test_report_includes_selected_options(self) -> None:
        report = build_report(
            "配料：水、柠檬酸",
            "medical-medium",
            "level_1",
            ["citric_acid"],
        )
        self.assertEqual(report["conclusion"], "FAIL")
        self.assertEqual(report["options"], ["citric_acid"])


if __name__ == "__main__":
    unittest.main()
