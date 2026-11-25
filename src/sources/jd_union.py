"""JD Union (京东联盟) adapter for ``jd.union.open.goods.query`` rows.

The union API returns promotion-facing fields only: title, image, price,
shop, sales volume. It never returns an ingredient list, so every SKU from
this source is D-grade and must be verified elsewhere before judging.
"""

from __future__ import annotations

from typing import Any

from .base import EvidenceType, Sku, SkuDraft, make_sku, pick

PLATFORM = "jd"

# ``priceInfo.lowestPrice`` comes without an explicit unit in the docs. Rather
# than guessing from the magnitude, the caller declares the unit it actually
# saw, so a 500+ CNY bulk listing can never be silently divided by 100.
#
# Confirm once against a real response: a 500g noodle pack that sells for 11.9
# CNY comes back as ``11.9`` when the unit is yuan, and as ``1190`` when the
# unit is cents.
#
#   jd_to_sku(raw)                       # price is already yuan (default)
#   jd_to_sku(raw, price_unit="cents")    # price is integer cents
PRICE_UNITS = ("yuan", "cents")


def _price_in_yuan(value: Any, price_unit: str = "yuan") -> float | Any:
    """Convert a JD price to yuan using the caller-declared unit."""
    if price_unit not in PRICE_UNITS:
        raise ValueError(f"price_unit must be one of {PRICE_UNITS}, got {price_unit!r}")
    if value is None or value == "":
        return value
    try:
        amount = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return value  # make_sku will try its own parse
    if price_unit == "cents":
        return round(amount / 100, 2)
    return amount


def to_sku(raw: dict[str, Any], price_unit: str = "yuan") -> Sku:
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
            price=_price_in_yuan(
                pick(price_info, "lowestPrice", "price") or pick(raw, "price"),
                price_unit,
            ),
            # goods.query does not expose net weight; callers may pass it after
            # reading the detail page.
            spec=pick(raw, "spec", "netWeight", "规格") or "",
            ingredient_text=pick(raw, "配料表", "ingredients"),
            evidence_type=EvidenceType.D,
            url=url,
            evidence_note=(
                "JD Union goods API does not expose ingredient text"
                if price_unit == "yuan"
                else "JD Union goods API does not expose ingredient text; "
                "price converted from cents (price_unit='cents')"
            ),
            checked_at=pick(raw, "checked_at") or "",
            raw=raw,
        )
    )
