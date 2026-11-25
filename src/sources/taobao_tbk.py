"""Taobao union (淘宝客) adapter for ``taobao.tbk.dg.material.optional`` rows.

The material API is promotion-facing: title, main image, coupon price, sales
volume, commission rate, promotion link. No ingredient list, no net weight.
"""

from __future__ import annotations

from typing import Any

from .base import EvidenceType, Sku, SkuDraft, make_sku, pick

PLATFORM = "taobao"


def to_sku(raw: dict[str, Any]) -> Sku:
    item_id = str(pick(raw, "num_iid", "item_id", "numIid") or "")

    url = pick(raw, "coupon_share_url", "item_url") or (
        f"https://item.taobao.com/item.htm?id={item_id}" if item_id else ""
    )

    return make_sku(
        SkuDraft(
            platform=PLATFORM,
            sku_id=item_id,
            title=pick(raw, "title", "short_title") or "",
            price=pick(raw, "zk_final_price", "price", "reserve_price"),
            spec=pick(raw, "spec", "规格") or "",
            ingredient_text=pick(raw, "配料表"),
            evidence_type=EvidenceType.D,
            url=url,
            evidence_note="Taobao union API does not expose ingredient text",
            checked_at=pick(raw, "checked_at") or "",
            raw=raw,
        )
    )
