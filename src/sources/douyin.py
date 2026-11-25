"""Douyin mall adapter.

Douyin is the only mainstream platform that routinely exposes a structured
``配料表`` attribute, so its SKUs usually arrive as A-grade evidence.
"""

from __future__ import annotations

from typing import Any

from .base import EvidenceType, Sku, SkuDraft, make_sku, pick

PLATFORM = "douyin"
PLACEHOLDER_EVIDENCE = {"详见详情", "见包装", "参考详情"}

_DETAIL_URL = "https://haohuo.jinritemai.com/views/product/item2?id={product_id}"


def to_sku(raw: dict[str, Any]) -> Sku:
    """Map a flattened Douyin product/SKU record onto :class:`Sku`."""
    product_id = str(pick(raw, "product_id", "productId") or "")
    sku_id = str(pick(raw, "sku_id", "skuId") or product_id)

    ingredient = pick(raw, "配料表", "配料", "配料组成", "原料成分")
    if ingredient is not None and str(ingredient).strip() in PLACEHOLDER_EVIDENCE:
        ingredient = None

    note = ""
    if ingredient is None:
        note = "Douyin listing carries no ingredient text; open the detail page or OCR the label"

    url = pick(raw, "url", "detail_url") or (_DETAIL_URL.format(product_id=product_id) if product_id else "")

    return make_sku(
        SkuDraft(
            platform=PLATFORM,
            sku_id=sku_id,
            title=pick(raw, "title", "商品名称") or "",
            price=pick(raw, "price", "价格"),
            spec=pick(raw, "spec", "单件净含量", "规格", "净含量") or "",
            ingredient_text=ingredient,
            evidence_type=EvidenceType.A if ingredient is not None else EvidenceType.D,
            url=url,
            evidence_note=note,
            checked_at=pick(raw, "checked_at", "search_time") or "",
            raw=raw,
        )
    )
