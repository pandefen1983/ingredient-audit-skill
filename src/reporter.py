from __future__ import annotations

import argparse
import json
from typing import Any, Iterable

from .auditor import audit_ingredients
from .pricer import normalize_price
from .schema import load_preset


def build_report(
    ingredients: str,
    preset: str,
    mode: str | None = None,
    options: Iterable[str] | None = None,
    custom_exclusions: Iterable[str] | None = None,
    price: float | str | None = None,
    spec: str | None = None,
) -> dict[str, Any]:
    rules = load_preset(preset, mode, options, custom_exclusions)
    audit = audit_ingredients(ingredients, rules)
    pricing = normalize_price(price, spec) if price is not None and spec else None
    return {
        "conclusion": audit["status"],
        "preset": rules.preset,
        "mode": rules.mode,
        "options": list(rules.options),
        "audit": audit,
        "pricing": pricing,
        "evidence": {"ingredient_text": ingredients},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an auditable ingredient and price report.")
    parser.add_argument("--ingredients", required=True)
    parser.add_argument("--preset", required=True)
    parser.add_argument("--mode")
    parser.add_argument("--option", action="append", default=[])
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--price")
    parser.add_argument("--spec")
    args = parser.parse_args()
    report = build_report(
        args.ingredients,
        args.preset,
        args.mode,
        args.option,
        args.exclude,
        args.price,
        args.spec,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
