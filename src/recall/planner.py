"""Turn one intent into a budgeted, ordered recall plan.

The plan is a plain data object, so it can be printed (``--plan``), cached,
diffed between runs, or handed to a browser agent / union API client as a
work list. Nothing here touches the network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .keywords import Query, expand_queries, load_keywords, resolve_category
from .taxonomy import CategoryTask, build_category_tasks, load_platforms

DEFAULT_PLATFORMS = ("jd", "taobao")


@dataclass
class RecallPlan:
    intent: str
    preset: str | None
    mode: str | None
    queries: list[Query] = field(default_factory=list)
    categories: list[CategoryTask] = field(default_factory=list)
    budget: int = 200
    planned_requests: int = 0
    dropped: list[dict[str, Any]] = field(default_factory=list)

    @property
    def requests(self) -> int:
        return len(self.queries) + sum(task.requests for task in self.categories)

    def as_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "preset": self.preset,
            "mode": self.mode,
            "budget": self.budget,
            "planned_requests": self.planned_requests,
            "requests": self.requests,
            "queries": [query.as_dict() for query in self.queries],
            "categories": [task.as_dict() for task in self.categories],
            "dropped": self.dropped,
        }

    def summary(self) -> dict[str, Any]:
        tiers: dict[int, int] = {}
        for query in self.queries:
            tiers[query.tier] = tiers.get(query.tier, 0) + 1
        for task in self.categories:
            tiers[task.tier] = tiers.get(task.tier, 0) + task.requests
        return {
            "intent": self.intent,
            "preset": self.preset,
            "requests": self.requests,
            "budget": self.budget,
            "by_tier": {f"tier{tier}": count for tier, count in sorted(tiers.items())},
            "dropped": len(self.dropped),
            "platforms": sorted({query.platform for query in self.queries}),
        }


def build_plan(
    intent: str,
    preset: str | None = None,
    mode: str | None = None,
    platforms: Iterable[str] = DEFAULT_PLATFORMS,
    budget: int = 200,
    keyword_config: dict[str, Any] | None = None,
    platform_config: dict[str, Any] | None = None,
) -> RecallPlan:
    """Build an ordered plan and cut it to ``budget`` requests.

    Ordering is strict: tier 1 keyword precision first, tier 2 category
    traversal second, tier 3 long tail last. When the budget runs out, tier 3
    is what gets dropped, so the plan degrades in a predictable direction.
    """
    kw = keyword_config if keyword_config is not None else load_keywords()
    pc = platform_config if platform_config is not None else load_platforms()
    platforms = list(platforms)

    resolved = resolve_category(intent, kw)
    category_name = resolved[0] if resolved else None

    queries = expand_queries(intent, kw, platforms, preset)
    categories = build_category_tasks(platforms, pc, category_name)

    work: list[tuple[int, int, str, Any, int]] = []
    for query in queries:
        work.append((query.tier, 0, "query", query, 1))
    for task in categories:
        work.append((task.tier, 1, "category", task, task.requests))
    work.sort(key=lambda item: (item[0], item[1]))

    plan = RecallPlan(intent=intent, preset=preset, mode=mode, budget=budget)
    planned = 0
    for tier, _phase, kind, payload, cost in work:
        planned += cost
        if plan.requests + cost > budget:
            plan.dropped.append(
                {
                    "kind": kind,
                    "tier": tier,
                    "cost": cost,
                    "item": payload.as_dict(),
                    "reason": "budget exceeded",
                }
            )
            continue
        if kind == "query":
            plan.queries.append(payload)
        else:
            plan.categories.append(payload)
    plan.planned_requests = planned
    return plan
