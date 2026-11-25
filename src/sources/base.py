"""Platform-agnostic product records and evidence grading.

Every marketplace returns a different shape. Adapters translate one platform's
raw payload into :class:`Sku` so that the auditor, pricer and reporter only ever
see a single structure.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class EvidenceType(str, Enum):
    """How trustworthy the ingredient text attached to a SKU is."""

    A = "A"  # full ingredient list from the detail page or a structured attribute
    B = "B"  # ingredient list recovered by OCR from a detail-page photo
    C = "C"  # only a marketing claim (title / main image), not a real label
    D = "D"  # no ingredient information at all

    @property
    def trusted(self) -> bool:
        """Only A and B may produce a PASS/FAIL verdict."""
        return self in (EvidenceType.A, EvidenceType.B)


_EVIDENCE_ALIASES = {
    "a": EvidenceType.A,
    "b": EvidenceType.B,
    "c": EvidenceType.C,
    "d": EvidenceType.D,
    "label": EvidenceType.A,
    "attribute": EvidenceType.A,
    "ocr": EvidenceType.B,
    "claim": EvidenceType.C,
    "none": EvidenceType.D,
}

# Values platforms write into a "配料表" field when they have nothing to show.
PLACEHOLDER_INGREDIENTS = {
    "见包装",
    "见包装详情",
    "见外包张详情",
    "详见详情",
    "详见包装",
    "详见商品详情",
    "参考详情",
    "无",
    "暂无",
    "-",
}

_INGREDIENT_PREFIX = re.compile(r"^(?:配料表?|配料|原料|原辅料|ingredients?)\s*[:：]\s*", re.I)


def parse_evidence(value: EvidenceType | str | None) -> EvidenceType:
    """Coerce a loose value into :class:`EvidenceType` (defaults to D)."""
    if isinstance(value, EvidenceType):
        return value
    if value is None:
        return EvidenceType.D
    key = str(value).strip().lower()
    return _EVIDENCE_ALIASES.get(key, EvidenceType.D)


def normalize_ingredient(text: Any) -> str | None:
    """Return clean ingredient text, or ``None`` when there is no real evidence."""
    if text is None:
        return None
    normalized = unicodedata.normalize("NFKC", str(text)).strip()
    if not normalized:
        return None
    if normalized.replace(" ", "") in PLACEHOLDER_INGREDIENTS:
        return None
    normalized = _INGREDIENT_PREFIX.sub("", normalized)
    normalized = normalized.strip().rstrip("。.;；")
    return normalized or None


@dataclass(frozen=True)
class Sku:
    """One purchasable specification, normalised across platforms."""

    platform: str
    sku_id: str
    title: str
    price: float | None
    spec: str
    ingredient_text: str | None
    evidence_type: EvidenceType
    url: str = ""
    evidence_note: str = ""
    checked_at: str = ""
    raw: dict[str, Any] | None = field(default=None, repr=False, compare=False)

    @property
    def has_trusted_evidence(self) -> bool:
        return self.evidence_type.trusted and bool(self.ingredient_text)

    def as_dict(self, include_raw: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "platform": self.platform,
            "sku_id": self.sku_id,
            "title": self.title,
            "price": self.price,
            "spec": self.spec,
            "ingredient_text": self.ingredient_text,
            "evidence_type": self.evidence_type.value,
            "url": self.url,
            "evidence_note": self.evidence_note,
            "checked_at": self.checked_at,
        }
        if include_raw and self.raw is not None:
            data["raw"] = self.raw
        return data


@dataclass(frozen=True)
class SkuDraft:
    """An adapter's pre-normalisation view of one SKU.

    Adapters fill this in; :func:`make_sku` decides the evidence grade so the
    rule lives in exactly one place.
    """

    platform: str
    sku_id: str
    title: str
    price: float | str | None
    spec: str
    ingredient_text: Any = None
    evidence_type: EvidenceType | str | None = None
    url: str = ""
    evidence_note: str = ""
    checked_at: str = ""
    raw: dict[str, Any] | None = None


def make_sku(draft: SkuDraft) -> Sku:
    """Normalise a draft into a :class:`Sku`, inferring evidence when unstated."""
    ingredient = normalize_ingredient(draft.ingredient_text)
    if draft.evidence_type is not None:
        evidence = parse_evidence(draft.evidence_type)
    elif ingredient is not None:
        evidence = EvidenceType.A
    else:
        evidence = EvidenceType.D
    if ingredient is None and evidence.trusted:
        # A trusted grade without text is self-contradictory; downgrade it.
        evidence = EvidenceType.D
    note = draft.evidence_note
    if not note and evidence is EvidenceType.D and not ingredient:
        note = "no ingredient text returned by platform"
    return Sku(
        platform=draft.platform,
        sku_id=str(draft.sku_id),
        title=str(draft.title or "").strip(),
        price=_to_price(draft.price),
        spec=str(draft.spec or "").strip(),
        ingredient_text=ingredient,
        evidence_type=evidence,
        url=draft.url,
        evidence_note=note,
        checked_at=draft.checked_at,
        raw=draft.raw,
    )


def _to_price(value: float | str | None) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"\d+(?:\.\d+)?", unicodedata.normalize("NFKC", str(value)).replace(",", ""))
    return float(match.group(0)) if match else None


def pick(raw: dict[str, Any], *keys: str) -> Any:
    """First non-empty value among ``keys``."""
    for key in keys:
        value = raw.get(key)
        if value not in (None, "", "-", "无"):
            return value
    return None


@runtime_checkable
class Source(Protocol):
    """Minimal interface every platform adapter must expose."""

    platform: str

    def to_sku(self, raw: dict[str, Any]) -> Sku:  # pragma: no cover - protocol
        ...
