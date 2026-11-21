from __future__ import annotations

from .reporter import build_report


DEMO_PRODUCTS = (
    {
        "name": "匿名商品 A｜米制薄饼",
        "ingredients": "配料：大米、水、酿造酱油（含小麦）、食盐",
        "additives": "包装未单列",
        "preset": "gluten-free",
        "mode": None,
        "price": 18.0,
        "spec": "600g",
    },
    {
        "name": "匿名商品 B｜薯类脆片",
        "ingredients": "配料：马铃薯、植物蛋白、食盐",
        "additives": "包装未单列",
        "preset": "medical-medium",
        "mode": "level_3",
        "price": 19.9,
        "spec": "500g*2袋",
    },
    {
        "name": "匿名商品 C｜原味米糕",
        "ingredients": "配料：大米、水",
        "additives": "包装未单列",
        "preset": "clean-label",
        "mode": None,
        "price": 24.0,
        "spec": "250g×4袋",
    },
)


def _reasons(report: dict) -> str:
    findings = [*report["audit"]["failures"], *report["audit"]["warnings"]]
    return "；".join(f"{item['match'] or '缺失信息'}：{item['reason']}" for item in findings) or "未命中排除或警示规则"


def main() -> None:
    print("Open Label Auditor｜内置脱敏 Mock Demo（不联网、不需要 API Key）")
    for index, product in enumerate(DEMO_PRODUCTS, start=1):
        report = build_report(
            product["ingredients"],
            product["preset"],
            product["mode"],
            price=product["price"],
            spec=product["spec"],
        )
        pricing = report["pricing"]
        per_jin = pricing.get("price_per_500g")
        unit_price = "需人工核验" if per_jin is None else f"CNY {per_jin:.2f}/斤"
        print(f"\n[{index}] {product['name']}｜{report['conclusion']}")
        print(f"  配料表原文：{product['ingredients']}")
        print(f"  食品添加剂原文：{product['additives']}")
        print(f"  规则：{product['preset']} / {product['mode'] or 'default'}")
        print(f"  审计依据：{_reasons(report)}")
        print(f"  规格与价格：{product['spec']}，CNY {product['price']:.2f}，{unit_price}")


if __name__ == "__main__":
    main()
