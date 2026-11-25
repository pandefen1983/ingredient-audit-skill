"""Command line entry point for the recall layer.

    python -m src.recall.run --query 面条 --preset medical-medium --level 3
    python -m src.recall.run --query 面条 --summary
    python -m src.recall.run --query 面条 --report --cache .cache/recall.sqlite3

``--plan`` (the default) is pure local computation: no network, no credentials.
``--report`` only reads the local cache, so it is equally safe to run offline.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from ..pipeline import run_pipeline
from ..sources import ADAPTERS
from .normalize import dedupe_fuzzy
from .planner import build_plan
from .store import SkuCache


def build_cache_report(
    cache: SkuCache,
    preset: str,
    mode: str | None = None,
    platforms: Iterable[str] | None = None,
    threshold: float = 0.85,
) -> dict[str, Any]:
    """Rebuild SKUs from cached raw payloads and run the existing pipeline."""
    wanted = set(platforms) if platforms else None
    skus = []
    by_platform: dict[str, int] = {}
    skipped: dict[str, int] = {}
    for platform, payload in cache.load_raw():
        if wanted and platform not in wanted:
            continue
        adapter = ADAPTERS.get(platform)
        if adapter is None:
            skipped[platform] = skipped.get(platform, 0) + 1
            continue
        sku = adapter(payload)
        by_platform[platform] = by_platform.get(platform, 0) + 1
        skus.append(sku)

    deduped = dedupe_fuzzy(skus, threshold=threshold)
    output = run_pipeline(deduped, preset, mode)
    output["sources"] = {
        "raw_from_cache": len(skus),
        "after_fuzzy_dedupe": len(deduped),
        "by_platform": by_platform,
        "skipped_unknown_platform": skipped,
        "cache": cache.stats(),
    }
    return output


def _platforms(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.recall.run",
        description="Plan a marketplace recall run, or report on cached results.",
    )
    parser.add_argument("--query", required=True, help="品类或搜索意图，例如 面条 / 煎饼 / 米线")
    parser.add_argument("--preset", default="medical-medium")
    parser.add_argument("--level", dest="mode", default=None, help="例如 level_3")
    parser.add_argument("--mode", dest="mode", default=None)
    parser.add_argument("--platform", default="jd,taobao", help="逗号分隔：jd,taobao,douyin")
    parser.add_argument("--budget", type=int, default=200, help="最大请求数")
    parser.add_argument("--cache", default=".cache/recall.sqlite3")
    parser.add_argument("--report", action="store_true", help="从本地缓存重新计算覆盖率漏斗")
    parser.add_argument("--summary", action="store_true", help="只打印计划摘要")
    parser.add_argument("--out", default=None, help="把结果写到该 JSON 文件")
    parser.add_argument("--indent", type=int, default=2)
    args = parser.parse_args(argv)

    platforms = _platforms(args.platform)

    if args.report:
        cache = SkuCache(args.cache)
        try:
            result: Any = build_cache_report(cache, args.preset, args.mode, platforms)
        finally:
            cache.close()
    else:
        plan = build_plan(
            args.query,
            preset=args.preset,
            mode=args.mode,
            platforms=platforms,
            budget=args.budget,
        )
        result = plan.summary() if args.summary else plan.as_dict()

    text = json.dumps(result, ensure_ascii=False, indent=args.indent)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
