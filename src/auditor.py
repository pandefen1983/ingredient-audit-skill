from __future__ import annotations

import re
import unicodedata
from typing import Any

from .schema import RuleSet


OCR_NORMALIZATIONS = {
    "山梨酸甲": "山梨酸钾",
    "苯甲酸纳": "苯甲酸钠",
    "麦芽胡精": "麦芽糊精",
    "黄源胶": "黄原胶",
    "谷元粉": "谷朊粉",
    "大豆卵粼脂": "大豆卵磷脂",
    "三氯庶糖": "三氯蔗糖",
}


def _normalize(text: str) -> str:
    normalized = re.sub(r"\s+", "", unicodedata.normalize("NFKC", text).strip().lower())
    for noisy, canonical in OCR_NORMALIZATIONS.items():
        normalized = normalized.replace(noisy, canonical)
    return normalized


def _mask_allowed(text: str, allow_terms: tuple[str, ...]) -> str:
    masked = text
    for term in sorted(allow_terms, key=len, reverse=True):
        masked = masked.replace(_normalize(term), " " * len(_normalize(term)))
    return masked


def _snippet(text: str, start: int, end: int, radius: int = 18) -> str:
    return text[max(0, start - radius) : min(len(text), end + radius)]


def _ingredient_count(text: str) -> int:
    body = re.sub(r"^(?:配料表?|ingredients?)\s*[:：]\s*", "", text, flags=re.I)
    depth = 0
    count = 1 if body.strip() else 0
    for char in body:
        if char in "（([":
            depth += 1
        elif char in "）)]":
            depth = max(0, depth - 1)
        elif depth == 0 and char in ",，、;；":
            count += 1
    return count


def audit_ingredients(text: str, rules: RuleSet) -> dict[str, Any]:
    original = text.strip()
    normalized = _normalize(original)
    searchable = _mask_allowed(normalized, rules.allow_terms)
    failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if not normalized:
        warnings.append({"type": "missing_ingredients", "match": "", "reason": "No ingredient text supplied", "snippet": ""})

    for term in rules.exclude_terms:
        needle = _normalize(term)
        start = searchable.find(needle)
        if start >= 0:
            failures.append(
                {
                    "type": "excluded_term",
                    "match": term,
                    "reason": f"Excluded by {rules.preset}/{rules.mode or 'default'}",
                    "snippet": _snippet(original, start, start + len(needle)),
                }
            )

    for item in rules.fail_patterns:
        match = re.search(item["pattern"], searchable, flags=re.I)
        if match:
            failures.append(
                {
                    "type": "fail_pattern",
                    "match": match.group(0),
                    "reason": item.get("reason", "Matched a prohibited pattern"),
                    "snippet": _snippet(original, match.start(), match.end()),
                }
            )

    # Warning patterns inspect the normalized original so an allowed compound
    # can still trigger a source-verification warning (for example 麦芽糊精).
    for item in rules.warn_patterns:
        match = re.search(item["pattern"], normalized, flags=re.I)
        if match:
            warnings.append(
                {
                    "type": "hidden_trap",
                    "match": match.group(0),
                    "reason": item.get("reason", "Needs manual verification"),
                    "snippet": _snippet(original, match.start(), match.end()),
                }
            )

    ingredient_count = _ingredient_count(original)
    if rules.max_ingredient_count is not None and ingredient_count > rules.max_ingredient_count:
        warnings.append(
            {
                "type": "ingredient_count",
                "match": str(ingredient_count),
                "reason": f"Ingredient count exceeds threshold {rules.max_ingredient_count}",
                "snippet": original[:80],
            }
        )

    status = "FAIL" if failures else "WARN" if warnings else "PASS"
    return {
        "status": status,
        "preset": rules.preset,
        "mode": rules.mode,
        "options": list(rules.options),
        "ingredient_count": ingredient_count,
        "failures": failures,
        "warnings": warnings,
        "original_text": original,
    }
