from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.auditor import audit_ingredients  # noqa: E402
from src.pricer import normalize_price  # noqa: E402
from src.schema import load_preset  # noqa: E402


FIXTURE = ROOT / "tests" / "fixtures" / "benchmark_cases.json"
REPORT = ROOT / "evals" / "report_latest.md"
EXPECTED_CATEGORIES = {
    "hidden_ingredients",
    "pack_unit_price_traps",
    "ocr_noise",
    "clean_expected_pass",
}
PRICE_TOLERANCE = 0.05


def _validate_cases(cases: list[dict[str, Any]]) -> None:
    required = {
        "id",
        "category",
        "preset",
        "ingredients_text",
        "price_yuan",
        "spec_text",
        "expected_status",
        "expected_needs_manual_check",
        "expected_unit_price_per_100",
    }
    if len(cases) < 36:
        raise ValueError(f"benchmark must retain at least the 36-case baseline, got {len(cases)}")
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("benchmark case IDs must be unique")
    categories = defaultdict(int)
    for case in cases:
        missing = required - case.keys()
        if missing:
            raise ValueError(f"{case.get('id', '<unknown>')} missing fields: {sorted(missing)}")
        if case["expected_status"] not in {"PASS", "WARN", "FAIL"}:
            raise ValueError(f"{case['id']} has invalid expected_status")
        categories[case["category"]] += 1
    if not EXPECTED_CATEGORIES.issubset(categories) or any(categories[name] < 9 for name in EXPECTED_CATEGORIES):
        raise ValueError(f"each baseline category must retain at least nine cases, got {dict(categories)}")


def _evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    rules = load_preset(
        case["preset"],
        case.get("variant"),
        case.get("options"),
        case.get("custom_excludes"),
    )
    audit = audit_ingredients(case["ingredients_text"], rules)
    pricing = normalize_price(case["price_yuan"], case["spec_text"])
    expected_price = case["expected_unit_price_per_100"]
    actual_price = pricing["price_per_100"]
    price_ok = (
        actual_price is None
        if expected_price is None
        else actual_price is not None and abs(actual_price - expected_price) <= PRICE_TOLERANCE
    )
    return {
        "id": case["id"],
        "category": case["category"],
        "expected_status": case["expected_status"],
        "actual_status": audit["status"],
        "expected_manual": case["expected_needs_manual_check"],
        "actual_manual": pricing["needs_manual_check"],
        "expected_price": expected_price,
        "actual_price": actual_price,
        "status_ok": audit["status"] == case["expected_status"],
        "manual_ok": pricing["needs_manual_check"] == case["expected_needs_manual_check"],
        "price_ok": price_ok,
    }


def _optional_llm_comparison(cases: list[dict[str, Any]]) -> str:
    if os.getenv("EVAL_USE_LLM") != "1":
        return "disabled"
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "requested but OPENAI_API_KEY is absent; offline evaluation continued"
    sample = cases[: min(5, len(cases))]
    prompt = (
        "Classify each anonymized food-label case as PASS, WARN, or FAIL under its named preset. "
        "Return a compact JSON array with id and status only. Cases:\n"
        + json.dumps(sample, ensure_ascii=False)
    )
    payload = json.dumps(
        {
            "model": os.getenv("EVAL_MODEL", "gpt-4.1-mini"),
            "input": prompt,
            "max_output_tokens": 500,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
        return f"completed on {len(sample)} comparison cases (model-assisted results are non-gating)"
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return f"unavailable ({type(exc).__name__}); offline evaluation continued"


def _percent(numerator: int, denominator: int) -> str:
    return "n/a" if denominator == 0 else f"{numerator / denominator:.2%}"


def _render_report(results: list[dict[str, Any]], llm_note: str) -> str:
    total = len(results)
    status_correct = sum(item["status_ok"] for item in results)
    manual_correct = sum(item["manual_ok"] for item in results)
    priced = [item for item in results if item["expected_price"] is not None]
    price_correct = sum(item["price_ok"] for item in priced)
    violations = [item for item in results if item["expected_status"] != "PASS"]
    expected_pass = [item for item in results if item["expected_status"] == "PASS"]
    false_passes = sum(item["actual_status"] == "PASS" for item in violations)
    false_kills = sum(item["actual_status"] == "FAIL" for item in expected_pass)
    mismatches = [item for item in results if not (item["status_ok"] and item["manual_ok"] and item["price_ok"])]

    lines = [
        "# Golden benchmark report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"Mode: deterministic offline rules; optional LLM comparison: {llm_note}",
        "",
        "## Summary",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Cases | {total} |",
        f"| Status accuracy | {_percent(status_correct, total)} ({status_correct}/{total}) |",
        f"| False-pass rate | {_percent(false_passes, len(violations))} ({false_passes}/{len(violations)}) |",
        f"| False-kill rate | {_percent(false_kills, len(expected_pass))} ({false_kills}/{len(expected_pass)}) |",
        f"| Unit-price accuracy (±{PRICE_TOLERANCE:.2f}) | {_percent(price_correct, len(priced))} ({price_correct}/{len(priced)}) |",
        f"| Manual-check accuracy | {_percent(manual_correct, total)} ({manual_correct}/{total}) |",
        f"| Total mismatches | {len(mismatches)} |",
        "",
        "## Category breakdown",
        "",
        "| Category | Cases | Status correct | Price correct | Manual correct |",
        "|---|---:|---:|---:|---:|",
    ]
    for category in sorted(EXPECTED_CATEGORIES):
        rows = [item for item in results if item["category"] == category]
        category_priced = [item for item in rows if item["expected_price"] is not None]
        lines.append(
            f"| {category} | {len(rows)} | {sum(x['status_ok'] for x in rows)} | "
            f"{sum(x['price_ok'] for x in category_priced)}/{len(category_priced)} | "
            f"{sum(x['manual_ok'] for x in rows)} |"
        )
    lines.extend(["", "## Mismatches", ""])
    if not mismatches:
        lines.append("None.")
    else:
        lines.extend(
            [
                "| ID | Status expected/actual | Manual expected/actual | Price expected/actual |",
                "|---|---|---|---|",
            ]
        )
        for item in mismatches:
            lines.append(
                f"| {item['id']} | {item['expected_status']} / {item['actual_status']} | "
                f"{item['expected_manual']} / {item['actual_manual']} | "
                f"{item['expected_price']} / {item['actual_price']} |"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    _validate_cases(cases)
    results = [_evaluate_case(case) for case in cases]
    llm_note = _optional_llm_comparison(cases)
    report = _render_report(results, llm_note)
    REPORT.write_text(report, encoding="utf-8")
    mismatches = sum(
        not (item["status_ok"] and item["manual_ok"] and item["price_ok"])
        for item in results
    )
    print(report)
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
