"""Deterministic keyword expansion for marketplace recall.

``SKILL.md`` asks the agent to "build a wide candidate pool with synonyms,
brands and category pages". That is prose, so every run produces a different
handful of queries. This module turns the same intent into a fixed, countable
query list: same input -> same plan -> comparable recall numbers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

CONFIG_ROOT = Path(__file__).resolve().parents[2] / "config"
DEFAULT_KEYWORDS = CONFIG_ROOT / "keywords.zh-CN.yaml"


@dataclass(frozen=True)
class Query:
    """One marketplace search request."""

    platform: str
    query: str
    tier: int
    source: str
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "query": self.query,
            "tier": self.tier,
            "source": self.source,
            "reason": self.reason,
        }


def load_keywords(path: Path | str | None = None) -> dict[str, Any]:
    """Load the keyword pools (JSON-compatible YAML, no PyYAML needed)."""
    target = Path(path) if path else DEFAULT_KEYWORDS
    return json.loads(Path(target).read_text(encoding="utf-8"))


def resolve_category(
    intent: str, config: dict[str, Any]
) -> tuple[str, dict[str, Any]] | None:
    """Match a free-text intent onto a configured category."""
    wanted = (intent or "").strip()
    if not wanted:
        return None
    categories = config.get("categories", {})
    for name, entry in categories.items():
        names = [name, *entry.get("variants", []), *entry.get("aliases", [])]
        if wanted == name or wanted in names:
            return name, entry
    for name, entry in categories.items():
        candidates = [name, *entry.get("aliases", [])]
        if any(candidate and (wanted in candidate or candidate in wanted) for candidate in candidates):
            return name, entry
    return None


def preset_ingredients(config: dict[str, Any], preset: str | None) -> list[str]:
    """Ingredients worth prefixing queries with, given the active preset."""
    prefixes = config.get("prefixes", {})
    table = prefixes.get("preset_ingredients", {})
    if preset and preset in table:
        return list(table[preset])
    return list(prefixes.get("ingredients", []))


def expand_queries(
    intent: str,
    config: dict[str, Any],
    platforms: Iterable[str],
    preset: str | None = None,
) -> list[Query]:
    """Expand one intent into a tiered, de-duplicated query list.

    Tiers:
      1 - highest precision (ingredient x category, brand x category)
      2 - category traversal (built by :mod:`src.recall.taxonomy`)
      3 - long tail (alias-only, ingredient x form)

    Tier 3 is the first thing a budget cut removes, so precision survives
    when the request budget is tight.
    """
    resolved = resolve_category(intent, config)
    if resolved is None:
        # Unknown category: keep the user's own words as a single precise query
        # instead of inventing ingredient monsters like "荞麦不存在的品类".
        return [
            Query(platform=platform, query=(intent or "").strip(), tier=1, source="intent")
            for platform in platforms
            if (intent or "").strip()
        ]

    category_name, entry = resolved
    base = entry.get("primary", category_name)
    aliases = list(entry.get("aliases", []))
    variants = list(entry.get("variants", []))
    brands = [
        brand.get("name", "")
        for brand in config.get("brands", [])
        if category_name in brand.get("categories", [])
    ]

    ingredients = preset_ingredients(config, preset)
    queries: list[Query] = []
    seen: set[tuple[str, str]] = set()

    def add(platform: str, text: str, tier: int, source: str, reason: str = "") -> None:
        clean = (text or "").strip()
        if not clean:
            return
        key = (platform, clean)
        if key in seen:
            return
        seen.add(key)
        queries.append(
            Query(platform=platform, query=clean, tier=tier, source=source, reason=reason)
        )

    for platform in platforms:
        # Tier 1: ingredient x category, then pure / 100% variants.
        for ingredient in ingredients:
            add(platform, f"{ingredient}{base}", 1, "ingredient", f"{ingredient} 是当前预设允许的原料")
            add(platform, f"纯{ingredient}{base}", 1, "ingredient+pure", f"排除掺杂，锁定纯{ingredient}")
            add(platform, f"100%{ingredient}{base}", 1, "ingredient+claim", "商家常用宣称写法")
        # Tier 1: known brands that sell this category.
        for brand in brands:
            add(platform, f"{brand} {base}", 1, "brand", f"{brand} 在该品类有在售商品")
        # Tier 3: aliases and ingredient x form, cheapest to drop.
        for alias in aliases[:4]:
            add(platform, alias, 3, "alias", "同义词/俗名，覆盖不同叫法")
        for ingredient in ingredients[:3]:
            for form in variants[:2]:
                if form != base:
                    add(platform, f"{ingredient}{form}", 3, "ingredient+form", "原料 + 形态词")
    return queries
