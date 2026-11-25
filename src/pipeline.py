"""Evidence-gated audit: recall many SKUs, verdict only the ones we can prove."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from .reporter import build_report
from .sources.base import EvidenceType, Sku

_EVIDENCE_RANK = {EvidenceType.A: 0, EvidenceType.B: 1, EvidenceType.C: 2, EvidenceType.D: 3}


def dedupe_skus(skus: Iterable[Sku]) -> list[Sku]:
    """Keep one SKU per ``(platform, sku_id)``, preferring the best evidence."""
    best: dict[tuple[str, str], Sku] = {}
    for sku in skus:
        key = (sku.platform, sku.sku_id or sku.title)
        current = best.get(key)
        if current is None or _EVIDENCE_RANK[sku.evidence_type] < _EVIDENCE_RANK[current.evidence_type]:
            best[key] = sku
    return list(best.values())


def audit_sku(
    sku: Sku,
    preset: str,
    mode: str | None = None,
    options: Iterable[str] | None = None,
    custom_exclusions: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Judge one SKU, refusing to PASS/FAIL without A/B-grade evidence."""
    base: dict[str, Any] = {
        "platform": sku.platform,
        "sku_id": sku.sku_id,
        "title": sku.title,
        "sku": sku.as_dict(),
    }

    if not sku.has_trusted_evidence:
        base.update(
            {
                "conclusion": "UNVERIFIED",
                "reason": "no_trusted_ingredient_evidence",
                "evidence_type": sku.evidence_type.value,
                "audit": None,
                "pricing": None,
            }
        )
        return base

    report = build_report(
        sku.ingredient_text,
        preset,
        mode,
        options,
        custom_exclusions,
        price=sku.price,
        spec=sku.spec or None,
    )
    base.update(report)
    base["evidence_type"] = sku.evidence_type.value
    base["evidence"] = {
        "type": sku.evidence_type.value,
        "url": sku.url,
        "note": sku.evidence_note,
        "checked_at": sku.checked_at,
        "ingredient_text": sku.ingredient_text,
    }
    if sku.price is not None and not sku.spec:
        base.setdefault("pricing_notes", []).append("price present but spec missing; unit price not computed")
    return base


def build_funnel(skus: Iterable[Sku], results: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Recall -> dedupe -> evidence -> verdict funnel for the report header."""
    recalled = list(skus)
    unique = dedupe_skus(recalled)
    verified = [sku for sku in unique if sku.has_trusted_evidence]
    verdicts = Counter(result["conclusion"] for result in results)
    judged = sum(verdicts[key] for key in ("PASS", "WARN", "FAIL"))
    return {
        "recalled": len(recalled),
        "unique": len(unique),
        "with_trusted_evidence": len(verified),
        "verified_ratio": round(len(verified) / len(unique), 4) if unique else 0.0,
        "verdicts": {
            "PASS": verdicts["PASS"],
            "WARN": verdicts["WARN"],
            "FAIL": verdicts["FAIL"],
            "UNVERIFIED": verdicts["UNVERIFIED"],
        },
        "judged": judged,
        "pass_rate_of_verified": round(verdicts["PASS"] / judged, 4) if judged else 0.0,
    }


def run_pipeline(
    skus: Iterable[Sku],
    preset: str,
    mode: str | None = None,
    options: Iterable[str] | None = None,
    custom_exclusions: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Audit every recalled SKU and return results plus the coverage funnel."""
    unique = dedupe_skus(skus)
    results = [
        audit_sku(sku, preset, mode, options, custom_exclusions)
        for sku in unique
    ]
    return {"results": results, "funnel": build_funnel(skus, results)}
