# Codex for Open Source application draft

Replace bracketed fields after the public repository and maintainer profile exist. Do not claim usage metrics that are not publicly verifiable.

## Project

**Project name:** Open Label Auditor / 安疗标准食品搜索工具

**GitHub repository:** `[public repository URL]`

**Brief description:**

Open Label Auditor is an open-source Codex skill and dependency-free Python toolkit for auditable food shopping. It asks users to choose Medical Medium, gluten-free, vegetarian, or custom rules; keeps exact-SKU ingredient and additive evidence visible; detects missing or conflicting evidence; and normalizes every purchasable package size for fair price comparison. Medical Medium claims are source-attributed and clearly separated from established medical evidence. The project focuses on reproducibility and Chinese-commerce use cases without scraping accounts or storing credentials.

## Why it matters to the ecosystem

Shopping agents can easily overstate confidence because marketplace titles, snippets, variants, and packaging images do not reliably identify the same formula. Open Label Auditor contributes reusable evidence-handling rules, deterministic preset evaluation, regression tests for false approvals, and transparent uncertainty states that other agent projects can inspect and extend.

## How API credits would be used

- Run reproducible evaluation suites against anonymized product-label and specification fixtures.
- Test multilingual requirement parsing and candidate-recall strategies across contributed examples.
- Review pull requests for evidence-binding regressions, unsafe certainty, and missed edge cases.
- Generate and verify release notes, migration notes, and maintainer triage summaries.
- Compare agent behavior across revisions while keeping deterministic audit modules as the ground truth.

## Maintainer evidence to add before applying

- `[maintainer GitHub profile and write access]`
- `[license and tagged release]`
- `[CI test badge]`
- `[issues or pull requests from users]`
- `[stars, forks, downloads, or other honest usage evidence]`
- `[one or two concrete examples of a prevented false-positive recommendation]`

## Near-term roadmap

1. Publish a stable preset schema and versioning policy.
2. Add structured candidate-ledger export for independent review.
3. Expand specification parsing through regression-driven contributions.
4. Grow the public benchmark beyond its 36-case baseline while preserving category balance.
5. Add independently reviewed exact-SKU evidence fixtures where licensing permits redistribution.
