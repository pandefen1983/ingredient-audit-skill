# Ingredient Audit Skill

**Ingredient Audit Skill** 是一款专为电商选品与食品成分核验设计的开源 **AI Skill**（支持 Codex / AI Agent / OpenAI Agents SDK），致力于自动化完成**商品搜索**、**配料表**分析与深度**配料表审核（Ingredient Verification）**。项目内置多维度饮食过滤规则，全面支持**美国医疗灵媒（Medical Medium / 安东尼·威廉 Anthony William）**的**安疗饮食**分级排雷标准、严格**无麸质食品（Gluten-Free）**排查、**素食（Vegan / Vegetarian）**筛选以及**零添加（Clean Label）**极简配料表核查，帮助用户在网购时精准避开隐形添加剂与风险成分。

---

## ✨ 核心特性 (Key Features)

* **多维度饮食预设（Dietary Presets）**：开箱即用的规则引擎，支持一键切换或组合多种严苛饮食标准。
* **深度配料表核验（Deep Ingredient Verification）**：不只看商品营销标题，直接解析商品详情页的完整**配料表**文本（含图片识别后的文本），逐项比对风险成分。
* **隐形添加剂识别（Hidden Additive Detection）**：内置同义词与别名映射库，自动揪出“麦芽糊精”“变性淀粉”“酵母提取物”“天然香料（Natural Flavors）”等伪装成分。
* **结构化排雷报告（Structured Audit Report）**：清晰输出【通过 / 警告 / 淘汰】结论、具体触发的违规成分及对应饮食规则依据，并保留精确 SKU 的包装原文证据。
* **单价归一化（Unit-Price Normalization）**：把商品页全部在售规格换算为当地币种每 500g 单价，从低到高排列，避免被多包装标价误导。

---

## 🥗 支持的饮食标准 (Supported Dietary Standards)

| 饮食体系 | 适用人群与场景 | 核心审核与排雷规则 |
| :--- | :--- | :--- |
| **安疗标准 (Medical Medium)** | 遵循**美国医疗灵媒（安东尼·威廉 Anthony William）**饮食法则的用户 | **Level 1 – Level 5** 逐级继承排雷：L1 排除蛋奶、小麦/大麦/黑麦、汽水；L2 增加猪肉、金枪鱼、玉米；L3 增加菜籽油/芥花油、大豆、鱼与海鲜；L4 增加醋、发酵食品、咖啡因；L5 增加大米、藜麦及其他食用油。可叠加 Bonus 附加限制（无盐、无激进脂肪、酒精、天然/人工香料、营养酵母、柠檬酸、人工甜味剂、味精、防腐剂等）。 |
| **严格无麸质 (Strict Gluten-Free)** | 乳糜泻、麸质过敏或严格控麸人群 | 排查小麦、大麦、黑麦、燕麦交叉污染风险，以及酱油、麦芽提取物、部分淀粉中的隐形麸质。 |
| **素食标准 (Vegetarian & Vegan)** | 纯净素、蛋奶素及鱼素主义者 | 支持细分模式（纯净素 / 蛋奶素 / 鱼素），自动识别明胶、胭脂红、乳清粉、蜂蜜、动物源性维生素 D3 等非素食成分。 |
| **配料表极简主义 (Clean Label / 零添加)** | 追求天然原生态、拒绝超加工食品的人群 | 严格执行**零添加**标准，过滤防腐剂、人工色素、香精、增稠剂、味精及呈味核苷酸，并在配料项超过 8 项时发出警告。 |

---

## 🚀 快速开始 (Quick Start)

### 1. 安装 Skill

将本仓库克隆到本地 AI Agent / Codex 技能目录：

```bash
git clone https://github.com/pandefen1983/ingredient-audit-skill.git ~/.codex/skills/ingredient-audit-skill
cd ~/.codex/skills/ingredient-audit-skill
python -m pip install -e .
```

无需 API Key；仓库自带的本地审计与 Demo 不联网。

### 2. 触发与使用示例 (Usage Examples)

在对话中直接向 AI 助手下达**商品搜索**或**配料表审核**指令。首次搜索需先确认购买/收货国家或地区。

* **场景一：按医疗灵媒标准筛选商品**
> “帮我在京东搜索符合**安疗标准（Level 3）**的**无麸质酱油**，并逐一审核它们的**配料表**。”

* **场景二：单品配料表排雷**
> “用 `anliao-food-search` 帮我检查这款燕麦奶的配料表，同时满足**纯净素食**、严格**无麸质**和**零添加（Clean Label）**标准：`水、燕麦、菜籽油、山梨酸钾、碳酸钙、食用盐`。”

### 3. 本地确定性运行

```bash
python -m src.schema medical-medium --mode level_3
python -m src.reporter --preset clean-label --ingredients "配料：水、山梨酸钾" --price 12.9 --spec "100g*2袋"
python evals/run_eval.py
python -m unittest discover -s tests -v
```

---

## 📋 审核输出示例 (Sample Output)

输入上述燕麦奶配料表，开启 **安疗标准（Level 3）+ 严格无麸质 + 零添加** 时，Skill 输出结构化结果：

```text
【审核结论】：❌ 不通过（发现高风险禁用成分）
【适用标准】：安疗标准 Level 3 + 严格无麸质 + 零添加（Clean Label）

【成分逐项核验】：
✅ 水 — 安全
⚠️ 燕麦 — 警告（需确认是否具有认证无麸质标识，以防生产流水线交叉污染）
❌ 菜籽油（芥花油）— 违规 [安疗 Level 3 核心雷区：高度精炼种子油]
❌ 山梨酸钾 — 违规 [零添加标准：防腐剂黑名单]
⚠️ 碳酸钙 — 提示（常见营养强化剂，非纯天然原生态食材）
⚠️ 食用盐 — 提示（安疗 Bonus 无盐选项开启时判为违规）
```

---

## 📂 目录结构 (Repository Structure)

```text
ingredient-audit-skill/
├── SKILL.md                    # AI Agent 核心技能指令、选择门与输出契约
├── agents/openai.yaml          # Codex / OpenAI Agents SDK 元数据
├── presets/                    # 饮食规则与配料表字典（YAML）
│   ├── medical-medium.yaml     # 美国医疗灵媒（安东尼·威廉）Level 1-5 分级规则
│   ├── gluten-free.yaml        # 严格无麸质及隐形麸质别名库
│   ├── vegetarian.yaml         # 素食（纯净素/蛋奶素/鱼素）成分库
│   └── clean-label.yaml        # 零添加极简配料表添加剂黑名单
├── src/                        # 确定性审计、计价、报告与 CLI 模块
├── evals/                      # 离线 golden set 与评估报告
├── tests/                      # 单元测试与基准样例
├── references/                 # 安疗分级资料出处
├── docs/                       # 设计与开源申请草稿
└── README.md                   # 项目说明文档
```

---

## ⚠️ 免责声明 (Disclaimer)

本工具仅用于辅助解析公开食品配料表信息与饮食偏好筛选，不构成任何医疗诊断、临床营养治疗建议或已确立的医学证据。食品厂商可能随时更改配方，购买及食用前请务必以商品实物外包装的最新**配料表**为准。
