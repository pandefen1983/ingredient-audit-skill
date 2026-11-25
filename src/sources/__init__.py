"""Source adapters: one module per marketplace, one shared :class:`Sku` shape."""

from __future__ import annotations

from .base import EvidenceType, Sku, SkuDraft, Source, make_sku, normalize_ingredient, parse_evidence
from .douyin import to_sku as douyin_to_sku
from .jd_union import to_sku as jd_to_sku
from .taobao_tbk import to_sku as taobao_to_sku

ADAPTERS = {
    "douyin": douyin_to_sku,
    "jd": jd_to_sku,
    "taobao": taobao_to_sku,
}

__all__ = [
    "ADAPTERS",
    "EvidenceType",
    "Sku",
    "SkuDraft",
    "Source",
    "douyin_to_sku",
    "jd_to_sku",
    "make_sku",
    "normalize_ingredient",
    "parse_evidence",
    "taobao_to_sku",
]
