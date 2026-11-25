"""JD Union (京东联盟) adapter for ``jd.union.open.goods.query`` rows.

The union API returns promotion-facing fields only: title, image, price,
shop, sales volume. It never returns an ingredient list, so every SKU from
this source is D-grade and must be verified elsewhere before judging.
"""

from __future__ import annotations

from typing import Any

from .base import EvidenceType, Sku, SkuDraft, make_sku, pick

PLATFORM = "jd"


def to_sku(raw: dict[str, Any]) -> Sku:
    price_info = raw.get("priceInfo") or {}
    sku_id = str(pick(raw, "skuId", "sku_id") or "")

    url = pick(raw, "materialUrl", "itemUrl", "url") or (
        f"https://item.jd.com/{sku_id}.html" if sku_id else ""
    )

    return make_sku(
        SkuDraft(
            platform=PLATFORM,
            sku_id=sku_id,
            title=pick(raw, "skuName", "title") or "",
            price=pick(price_info, "lowestPrice", "price") or pick(raw, "price"),
            # goods.query does not expose net weight; callers may pass it after
            # reading the detail page.
            spec=pick(raw, "spec", "netWeight", "规格") or "",
            ingredient_text=pick(raw, "配料表", "ingredients"),
            evidence_type=EvidenceType.D,
            url=url,
            evidence_note="JD Union goods API does not expose ingredient text",
            checked_at=pick(raw, "checked_at") or "",
            raw=raw,
        )
    )
