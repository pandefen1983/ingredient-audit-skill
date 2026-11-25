# 多平台 Adapter 与证据分级

这个目录把「去哪个平台搜」和「怎么判定」拆开：每个平台一个 adapter，统一输出 `Sku`，`auditor / pricer / reporter` 保持不动。

## 为什么

| 平台 | 能否拿到配料表 | 说明 |
|---|---|---|
| 抖音商品 | 常能（A 级） | 商品属性里的「配料表」字段 |
| 京东联盟 | 不能（D 级） | `goods.query` 只给标题、主图、价格、销量 |
| 淘宝客 | 不能（D 级） | 物料接口只给标题、主图、券后价、佣金 |

联盟 API 能解决「搜得全、不被风控」，但解决不了「配料表」；核验必须落在详情页或 OCR 上。

## `Sku` 字段

```python
Sku(
    platform="douyin",          # douyin / jd / taobao
    sku_id="3685154883787522",  # 平台侧唯一 ID
    title="100%纯荞麦挂面 500g",
    price=12.53,                # 券后价，元
    spec="1000g",               # 净含量，元/斤靠它折算
    ingredient_text="荞麦粉、生活饮用水",  # 取不到就是 None，绝不编造
    evidence_type=EvidenceType.A,
    url="https://haohuo.jinritemai.com/...",
    evidence_note="",
    checked_at="2026-11-25",
)
```

## 证据等级

| 等级 | 来源 | 能否判 PASS/FAIL |
|---|---|---|
| A | 详情页/属性栏配料表原文 | 能 |
| B | 详情页长图 OCR | 能 |
| C | 只有标题、主图宣称 | 不能，只能 `UNVERIFIED` |
| D | 没有任何配料信息 | 不能，`UNVERIFIED` |

`has_trusted_evidence` 是唯一闸门：C/D 一律不进入 `auditor`，避免「标题写纯荞麦、实际掺大豆」被判成合格。

## 用法

```python
from src.pipeline import run_pipeline
from src.sources import douyin_to_sku, jd_to_sku

skus = [douyin_to_sku(raw) for raw in douyin_rows] + [jd_to_sku(raw) for raw in jd_rows]
output = run_pipeline(skus, "medical-medium", "level_3")
print(output["funnel"])
# {'recalled': 180, 'unique': 162, 'with_trusted_evidence': 41, 'verified_ratio': 0.2531,
#  'verdicts': {'PASS': 12, 'WARN': 5, 'FAIL': 24, 'UNVERIFIED': 121}, 'judged': 41, 'pass_rate_of_verified': 0.2927}
```

单条判定：

```python
from src.pipeline import audit_sku
audit_sku(sku, "medical-medium", "level_3", options=["preservatives"])
```

## 覆盖率漏斗

`build_funnel` 输出 `recalled → unique → with_trusted_evidence → verdicts`，让「只找到 3 款」变成可解释的数字：不是市面只有 3 款，而是 180 条里只有 41 条拿到了可信配料表。

## 加一个新平台

1. 新建 `src/sources/<platform>.py`，实现 `to_sku(raw) -> Sku`；
2. 在 `src/sources/__init__.py` 的 `ADAPTERS` 里注册；
3. 在 `tests/test_sources.py` 补一份真实 payload 的用例。

注意：**adapter 只负责搬运字段，不推断证据等级以外的信息**。拿不到配料表就老实写 `None + D`，不要用标题补。
