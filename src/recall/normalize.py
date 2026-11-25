"""Title and spec normalisation plus fuzzy cross-linking de-duplication.

One product is usually listed several times (flagship store, POP store, a
different listing with the same label, 1-pack vs 3-pack). Recall widens the
candidate pool, so de-duplication has to be fuzzy: exact ``sku_id`` matching
alone leaves dozens of duplicates in the report.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Iterable

from ..sources.base import EvidenceType, Sku

_EVIDENCE_RANK = {EvidenceType.A: 0, EvidenceType.B: 1, EvidenceType.C: 2, EvidenceType.D: 3}

_SPEC_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(kg|千克|g|克|斤)\s*(?:[*×xX]\s*(\d+)\s*(?:袋|包|盒|张|片|斤|g|克)?)?",
    re.I,
)
_UNIT_TO_GRAMS = {"kg": 1000.0, "千克": 1000.0, "g": 1.0, "克": 1.0, "斤": 500.0}
_PUNCT_RE = re.compile(r"[^\w\u4e00-\u9fff]+", re.U)
_DEFAULT_NOISE = ("包邮", "旗舰店", "官方", "正品", "整箱", "新包装", "旧包装", "现货")


def spec_grams(text: str | None) -> float | None:
    """Total net weight in grams, or ``None`` when the text carries no weight.

    ``500g*2袋`` becomes 1000g so a 3-pack listing is not compared against a
    single pack as if they were the same SKU.
    """
    if not text:
        return None
    normalized = unicodedata.normalize("NFKC", str(text))
    match = _SPEC_RE.search(normalized)
    if not match:
        return None
    amount = float(match.group(1))
    grams = amount * _UNIT_TO_GRAMS.get(match.group(2).lower(), 1.0)
    count = match.group(3)
    if count:
        grams *= int(count)
    return round(grams, 2)


def normalize_spec(text: str | None) -> str:
    """Canonical weight string such as ``500g``; empty when unknown."""
    grams = spec_grams(text)
    if grams is None:
        return ""
    if grams >= 1000 and grams % 100 == 0:
        return f"{int(grams)}g"
    return f"{grams:g}g"


def normalize_title(title: str | None, noise: Iterable[str] = _DEFAULT_NOISE) -> str:
    """Lowercase, strip punctuation and marketplace noise words."""
    if not title:
        return ""
    text = unicodedata.normalize("NFKC", str(title)).lower()
    for word in noise:
        text = text.replace(word.lower(), "")
    text = text.replace("克", "g").replace("千克", "kg")
    text = _PUNCT_RE.sub("", text)
    return text


def title_key(sku: Sku, noise: Iterable[str] = _DEFAULT_NOISE) -> tuple[str, float | None]:
    """Blocking key: platform + net weight, with the normalised title attached."""
    return (sku.platform, spec_grams(sku.spec))


def _same_product(left: Sku, right: Sku, threshold: float, noise: Iterable[str]) -> bool:
    if left.platform != right.platform:
        return False
    grams_left, grams_right = spec_grams(left.spec), spec_grams(right.spec)
    if grams_left is not None and grams_right is not None and grams_left != grams_right:
        return False
    a, b = normalize_title(left.title, noise), normalize_title(right.title, noise)
    if not a or not b:
        return False
    if a == b:
        return True
    return SequenceMatcher(None, a, b).ratio() >= threshold


def dedupe_fuzzy(
    skus: Iterable[Sku],
    threshold: float = 0.85,
    noise: Iterable[str] = _DEFAULT_NOISE,
) -> list[Sku]:
    """Collapse near-duplicate listings, keeping the best-evidenced SKU."""
    ordered = sorted(skus, key=lambda sku: _EVIDENCE_RANK[sku.evidence_type])
    kept: list[Sku] = []
    for sku in ordered:
        if any(_same_product(sku, existing, threshold, noise) for existing in kept):
            continue
        kept.append(sku)
    return kept
