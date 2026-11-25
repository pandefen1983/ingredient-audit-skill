"""Recall layer: deterministic query planning, category traversal, cache.

``auditor`` / ``pricer`` / ``reporter`` are untouched: this package only decides
*what to fetch*, never *how to judge*.
"""

from __future__ import annotations

from .keywords import Query, expand_queries, load_keywords, resolve_category
from .normalize import dedupe_fuzzy, normalize_spec, normalize_title, spec_grams
from .planner import RecallPlan, build_plan
from .store import SkuCache
from .taxonomy import CategoryTask, build_category_tasks, load_platforms, request_interval

__all__ = [
    "CategoryTask",
    "Query",
    "RecallPlan",
    "SkuCache",
    "build_category_tasks",
    "build_plan",
    "dedupe_fuzzy",
    "expand_queries",
    "load_keywords",
    "load_platforms",
    "normalize_spec",
    "normalize_title",
    "request_interval",
    "resolve_category",
    "spec_grams",
]
