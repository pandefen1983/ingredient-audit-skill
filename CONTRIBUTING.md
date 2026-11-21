# Contributing to Open Label Auditor

Thank you for helping make food-label screening more transparent. Contributions should preserve the project’s core invariant: every decision must be reproducible from quoted label/specification evidence, and uncertainty must not be converted into a confident pass.

## Development setup

```bash
python -m venv .venv
# Activate the environment for your shell, then:
python -m pip install -e .
python -m unittest discover -s tests -v
python evals/run_eval.py
python -m src.demo
```

The runtime intentionally uses only the Python standard library. Preset files use the JSON-compatible subset of YAML and are loaded without a YAML dependency.

## Adding a screening preset

New presets may cover ketogenic diets, low-purine screening, halal checks, pet-food label review, or another clearly scoped use case.

1. Add `presets/<preset-name>.yaml` with a lowercase hyphenated name, a concise description, a default mode, and explicit `exclude_terms`, `allow_terms`, `fail_patterns`, or `warn_patterns`.
2. Use `FAIL` only for evidence that clearly violates the selected rule. Use a warning pattern when the ingredient source or manufacturing context is ambiguous.
3. Attribute source-based frameworks and distinguish source claims from medical or scientific consensus.
4. Add focused unit tests in `tests/test_presets.py` for inheritance, allowed exceptions, ambiguous terms, and custom exclusions.
5. Document the preset in the README table and, when substantial source detail is needed, add a focused file under `references/` and link it from `SKILL.md`.

Do not add rules based only on a single marketing page or silently broaden an existing preset’s meaning.

## Adding benchmark traps

Append anonymized cases to `tests/fixtures/benchmark_cases.json`. The original 36 cases and four baseline categories must remain intact; additional cases are allowed.

Each case requires:

- `id`: unique and non-identifying;
- `category`: an existing category or a documented new category;
- `preset` and optional `variant`, `options`, or `custom_excludes`;
- `ingredients_text`: complete synthetic or anonymized label text;
- `price_yuan` and `spec_text`;
- `expected_status`: `PASS`, `WARN`, or `FAIL`;
- `expected_needs_manual_check`;
- `expected_unit_price_per_100`, using `null` when no guaranteed denominator exists.

Useful additions include hidden compound ingredients, OCR errors, `买一送一`, drained/solid weight, approximate or random weight, mixed units, and clean counterexamples that protect against false positives. Never commit a real customer name, order number, address, account identifier, cookie, credential, or private product screenshot.

If a new category is introduced, update `EXPECTED_CATEGORIES` and the validation/report logic in `evals/run_eval.py`. Keep the unit-price tolerance at `±0.05` unless a pull request explains and tests a different policy.

## Pull requests

- Keep the diff focused and explain the user-visible behavior change.
- Include evidence for new rules and regression cases for bug fixes.
- Run the unit tests, golden evaluation, and Mock Demo locally.
- Do not manually edit benchmark scores in the README unless `evals/report_latest.md` was regenerated and supports those exact figures.
- All GitHub Actions checks must pass before merge.

## 中文要点

- 新增预设时要明确适用范围；确定违规才判 `FAIL`，来源不明应判 `WARN`。
- 新增黄金案例必须脱敏，并完整填写配料、价格、规格、预期状态、人工核验和单位价格字段。
- 不得提交姓名、订单号、地址、账号、Cookie、密钥或其他隐私数据。
- PR 必须通过单元测试、`evals/run_eval.py` 自动测评和本地 Mock Demo。
