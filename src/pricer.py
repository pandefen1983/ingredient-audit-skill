from __future__ import annotations

import re
import unicodedata
from typing import Any


UNIT_FACTORS = {
    "g": (1.0, "g"),
    "克": (1.0, "g"),
    "kg": (1000.0, "g"),
    "千克": (1000.0, "g"),
    "公斤": (1000.0, "g"),
    "斤": (500.0, "g"),
    "ml": (1.0, "ml"),
    "毫升": (1.0, "ml"),
    "l": (1000.0, "ml"),
    "升": (1000.0, "ml"),
}
UNIT_PATTERN = "kg|千克|公斤|ml|毫升|g|克|斤|l|升"


def _number(value: str) -> float:
    return float(value)


def parse_spec(spec: str) -> dict[str, Any]:
    normalized = unicodedata.normalize("NFKC", spec).lower().replace(" ", "")
    needs_manual = bool(re.search(r"固形物|沥干物|净含量以|约|随机|赠|买一送一|送一", normalized))
    notes: list[str] = []

    total_match = re.search(rf"共(\d+(?:\.\d+)?)({UNIT_PATTERN})", normalized)
    if total_match:
        amount, unit = _number(total_match.group(1)), total_match.group(2)
        factor, base_unit = UNIT_FACTORS[unit]
        total = amount * factor
    else:
        multi_match = re.search(rf"(\d+(?:\.\d+)?)({UNIT_PATTERN})[*x×](\d+)", normalized)
        if multi_match:
            amount, unit, count = _number(multi_match.group(1)), multi_match.group(2), int(multi_match.group(3))
            factor, base_unit = UNIT_FACTORS[unit]
            total = amount * factor * count
        else:
            single_match = re.search(rf"(\d+(?:\.\d+)?)({UNIT_PATTERN})", normalized)
            if not single_match:
                return {
                    "total_amount": None,
                    "base_unit": None,
                    "needs_manual_check": True,
                    "notes": ["No supported weight or volume found"],
                    "original_spec": spec,
                }
            amount, unit = _number(single_match.group(1)), single_match.group(2)
            factor, base_unit = UNIT_FACTORS[unit]
            total = amount * factor

    if needs_manual:
        notes.append("Specification contains a conditional or ambiguous quantity")
    return {
        "total_amount": round(total, 4),
        "base_unit": base_unit,
        "needs_manual_check": needs_manual,
        "notes": notes,
        "original_spec": spec,
    }


def normalize_price(price: float | str, spec: str) -> dict[str, Any]:
    if isinstance(price, str):
        match = re.search(r"\d+(?:\.\d+)?", unicodedata.normalize("NFKC", price).replace(",", ""))
        if not match:
            raise ValueError(f"Unsupported price: {price}")
        numeric_price = float(match.group(0))
    else:
        numeric_price = float(price)
    parsed = parse_spec(spec)
    total = parsed["total_amount"]
    # Conditional, gifted, approximate, random, or drained quantities do not
    # provide a guaranteed edible denominator, so a unit price would mislead.
    per_100 = round(numeric_price / total * 100, 2) if total and not parsed["needs_manual_check"] else None
    result = {
        "price": numeric_price,
        **parsed,
        "price_per_100": per_100,
        "price_per_100_unit": f"CNY/100{parsed['base_unit']}" if parsed["base_unit"] else None,
    }
    if parsed["base_unit"] == "g" and total and not parsed["needs_manual_check"]:
        result["price_per_500g"] = round(numeric_price / total * 500, 2)
    return result
