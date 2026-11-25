# 召回层：关键词扩展 + 类目遍历 + 缓存

`SKILL.md` 里“用同义词、品牌页、类目页建立宽候选池”是一句散文指令，每次执行靠模型临场想词，于是每次搜到的商品都不一样、也说不清搜了多少。这一层把它变成固定代码：同样的意图 → 同样的计划 → 可比的召回数字。

判定逻辑（`auditor` / `pricer` / `reporter`）一行未改，这一层只决定“去抓什么”。

## 四个阶段

| 阶段 | 文件 | 作用 |
|---|---|---|
| P0 关键词扩展 | `src/recall/keywords.py` + `config/keywords.zh-CN.yaml` | 成分×品类、纯/100% 变体、品牌×品类、同义词长尾 |
| P1 类目遍历 | `src/recall/taxonomy.py` + `config/platforms.yaml` | 类目 × 价格分片 × 翻页，捞标题不含关键词的长尾 |
| P2 模糊去重 | `src/recall/normalize.py` | 净含量归一 + 标题相似度，合并“同款不同链接” |
| P3 缓存与预算 | `src/recall/store.py` | SQLite 记录已抓过的 query 与 SKU，TTL 内不重抓 |
| 计划器 | `src/recall/planner.py` | 汇总成优先级队列，按预算裁剪 |

## 用法

```bash
# 1. 出计划（纯本地，不联网，不需要凭证）
python -m src.recall.run --query 面条 --preset medical-medium --level level_3 --summary

# 2. 看完整计划（每条 query 带 tier 与理由）
python -m src.recall.run --query 煎饼 --platform jd,taobao,douyin --out plan.json

# 3. 抓取结果写进缓存后，重算覆盖率漏斗
python -m src.recall.run --query 面条 --report --cache .cache/recall.sqlite3
```

`--summary` 示例输出：

```json
{"intent":"面条","requests":96,"budget":200,
 "by_tier":{"tier1":58,"tier2":18,"tier3":20},"dropped":0,"platforms":["jd","taobao"]}
```

## Tier 与预算

- **tier1**：`成分 × 品类`（荞麦面条、纯荞麦面条、100%荞麦面条）、`品牌 × 品类`（金沙河 面条）
- **tier2**：类目 × 价格分片（0–20 / 20–50 / 50+），每条分片算 `pages` 个请求
- **tier3**：同义词（挂面、龙须面）、`成分 × 形态`（荞麦挂面）

预算不够时**从 tier3 开始砍**，所以计划降级方向可预测：先丢长尾，保住精准词。`dropped` 里逐条记录了被砍的项与原因。

## 为什么这样能缓解限流

不是换 IP，而是“少而准 + 不重复”：

1. 每个平台有 `request_interval_seconds`（京东 1s / 淘宝 1.5s / 抖音 2s），调用方按这个间隔串行；
2. 缓存 TTL 默认 7 天，`should_refetch()` 为 `False` 就跳过；
3. 预算上限默认 200 次，计划先算总数再执行。

## 去重的边界

`dedupe_fuzzy` 按 `平台 + 净含量 + 标题相似度 ≥ 0.85` 合并，保留证据等级最高的那条。

- `500g*2袋` 会归一成 `1000g`，不会和单袋混在一起；
- 不同平台之间不合并（京东和淘宝的 SKU 定价不同）；
- 阈值是经验值，标题差异极大的同款仍可能漏合，宁可少合也不错合。

## 已知局限

- 召回量上去后 `verified_ratio` 会下降（分母变大）。PASS 数量要涨，得靠详情页 OCR 补 B 级证据。
- 不绕验证码、不换 IP，平台分页上限也不会被突破。
- 这一层不发 HTTP：抓取由浏览器 Agent 按计划执行，或将来由联盟 API 客户端喂 JSON 进 `SkuCache`。
